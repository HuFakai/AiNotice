# -*- coding: utf-8 -*-
"""
统一消息推送 API 接口

认证方式：
- JWT Token：前端控制台调用，直接放行；
- API Key（xai_sk_ 前缀）：必须持有 send_notify 权限位，否则 403。
"""

from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_auth_service,
    get_api_key_service,
    security,
)
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.notification import NotificationSendRequest, NotificationSendResponse
from app.services.auth_service import AuthService
from app.services.api_key_service import ApiKeyService
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notify", tags=["消息推送"])

# API Key 调用统一推送所需的权限位
REQUIRED_NOTIFY_PERMISSION = "send_notify"


async def get_notify_caller(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> Tuple[User, Optional["ApiKey"]]:
    """
    本地认证 helper：同时支持 JWT 与 API Key 两种认证方式。

    返回 (用户对象, API Key 对象或 None)，端点据此读取密钥绑定的通知渠道。

    - JWT：验证通过后放行，API Key 对象为 None；
    - API Key：验证 key 有效外，还要求 key 具备 send_notify 权限，否则 403。

    失败时的状态码与提示文案与既有依赖保持一致，保证响应兼容。
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要认证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # API Key 认证（xai_sk_ 前缀）
    if token.startswith("xai_sk_"):
        try:
            is_valid, user, api_key_obj = await api_key_service.verify_api_key(token)
        except Exception:
            logger.exception("统一推送：API Key 认证异常")
            is_valid, user, api_key_obj = False, None, None

        if is_valid and user and api_key_obj:
            permissions = api_key_obj.permissions or {}
            if not permissions.get(REQUIRED_NOTIFY_PERMISSION, False):
                logger.warning(
                    f"API Key 缺少 {REQUIRED_NOTIFY_PERMISSION} 权限，拒绝推送 "
                    f"(key_id={api_key_obj.id}, user={user.username})"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API 密钥缺少 {REQUIRED_NOTIFY_PERMISSION} 权限",
                )
            logger.debug(f"统一推送 API Key 认证成功: 用户={user.username}, key_id={api_key_obj.id}")
            return user, api_key_obj

    # JWT 认证（API Key 无效时保持与旧行为一致，继续尝试 JWT）
    try:
        is_valid, user = await auth_service.verify_token(token)
        if is_valid and user:
            logger.debug(f"统一推送 JWT 认证成功: 用户={user.username}")
            return user, None
    except Exception:
        logger.exception("统一推送：JWT 认证异常")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/send", response_model=NotificationSendResponse, summary="统一推送消息")
async def send_notification(
    req: NotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    caller: Tuple[User, Optional[ApiKey]] = Depends(get_notify_caller),
):
    """
    统一推送接口，支持小爱音箱、邮件、钉钉、飞书、企业微信和 Webhook。

    渠道解析优先级：
    1. 请求显式指定 `channel_id` → 用该渠道（覆盖密钥绑定）；
    2. 请求指定 `channel_type` + `config` → 用临时配置；
    3. 两者都没有且使用 **API Key** 认证 → 向密钥绑定的全部启用渠道推送；
    4. JWT 调用必须显式指定渠道。

    **双重认证支持**:
    - ✅ **JWT Token**: 前端控制台调用
    - ✅ **API Key**: 脚本或自动化外部调用（Authorization: Bearer xai_sk_...，需 send_notify 权限）

    **异步语义**: 接口仅完成调度并立即返回 `log_id(s)`，真实发送结果请按 log_id 查询通知日志。
    """
    current_user, api_key_obj = caller
    try:
        logger.info(
            f"用户 {current_user.username} 触发统一消息推送 (类型: {req.channel_type or '指定通道ID' or '绑定渠道'})"
        )
        # API Key：绑定列表可能为空（[]），用于区分"密钥无绑定"与"JWT 调用"（None）
        bound_channel_ids = list(api_key_obj.channel_ids or []) if api_key_obj else None
        return await notification_service.send_notification(
            db, current_user.id, req, bound_channel_ids=bound_channel_ids
        )
    except Exception:
        logger.exception("统一推送失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="发送失败，请稍后重试",
        )


@router.post("", response_model=NotificationSendResponse, summary="统一推送消息 (别名)")
async def send_notification_alias(
    req: NotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    caller: Tuple[User, Optional[ApiKey]] = Depends(get_notify_caller),
):
    """统一推送接口别名"""
    return await send_notification(req, db, caller)