# -*- coding: utf-8 -*-
"""
用户管理API路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from loguru import logger

from app.dependencies import get_current_active_user, get_client_ip, get_user_agent, DatabaseSession
from app.services.user_service import UserService
from app.schemas.user import (
    UserProfile,
    UpdateProfileRequest,
    ChangePasswordRequest,
    UserActivityResponse,
    UserStatsResponse,
    LoginHistoryResponse,
)
from app.schemas.auth import SuccessResponse
from app.models.user import User


router = APIRouter(prefix="/user", tags=["用户管理"])


@router.get("/profile", response_model=UserProfile, summary="获取用户资料", description="获取当前用户的详细资料信息")
async def get_user_profile(current_user: User = Depends(get_current_active_user)):
    """获取用户资料"""
    return UserProfile.from_orm(current_user)


@router.put("/profile", response_model=SuccessResponse, summary="更新用户资料", description="更新当前用户的资料信息")
async def update_user_profile(
    request: UpdateProfileRequest,
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """更新用户资料"""
    try:
        user_service = UserService(db)

        success = await user_service.update_user_profile(
            user_id=current_user.id, display_name=request.display_name, client_ip=client_ip, user_agent=user_agent
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="更新资料失败")

        return SuccessResponse(message="资料更新成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户资料API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/change-password", response_model=SuccessResponse, summary="修改密码", description="修改当前用户的登录密码")
async def change_password(
    request: ChangePasswordRequest,
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """修改密码"""
    try:
        user_service = UserService(db)

        success = await user_service.change_password(
            user_id=current_user.id,
            old_password=request.old_password,
            new_password=request.new_password,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码修改失败，请检查旧密码是否正确")

        return SuccessResponse(message="密码修改成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改密码API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get("/activities", response_model=List[UserActivityResponse], summary="获取用户活动记录", description="获取当前用户的活动记录列表")
async def get_user_activities(
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(50, ge=1, le=100, description="限制数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取用户活动记录"""
    try:
        user_service = UserService(db)

        activities = await user_service.get_user_activities(user_id=current_user.id, limit=limit, offset=offset)

        return [UserActivityResponse.from_orm(activity) for activity in activities]

    except Exception as e:
        logger.error(f"获取用户活动API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get("/stats", response_model=UserStatsResponse, summary="获取用户统计信息", description="获取当前用户的统计数据")
async def get_user_stats(db: DatabaseSession, current_user: User = Depends(get_current_active_user)):
    """获取用户统计信息"""
    try:
        # 这里需要实现统计逻辑
        # 暂时返回示例数据
        # 查询API调用总次数
        from app.models.api_call_log import ApiCallLog
        from sqlalchemy import func, select
        
        # 使用异步查询
        result = await db.execute(
            select(func.count(ApiCallLog.id)).where(
                ApiCallLog.user_id == current_user.id
            )
        )
        total_calls = result.scalar() or 0
        
        return UserStatsResponse(
            device_count=len(current_user.devices) if current_user.devices else 0,
            online_devices=sum(1 for device in (current_user.devices or []) if device.is_online),
            api_keys_count=len(current_user.api_keys) if current_user.api_keys else 0,
            active_api_keys=sum(1 for key in (current_user.api_keys or []) if key.is_active),
            speak_tasks_today=0,  # 需要从数据库查询
            speak_tasks_month=0,  # 需要从数据库查询
            total_api_calls=total_calls,
        )

    except Exception as e:
        logger.error(f"获取用户统计API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get("/login-history", response_model=List[UserActivityResponse], summary="获取用户活动记录", description="获取当前用户的所有活动记录")
async def get_login_history(
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(20, ge=1, le=100, description="限制数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取用户活动记录"""
    try:
        # 查询用户的所有活动记录
        from app.models.user_activity import UserActivity
        from sqlalchemy import select
        
        result = await db.execute(
            select(UserActivity).where(
                UserActivity.user_id == current_user.id
            ).order_by(UserActivity.created_at.desc()).offset(offset).limit(limit)
        )
        activities = result.scalars().all()
        
        # 转换为用户活动记录格式
        activity_list = []
        for activity in activities:
            activity_list.append(UserActivityResponse(
                id=activity.id,
                activity_type=activity.activity_type,
                activity_description=activity.activity_description,
                resource_type=activity.resource_type,
                resource_id=activity.resource_id,
                client_ip=activity.client_ip,
                created_at=activity.created_at
            ))
        
        return activity_list
        
    except Exception as e:
        logger.error(f"获取用户活动记录API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")
