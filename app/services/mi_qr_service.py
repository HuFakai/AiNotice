# -*- coding: utf-8 -*-
"""
小米账号扫码登录服务

协议参考 PiotrMachowski/Xiaomi-cloud-tokens-extractor 的 QR 实现：
1. GET https://account.xiaomi.com/longPolling/loginUrl  -> {qr, loginUrl, lp, timeout}
2. 展示 qr 图片（本服务代理下载，避免混合内容/CORS 问题）
3. 长轮询 lp 地址 -> 登录完成后返回 {userId, ssecurity, cUserId, passToken, location}
4. （由 miservice 的 MiAccount 在首次 API 调用时用 passToken 自动换取 serviceToken）

会话状态持久化到数据库（mi_qr_sessions 表）：
- uvicorn reload（API_DEBUG=True）、多 worker 部署、进程重启都不会丢会话
- （此前存进程内存，曾导致"二维码能显示但轮询报会话不存在"）

会话状态机: waiting -> confirmed -> consumed；waiting -> expired/error
"""

import time
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx
from sqlalchemy import select, delete
from loguru import logger

from app.database import AsyncSessionLocal
from app.models.mi_qr_session import MiQrSession

LOGIN_URL = "https://account.xiaomi.com/longPolling/loginUrl"
SID = "xiaomiio"
POLL_TIMEOUT_SECONDS = 8           # 单次轮询对小米 lp 的最长等待（须小于常见客户端/代理超时）
STALE_SESSION_GRACE = 120          # 过期会话在库中的保留宽限（秒），便于排查后清理
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _strip_prefix(text: str) -> str:
    """小米接口响应以 &&&START&&& 开头，去掉后才是 JSON。"""
    if text.startswith("&&&START&&&"):
        text = text[len("&&&START&&&"):]
    return text.strip()


def generate_device_id() -> str:
    """生成与 miservice 同规格的 16 位大写十六进制设备 ID。"""
    return secrets.token_hex(8).upper()


