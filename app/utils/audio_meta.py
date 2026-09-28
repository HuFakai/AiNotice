# -*- coding: utf-8 -*-
"""
音频时长估算

小爱音箱的 URL 音频播放在部分固件上会单曲循环（设备侧行为，无法通过
loop 设置关闭），因此服务端需要知道音频时长，在播放结束后自动下发停止。

解析策略：
1. mutagen 完整解析（优先，支持 MP3/WAV/OGG/FLAC/M4A）
2. 失败时对 MP3 做帧头估算（CBR 精确；VBR 误差数秒可接受）
3. 均失败返回 None（调用方跳过自动停止并提示）
"""

import io
import struct
from typing import Optional

import httpx
from loguru import logger

MAX_DOWNLOAD = 20 * 1024 * 1024  # 20MB
DOWNLOAD_TIMEOUT = 15

# MPEG1 Layer3 比特率表（kbps）
_MP3_BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
_MP3_SAMPLERATES = [44100, 48000, 32000, 0]


async def fetch_audio_bytes(url: str) -> Optional[bytes]:
    """下载音频内容（≤20MB），失败返回 None"""
    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
        if len(data) > MAX_DOWNLOAD:
            logger.warning(f"音频时长估算：文件超过 {MAX_DOWNLOAD} 字节，跳过解析")
            return None
        return data
    except Exception as e:
        logger.warning(f"音频时长估算：下载失败 {type(e).__name__}: {e}")
        return None


def _mp3_duration_estimate(data: bytes) -> Optional[float]:
    """从首个 MPEG 帧头估算时长（秒）"""
    idx = data.find(b"\xff\xfb")
    if idx == -1:
        idx = data.find(b"\xff\xf3")  # MPEG2 Layer3
        if idx == -1:
            return None
    if idx + 4 > len(data):
        return None
    header = data[idx : idx + 4]
    try:
        _, _, b3, b4 = struct.unpack("BBBB", header)
    except Exception:
        return None

    bitrate_idx = (b3 >> 4) & 0x0F
    samplerate_idx = (b4 >> 2) & 0x03
    bitrate = _MP3_BITRATES[bitrate_idx]
    samplerate = _MP3_SAMPLERATES[samplerate_idx]
    if not bitrate or not samplerate:
        return None

    # 跳过 ID3v2 标签体积（帧头位于标签之后）
    audio_size = len(data)
    if data[:3] == b"ID3":
        try:
            tag_size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
            audio_size = max(0, len(data) - 10 - tag_size)
        except Exception:
            pass

    return audio_size * 8.0 / (bitrate * 1000)


def estimate_duration_sync(data: bytes) -> Optional[float]:
    """从音频字节估算时长（秒）；失败返回 None"""
    try:
        from mutagen import File as MutagenFile

        info = MutagenFile(io.BytesIO(data))
        if info is not None and getattr(info.info, "length", None):
            return float(info.info.length)
    except Exception as e:
        logger.debug(f"mutagen 解析失败，回退 MP3 帧头估算: {e}")

    return _mp3_duration_estimate(data)


async def estimate_audio_duration(url: str) -> Optional[float]:
    """下载远端音频并估算时长（秒）；任一环节失败返回 None"""
    data = await fetch_audio_bytes(url)
    if not data:
        return None
    return estimate_duration_sync(data)
