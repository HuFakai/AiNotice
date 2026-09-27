# -*- coding: utf-8 -*-
"""
通知渠道管理 API 接口
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
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
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有通知渠道列表"""
    try:
        channels = await notification_service.get_user_channels(db, current_user.id)
        # 转换为响应格式并脱敏配置
        return [NotificationChannelResponse.from_orm_masked(c) for c in channels]
    except Exception as e:
        logger.error(f"获取通道列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取通道列表失败: {str(e)}"
        )


@router.post("", response_model=NotificationChannelResponse, summary="创建通知通道")
async def create_channel(
    req: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    except Exception as e:
        logger.error(f"创建通知通道异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建通知通道失败: {str(e)}"
        )


@router.get("/{channel_id}", response_model=NotificationChannelResponse, summary="获取通道详情")
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据通道ID获取特定渠道详情"""
    channel = await notification_service.get_channel_by_id(db, current_user.id, channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
    return NotificationChannelResponse.from_orm_masked(channel)


@router.put("/{channel_id}", response_model=NotificationChannelResponse, summary="更新通知通道")
async def update_channel(
    channel_id: int,
    req: NotificationChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新已存在的通知渠道"""
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
    except Exception as e:
        logger.error(f"更新通知通道异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新通知通道失败: {str(e)}"
        )


@router.delete("/{channel_id}", summary="删除通知通道")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定的通知渠道"""
    success = await notification_service.delete_channel(db, current_user.id, channel_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知渠道不存在")
    return {"success": True, "message": "通知通道删除成功"}


@router.post("/{channel_id}/test", response_model=NotificationSendResponse, summary="测试通知通道")
async def test_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """向指定通道发送测试消息以验证配置是否正确"""
    # 构造一条测试发送请求
    test_req = NotificationSendRequest(
        channel_id=channel_id,
        title="爱通知测试消息",
        content="这只是一条用来验证您通知通道配置是否正确的测试消息！如果您收到这条消息，说明您的配置已成功生效。",
    )
    try:
        return await notification_service.send_notification(db, current_user.id, test_req)
    except Exception as e:
        logger.error(f"测试通知通道异常: {e}")
        return NotificationSendResponse(success=False, message=f"发送测试通知失败: {str(e)}")
