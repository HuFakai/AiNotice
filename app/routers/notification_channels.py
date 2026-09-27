# -*- coding: utf-8 -*-
"""
通知渠道管理 API 接口
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.schemas.notification_channel import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationChannelResponse,
)
from app.services.notification_service import notification_service
from app.schemas.notification import NotificationSendRequest, NotificationSendResponse

router = APIRouter(prefix="/channels", tags=["通知渠道管理"])


@router.get("", response_model=List[NotificationChannelResponse], summary="获取通道列表")
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的所有通知渠道列表（敏感配置已脱敏，解密失败的渠道带 config_error）"""
    try:
        channels = await notification_service.get_user_channels(db, current_user.id)
        # 转换为响应格式并脱敏配置
        return [NotificationChannelResponse.from_orm_masked(c) for c in channels]
    except Exception:
        logger.exception("获取通道列表异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取通道列表失败，请稍后重试"
        )


@router.post("", response_model=NotificationChannelResponse, summary="创建通知通道")
async def create_channel(
    req: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """为当前用户创建新的通知渠道"""
    try:
        channel = await notification_service.create_channel(
            db=db,
            user_id=current_user.id,
            name=req.name,
            channel_type=req.channel_type,
            config=req.config,
            is_active=req.is_active
        )
        return NotificationChannelResponse.from_orm_masked(channel)
    except Exception:
        logger.exception("创建通知通道异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建通知通道失败，请稍后重试"
        )


@router.get("/{channel_id}", response_model=NotificationChannelResponse, summary="获取通道详情")
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    根据通道ID获取特定渠道详情。

    配置解密失败时不会 500：config 返回空对象并附带 config_error 提示。
    """
    channel = await notification_service.get_channel_by_id(db, current_user.id, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
    return NotificationChannelResponse.from_orm_masked(channel)


@router.put("/{channel_id}", response_model=NotificationChannelResponse, summary="更新通知通道")
async def update_channel(
    channel_id: int,
    req: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    更新已存在的通知渠道。

    config 为增量合并：值为 null、空字符串或 "******" 的字段保留原值；
    值为 "__DELETE__" 的字段会被删除。
    """
    try:
        channel = await notification_service.update_channel(
            db=db,
            user_id=current_user.id,
            channel_id=channel_id,
            name=req.name,
            channel_type=req.channel_type,
            config=req.config,
            is_active=req.is_active
        )
        if not channel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
        return NotificationChannelResponse.from_orm_masked(channel)
    except HTTPException:
        raise
    except ValueError as e:
        # 配置解密失败等明确的业务错误：返回可读提示
        logger.warning(f"更新通知通道校验失败 (ID={channel_id}): {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("更新通知通道异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新通知通道失败，请稍后重试"
        )


@router.delete("/{channel_id}", summary="删除通知通道")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除指定的通知渠道"""
    try:
        success = await notification_service.delete_channel(db, current_user.id, channel_id)
    except Exception:
        logger.exception("删除通知通道异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="删除通知通道失败，请稍后重试"
        )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
    return {"success": True, "message": "通知通道删除成功"}


@router.post("/{channel_id}/test", response_model=NotificationSendResponse, summary="测试通知通道")
async def test_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    向指定通道同步发送测试消息以验证配置是否正确。

    该接口 wait=True 真实执行发送，返回体 {success, message, log_id} 反映真实成败，
    并写入 NotificationLog 便于回溯。
    """
    # 构造一条测试发送请求
    test_req = NotificationSendRequest(
        channel_id=channel_id,
        title="爱通知测试消息",
        content="这只是一条用来验证您通知通道配置是否正确的测试消息！如果您收到这条消息，说明您的配置已成功生效。",
    )
    try:
        return await notification_service.send_notification(db, current_user.id, test_req, wait=True)
    except ValueError as e:
        logger.warning(f"测试通知通道校验失败 (ID={channel_id}): {e}")
        return NotificationSendResponse(success=False, message=str(e))
    except Exception:
        logger.exception("测试通知通道异常")
        return NotificationSendResponse(success=False, message="发送测试通知失败，请稍后重试")