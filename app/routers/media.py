# -*- coding: utf-8 -*-
"""
音频媒体上传

为通知渠道的"音频播报"模式提供在线音频托管：
- POST /api/v1/media/upload：登录用户上传音频文件（≤20MB），
  返回可直链访问的 URL（/media/{文件名}，静态公开访问——音箱需要匿名拉取）
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from loguru import logger

from app.dependencies import get_current_active_user
from app.models.user import User

router = APIRouter(prefix="/media", tags=["音频媒体"])

MAX_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}


def media_dir() -> Path:
    d = Path("data/media")
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/upload", summary="上传音频文件", description="上传 MP3/WAV/OGG/FLAC/M4A/AAC 音频（≤20MB），返回可公网直链的播放 URL")
async def upload_audio(
    file: UploadFile = File(..., description="音频文件"),
    current_user: User = Depends(get_current_active_user),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的音频格式 {ext or '(无后缀)'}，仅允许: {', '.join(sorted(ALLOWED_EXTS))}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="音频文件超过 20MB 限制")
    if not content:
        raise HTTPException(status_code=400, detail="空文件")

    fname = f"{uuid.uuid4().hex}{ext}"
    target = media_dir() / fname
    target.write_bytes(content)

    url = f"/media/{fname}"
    logger.info(f"音频上传成功: user={current_user.username} file={fname} size={len(content)}")
    return {"success": True, "url": url, "filename": file.filename, "size": len(content)}
