# -*- coding: utf-8 -*-
"""
用户管理API路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """获取用户统计信息（聚合查询，不加载关系集合）"""
    try:
        from datetime import datetime, timezone

        from app.models.api_call_log import ApiCallLog
        from app.models.device import Device
        from app.models.api_key import ApiKey
        from app.models.speak_task import SpeakTask
        from sqlalchemy import func, select

        async def _scalar(stmt) -> int:
            result = await db.execute(stmt)
            return result.scalar() or 0

        total_calls = await _scalar(select(func.count(ApiCallLog.id)).where(ApiCallLog.user_id == current_user.id))
        device_count = await _scalar(select(func.count(Device.id)).where(Device.user_id == current_user.id))
        online_devices = await _scalar(
            select(func.count(Device.id)).where(Device.user_id == current_user.id, Device.is_online == True)  # noqa: E712
        )
        api_keys_count = await _scalar(select(func.count(ApiKey.id)).where(ApiKey.user_id == current_user.id))
        active_api_keys = await _scalar(
            select(func.count(ApiKey.id)).where(ApiKey.user_id == current_user.id, ApiKey.is_active == True)  # noqa: E712
        )

        # 今日/本月播放任务数（UTC 边界，与库内时间语义一致）
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        speak_tasks_today = await _scalar(
            select(func.count(SpeakTask.id)).where(SpeakTask.user_id == current_user.id, SpeakTask.created_at >= day_start)
        )
        speak_tasks_month = await _scalar(
            select(func.count(SpeakTask.id)).where(SpeakTask.user_id == current_user.id, SpeakTask.created_at >= month_start)
        )

        return UserStatsResponse(
            device_count=device_count,
            online_devices=online_devices,
            api_keys_count=api_keys_count,
            active_api_keys=active_api_keys,
            speak_tasks_today=speak_tasks_today,
            speak_tasks_month=speak_tasks_month,
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

# ---------------------------------------------------------------------------
# 日志生命周期管理（个人中心）
# ---------------------------------------------------------------------------

LOG_RETENTION_TABLES = {
    "api_call_logs": "API 调用日志",
    "speak_tasks": "播放任务记录",
    "user_activities": "用户活动记录",
    "notification_logs": "通知日志",
}


async def _table_count(db: AsyncSession, table: str) -> int:
    from sqlalchemy import text as _text

    try:
        return (await db.execute(_text(f"SELECT COUNT(*) FROM {table}"))).scalar() or 0
    except Exception:
        return 0


@router.get("/log-settings", summary="获取日志生命周期设置", description="返回各日志表的保留天数（生效值）、当前行数与最近清理时间")
async def get_log_settings(db: DatabaseSession, current_user: User = Depends(get_current_active_user)):
    from app.models.system_setting import SystemSetting
    from app.services.cleanup_service import DatabaseCleanupService

    async with DatabaseCleanupService() as svc:
        retentions = await svc.resolve_retentions(db)

    counts = {t: await _table_count(db, t) for t in LOG_RETENTION_TABLES}
    last_row = (await db.execute(
        select(SystemSetting).where(SystemSetting.setting_key == "last_cleanup_at")
    )).scalar_one_or_none()

    return {
        "success": True,
        "retentions": retentions,
        "counts": counts,
        "last_cleanup_at": last_row.setting_value if last_row else None,
    }


@router.put("/log-settings", summary="更新日志保留天数", description="整体更新各日志表的保留天数（1-3650 天），次日定时清理生效，也可立即手动清理")
async def update_log_settings(
    request: Request,
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
):
    from app.models.system_setting import SystemSetting, SettingType
    from app.services.cleanup_service import DatabaseCleanupService

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须是 JSON")

    table_to_key = {t: cfg[0] for t, cfg in DatabaseCleanupService.RETENTION_KEYS.items()}
    updates = {}
    for table, key in table_to_key.items():
        if table not in payload:
            continue
        try:
            days = int(payload[table])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{table} 的保留天数必须是整数")
        if not 1 <= days <= 3650:
            raise HTTPException(status_code=400, detail=f"{table} 的保留天数需在 1-3650 之间")
        updates[key] = days

    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的保留天数")

    for key, days in updates.items():
        row = (await db.execute(select(SystemSetting).where(SystemSetting.setting_key == key))).scalar_one_or_none()
        if row:
            row.setting_value = str(days)
        else:
            db.add(SystemSetting(
                setting_key=key, setting_value=str(days),
                setting_type=SettingType.INT, description=f"日志保留天数（{key}）", is_public=False,
            ))
    await db.commit()

    async with DatabaseCleanupService() as svc:
        retentions = await svc.resolve_retentions(db)
    return {"success": True, "message": "日志保留天数已更新", "retentions": retentions}


@router.post("/log-settings/cleanup", summary="立即执行日志清理", description="按当前保留天数立即清理各日志表，返回逐表删除统计")
async def run_log_cleanup(db: DatabaseSession, current_user: User = Depends(get_current_active_user)):
    from app.services.cleanup_service import DatabaseCleanupService

    async with DatabaseCleanupService() as svc:
        summary = await svc.cleanup_all_tables()
    return {"success": True, "message": f"清理完成：共删除 {summary.get('total_records_deleted', 0)} 条记录", "summary": summary}
