# -*- coding: utf-8 -*-
"""
API 调用日志中间件

记录所有已认证的 /api/v1 请求（真实端点、方法、状态码、耗时、来源 IP、
调用身份），用于统计分析页与调用日志展示。

设计要点：
- 纯 ASGI 中间件（非 BaseHTTPMiddleware），不缓冲响应体、不阻塞流式响应
- 写库在后台任务中用独立会话完成，不拖慢请求本身
- 仅记录能归属到用户的请求（认证依赖会把身份写入 request.state），
  匿名请求（登录/健康检查等）不记录
- speak_service 不再手写调用日志，避免端点错误与重复记录
"""

import asyncio
import time
from typing import Any, Dict, Set

from loguru import logger

from app.config import get_settings

# 持有后台写库任务引用，防止被 GC
_bg_tasks: Set[asyncio.Task] = set()

# 不记录的路径前缀/精确路径
SKIP_PATHS = {
    "/api/v1/health",
    "/api/v1/analytics/health",
}


def _client_ip_from_scope(scope) -> str:
    """与 dependencies.get_client_ip 同策略，但直接读 ASGI scope（避免循环依赖）"""
    from ipaddress import ip_address

    headers = dict((k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope.get("headers", []))

    if get_settings().trust_proxy_headers:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
            try:
                ip_address(ip)
                return ip
            except ValueError:
                pass
        real_ip = headers.get("x-real-ip")
        if real_ip:
            try:
                ip_address(real_ip)
                return real_ip
            except ValueError:
                pass

    client = scope.get("client")
    return client[0] if client else "unknown"


async def _write_log(entry: Dict[str, Any]) -> None:
    """后台写库（独立会话，失败仅记日志不影响业务）"""
    try:
        from sqlalchemy import insert

        from app.database import AsyncSessionLocal
        from app.models.api_call_log import ApiCallLog

        async with AsyncSessionLocal() as session:
            await session.execute(insert(ApiCallLog).values(**entry))
            await session.commit()
    except Exception as e:
        logger.warning(f"写入 API 调用日志失败（忽略）: {type(e).__name__}: {e}")


class ApiCallLogMiddleware:
    """记录已认证 /api/v1 请求的调用日志"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if not path.startswith("/api/v1") or path in SKIP_PATHS:
            return await self.app(scope, receive, send)

        state = scope.setdefault("state", {})
        start = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            user_id = state.get("auth_user_id")
            # 仅记录能归属到用户的请求
            if user_id is not None:
                query = scope.get("query_string", b"").decode("latin-1")
                entry = {
                    "user_id": user_id,
                    "api_key_id": state.get("auth_api_key_id"),
                    "endpoint": path,
                    "method": scope.get("method", "GET"),
                    "request_ip": _client_ip_from_scope(scope),
                    "user_agent": dict((k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope.get("headers", [])).get("user-agent"),
                    "status_code": status_holder["code"],
                    "response_time_ms": duration_ms,
                    "request_params": {"query": query} if query else None,
                }
                task = asyncio.create_task(_write_log(entry))
                _bg_tasks.add(task)
                task.add_done_callback(_bg_tasks.discard)
