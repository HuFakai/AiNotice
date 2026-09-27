# -*- coding: utf-8 -*-
"""
统一消息推送 API 接口
"""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_user_and_api_key_info
from app.models.user import User
from app.schemas.notification import NotificationSendRequest, NotificationSendResponse
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notify", tags=["消息推送"])


@router.post("/send", response_model=NotificationSendResponse, summary="统一推送消息")
async def send_notification(
    req: NotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    user_and_api: tuple = Depends(get_user_and_api_key_info),
):
    """
    统一推送接口，支持小爱音箱、邮件、钉钉、飞书、企业微信和 Webhook。

    可以使用已保存的通道（指定 `channel_id`），也可以直接使用临时配置。

    **双重认证支持**:
    - ✅ **JWT Token**: 前端控制台调用
    - ✅ **API Key**: 脚本或自动化外部调用（Authorization: Bearer xai_sk_...）
    """
    current_user, api_key_id = user_and_api
    try:
        logger.info(f"用户 {current_user.username} 触发统一消息推送 (类型: {req.channel_type or '指定通道ID'})")
        return await notification_service.send_notification(db, current_user.id, req)
    except Exception as e:
        logger.error(f"统一推送失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"发送失败: {str(e)}"
        )


@router.post("", response_model=NotificationSendResponse, summary="统一推送消息 (别名)")
async def send_notification_alias(
    req: NotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    user_and_api: tuple = Depends(get_user_and_api_key_info),
):
    """统一推送接口别名"""
    return await send_notification(req, db, user_and_api)