class MiQrLoginService:
    """小米扫码登录会话管理（数据库持久化）"""

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
        """SQLite 读回的 datetime 是 naive，统一按 UTC 归一化后再比较"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @classmethod
    def _is_expired(cls, session: MiQrSession) -> bool:
        created = cls._utc_aware(session.created_at)
        if created is None:
            return True
        return datetime.now(timezone.utc) - created > timedelta(seconds=session.timeout_seconds)

    @staticmethod
    def _public_payload(session: MiQrSession, message: Optional[str] = None) -> Dict:
        return {
            "status": session.status,
            "message": message or "",
            "account_id": None,
            "mi_username": None,
        }

    async def _mark(self, session_id: str, status: str, result: Optional[dict] = None) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(MiQrSession, session_id)
            if row:
                row.status = status
                row.result_json = result
                await db.commit()

    async def _cleanup_expired(self) -> None:
        """清理过期/已完结会话行，防止表无限增长。"""
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    delete(MiQrSession).where(
                        MiQrSession.updated_at < datetime.now(timezone.utc) - timedelta(
                            seconds=POLL_TIMEOUT_SECONDS + STALE_SESSION_GRACE + 600
                        )
                    )
                )
                await db.commit()
        except Exception as e:
            logger.debug(f"扫码会话清理失败（忽略）: {e}")

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    async def create_session(self, user_id: int, display_name: Optional[str] = None) -> Dict:
        """创建扫码登录会话，返回二维码信息。"""
        params = {
            "_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false",
            "sid": SID,
            "serviceParam": "",
            "_locale": "zh_CN",
            "_dc": str(int(time.time() * 1000)),
        }
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            resp = await client.get(LOGIN_URL, params=params)
            resp.raise_for_status()
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else None
            if data is None:
                import json

                data = json.loads(_strip_prefix(resp.text))

        if not data.get("qr") or not data.get("lp"):
            raise ValueError("小米服务未返回二维码信息")

        session_id = uuid.uuid4().hex
        timeout = int(data.get("timeout") or 300)
        async with AsyncSessionLocal() as db:
            db.add(
                MiQrSession(
                    session_id=session_id,
                    user_id=user_id,
                    qr_url=data["qr"],
                    login_url=data.get("loginUrl", ""),
                    lp_url=data["lp"],
                    timeout_seconds=timeout,
                    display_name=display_name,
                    status="waiting",
                )
            )
            await db.commit()

        # 顺带清理历史会话（低频操作，不阻塞主流程）
        try:
            await self._cleanup_expired()
        except Exception:
            pass

        return {
            "session_id": session_id,
            "qr_image_url": f"/api/v1/mi-accounts/qr/{session_id}/image",
            "login_url": data.get("loginUrl", ""),
            "expires_in": timeout,
        }

    async def _get_session(self, session_id: str, user_id: int) -> Optional[MiQrSession]:
        """取会话（校验归属 + 过期标记）。"""
        async with AsyncSessionLocal() as db:
            row = await db.get(MiQrSession, session_id)
            if not row or row.user_id != user_id:
                return None
            if row.status == "waiting" and self._is_expired(row):
                row.status = "expired"
                await db.commit()
            # 脱离会话对象返回（避免跨会话使用）
            db.expunge(row)
            return row

    async def get_qr_image(self, session_id: str, user_id: int) -> Optional[bytes]:
        """下载二维码 PNG（代理小米的图片地址）。"""
        session = await self._get_session(session_id, user_id)
        if not session:
            return None
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(session.qr_url)
            resp.raise_for_status()
            return resp.content

    async def poll_status(self, session_id: str, user_id: int) -> Dict:
        """
        轮询扫码状态。

        服务端对小米 lp 地址做一次最长 POLL_TIMEOUT_SECONDS 的等待，
        前端以 2~3 秒间隔调用本接口即可。
        """
        session = await self._get_session(session_id, user_id)
        if not session:
            return {"status": "expired", "message": "会话不存在或已过期，请重新获取二维码"}

        if session.status == "confirmed":
            return {"status": "confirmed", "message": "登录成功"}

        if session.status in ("expired", "error"):
            return {"status": session.status, "message": "二维码已过期，请重新获取"}

        created = MiQrLoginService._utc_aware(session.created_at)
        if created is None or (datetime.now(timezone.utc) - created).total_seconds() > session.timeout_seconds:
            await self._mark(session_id, "expired")
            return {"status": "expired", "message": "二维码已过期，请重新获取"}

        # 对小米 lp 做一次短等待的长轮询
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(POLL_TIMEOUT_SECONDS, connect=10),
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(session.lp_url)
        except httpx.TimeoutException:
            return self._public_payload(session, "等待扫码")
        except httpx.HTTPError as e:
            logger.warning(f"小米扫码轮询请求失败: {e}")
            return self._public_payload(session, "网络波动，继续等待")

        if resp.status_code != 200:
            return self._public_payload(session, "等待扫码")

        try:
            import json

            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else json.loads(
                _strip_prefix(resp.text)
            )
        except (ValueError, json.JSONDecodeError):
            return self._public_payload(session, "等待扫码")

        user_id_mi = data.get("userId")
        pass_token = data.get("passToken")
        if not user_id_mi or not pass_token:
            await self._mark(session_id, "error")
            logger.error(f"小米扫码轮询返回缺少凭据字段: {list(data.keys())}")
            return {"status": "error", "message": "登录数据异常，请重试"}

        result = {
            "mi_user_id": str(user_id_mi),
            "mi_pass_token": pass_token,
            "c_user_id": data.get("cUserId"),
            "display_name": session.display_name,
        }
        await self._mark(session_id, "confirmed", result)
        logger.info(f"小米扫码登录成功: userId={user_id_mi}")
        return {"status": "confirmed", "message": "登录成功"}

    async def mark_error(self, session_id: str, user_id: int, message: str) -> None:
        """绑定失败时把会话标记为 error，允许用户重试或重新扫码。"""
        async with AsyncSessionLocal() as db:
            row = await db.get(MiQrSession, session_id)
            if row and row.user_id == user_id:
                row.status = "error"
                row.result_json = None
                await db.commit()

    async def consume_result(self, session_id: str, user_id: int) -> Optional[dict]:
        """取出并清除扫码结果（只允许消费一次，防止 token 泄露）。"""
        async with AsyncSessionLocal() as db:
            row = await db.get(MiQrSession, session_id)
            if not row or row.user_id != user_id or row.status != "confirmed" or not row.result_json:
                return None
            result = dict(row.result_json)
            row.status = "consumed"
            row.result_json = None
            await db.commit()
            return result


# 全局单例
mi_qr_login_service = MiQrLoginService()
