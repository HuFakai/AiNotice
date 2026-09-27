# -*- coding: utf-8 -*-
"""
小米账号扫码登录服务

协议参考 PiotrMachowski/Xiaomi-cloud-tokens-extractor 的 QR 实现：
1. GET https://account.xiaomi.com/longPolling/loginUrl  -> {qr, loginUrl, lp, timeout}
2. 展示 qr 图片（本服务代理下载，避免混合内容/CORS 问题）
3. 长轮询 lp 地址 -> 登录完成后返回 {userId, ssecurity, cUserId, passToken, location}
4. （由 miservice 的 MiAccount 在首次 API 调用时用 passToken 自动换取 serviceToken）

会话状态保存在进程内存中（单实例部署），确认后凭据只落库、不回传前端。
"""

import time
import uuid
import secrets
from typing import Dict, Optional

import httpx
from loguru import logger

LOGIN_URL = "https://account.xiaomi.com/longPolling/loginUrl"
SID = "xiaomiio"
SESSION_TTL_SECONDS = 300          # 会话最长有效期兜底
POLL_TIMEOUT_SECONDS = 25          # 单次轮询请求的服务端最长等待
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
    """小米扫码登录会话管理"""

    def __init__(self):
        # session_id -> {user_id, qr_url, login_url, lp_url, timeout, created_at,
        #                status: waiting|confirmed|expired|error, result: {...}}
        self._sessions: Dict[str, dict] = {}

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [sid for sid, s in self._sessions.items() if now - s["created_at"] > SESSION_TTL_SECONDS + 60]
        for sid in expired:
            self._sessions.pop(sid, None)

    async def create_session(self, user_id: int, display_name: Optional[str] = None) -> Dict:
        """创建扫码登录会话，返回二维码信息。"""
        self._cleanup()
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
        timeout = int(data.get("timeout") or 180)
        self._sessions[session_id] = {
            "user_id": user_id,
            "qr_url": data["qr"],
            "login_url": data.get("loginUrl", ""),
            "lp_url": data["lp"],
            "timeout": timeout,
            "display_name": display_name,
            "created_at": time.monotonic(),
            "status": "waiting",
            "result": None,
        }
        return {
            "session_id": session_id,
            "qr_image_url": f"/api/v1/mi-accounts/qr/{session_id}/image",
            "login_url": data.get("loginUrl", ""),
            "expires_in": timeout,
        }

    def get_session(self, session_id: str, user_id: int) -> Optional[dict]:
        """取会话（校验归属），不存在或过期返回 None。"""
        session = self._sessions.get(session_id)
        if not session or session["user_id"] != user_id:
            return None
        if time.monotonic() - session["created_at"] > session["timeout"]:
            if session["status"] not in ("confirmed",):
                session["status"] = "expired"
        return session

    async def get_qr_image(self, session_id: str, user_id: int) -> Optional[bytes]:
        """下载二维码 PNG（代理小米的图片地址）。"""
        session = self.get_session(session_id, user_id)
        if not session:
            return None
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(session["qr_url"])
            resp.raise_for_status()
            return resp.content

    async def poll_status(self, session_id: str, user_id: int) -> Dict:
        """
        轮询扫码状态。

        服务端对小米 lp 地址做一次最长 POLL_TIMEOUT_SECONDS 的等待，
        前端以 2~3 秒间隔调用本接口即可。
        """
        session = self.get_session(session_id, user_id)
        if not session:
            return {"status": "expired", "message": "会话不存在或已过期"}

        if session["status"] == "confirmed":
            return {"status": "confirmed", "message": "登录成功"}

        if session["status"] in ("expired", "error"):
            return {"status": session["status"], "message": "二维码已过期，请重新获取"}

        elapsed = time.monotonic() - session["created_at"]
        if elapsed > session["timeout"]:
            session["status"] = "expired"
            return {"status": "expired", "message": "二维码已过期，请重新获取"}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(POLL_TIMEOUT_SECONDS, connect=10),
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(session["lp_url"])
        except httpx.TimeoutException:
            return {"status": "waiting", "message": "等待扫码"}
        except httpx.HTTPError as e:
            logger.warning(f"小米扫码轮询请求失败: {e}")
            return {"status": "waiting", "message": "网络波动，继续等待"}

        if resp.status_code != 200:
            return {"status": "waiting", "message": "等待扫码"}

        try:
            import json

            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else json.loads(
                _strip_prefix(resp.text)
            )
        except (ValueError, json.JSONDecodeError):
            return {"status": "waiting", "message": "等待扫码"}

        user_id_mi = data.get("userId")
        pass_token = data.get("passToken")
        if not user_id_mi or not pass_token:
            session["status"] = "error"
            logger.error(f"小米扫码轮询返回缺少凭据字段: {list(data.keys())}")
            return {"status": "error", "message": "登录数据异常，请重试"}

        session["status"] = "confirmed"
        session["result"] = {
            "mi_user_id": str(user_id_mi),
            "mi_pass_token": pass_token,
            "c_user_id": data.get("cUserId"),
            "display_name": session.get("display_name"),
        }
        logger.info(f"小米扫码登录成功: userId={user_id_mi}")
        return {"status": "confirmed", "message": "登录成功"}

    def consume_result(self, session_id: str, user_id: int) -> Optional[dict]:
        """取出并清除扫码结果（只允许消费一次，防止 token 泄露）。"""
        session = self.get_session(session_id, user_id)
        if not session or session["status"] != "confirmed":
            return None
        result = session["result"]
        session["result"] = None
        self._sessions.pop(session_id, None)
        return result


# 全局单例
mi_qr_login_service = MiQrLoginService()
