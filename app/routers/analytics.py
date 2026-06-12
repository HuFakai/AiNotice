# -*- coding: utf-8 -*-
"""
API调用统计分析路由
提供API调用记录和统计分析的RESTful接口
"""

from datetime import datetime, date
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import io
import csv
import json

from app.dependencies import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.analytics_service import analytics_service
from app.schemas.analytics import (
    CallLogsQueryParams, AnalyticsQueryParams,
    ApiCallLogResponse, CallLogsListResponse,
    AnalyticsOverviewResponse, EndpointAnalyticsResponse,
    PerformanceAnalyticsResponse, QuotaAnalyticsResponse,
    RealTimeStatsResponse, HealthCheckResponse
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/call-logs", response_model=CallLogsListResponse)
async def get_call_logs(
    params: CallLogsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取API调用记录列表
    
    支持多种筛选条件：
    - 时间范围筛选
    - 端点筛选
    - 状态码筛选
    - API密钥筛选
    - API密钥名称筛选
    - HTTP方法筛选
    - 播报内容关键词筛选
    """
    try:
        logs, pagination = await analytics_service.get_call_logs(
            db, current_user.id, params
        )
        
        # 转换为响应模型
        log_responses = [
            ApiCallLogResponse(
                id=log.id,
                user_id=log.user_id,
                api_key_id=log.api_key_id,
                endpoint=log.endpoint,
                method=log.method,
                status_code=log.status_code,
                response_time_ms=log.response_time_ms,
                request_size=log.request_size,
                response_size=log.response_size,
                user_agent=log.user_agent,
                ip_address=log.ip_address,
                error_message=log.error_message,
                created_at=log.created_at
            )
            for log in logs
        ]
        
        return CallLogsListResponse(
            data=log_responses,
            pagination=pagination
        )
        
    except Exception as e:
        logger.error(f"获取调用记录失败: {e}")
        raise HTTPException(status_code=500, detail="获取调用记录失败")


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    params: AnalyticsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取统计分析概览
    
    包含：
    - 总体统计数据
    - 时间序列趋势
    - 热门端点
    - 错误分布
    """
    try:
        overview_stats, time_series = await analytics_service.get_overview_stats(
            db, current_user.id, params
        )
        
        return AnalyticsOverviewResponse(
            data=overview_stats,
            time_series=time_series
        )
        
    except Exception as e:
        logger.error(f"获取统计概览失败: {e}")
        raise HTTPException(status_code=500, detail="获取统计概览失败")


@router.get("/endpoints", response_model=EndpointAnalyticsResponse)
async def get_endpoint_analytics(
    params: AnalyticsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取端点分析
    
    包含：
    - 各端点调用统计
    - 成功率分析
    - 响应时间分析
    - 数据传输量分析
    """
    try:
        endpoint_stats, time_series = await analytics_service.get_endpoint_analytics(
            db, current_user.id, params
        )
        
        return EndpointAnalyticsResponse(
            data=endpoint_stats,
            time_series=time_series
        )
        
    except Exception as e:
        logger.error(f"获取端点分析失败: {e}")
        raise HTTPException(status_code=500, detail="获取端点分析失败")


@router.get("/performance", response_model=PerformanceAnalyticsResponse)
async def get_performance_analytics(
    params: AnalyticsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取性能分析
    
    包含：
    - 响应时间统计（平均值、P50、P95、P99）
    - QPS统计
    - 性能趋势分析
    """
    try:
        performance_stats, time_series = await analytics_service.get_performance_analytics(
            db, current_user.id, params
        )
        
        return PerformanceAnalyticsResponse(
            data=performance_stats,
            time_series=time_series
        )
        
    except Exception as e:
        logger.error(f"获取性能分析失败: {e}")
        raise HTTPException(status_code=500, detail="获取性能分析失败")


@router.get("/quotas", response_model=QuotaAnalyticsResponse)
async def get_quota_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取配额分析
    
    包含：
    - 各端点配额使用情况
    - 配额剩余量
    - 配额重置时间
    """
    try:
        quota_usage = await analytics_service.get_quota_analytics(
            db, current_user.id
        )
        
        return QuotaAnalyticsResponse(
            data=quota_usage
        )
        
    except Exception as e:
        logger.error(f"获取配额分析失败: {e}")
        raise HTTPException(status_code=500, detail="获取配额分析失败")


@router.get("/real-time", response_model=RealTimeStatsResponse)
async def get_real_time_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取实时统计
    
    包含：
    - 当前QPS
    - 活跃用户数
    - 最近调用记录
    - 系统健康状态
    - 告警信息
    """
    try:
        real_time_stats = await analytics_service.get_real_time_stats(
            db, current_user.id
        )
        
        return RealTimeStatsResponse(
            data=real_time_stats
        )
        
    except Exception as e:
        logger.error(f"获取实时统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取实时统计失败")





@router.get("/speak/call-logs", response_model=CallLogsListResponse)
async def get_speak_call_logs(
    params: CallLogsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取speak接口的调用记录列表
    
    专门针对/api/v1/speak接口的调用记录，包含：
    - 调用时间
    - 被调用设备ID和名称
    - 语音播报内容
    - 任务结束时间
    - 调用IP地址
    - 使用的API密钥
    
    支持筛选条件：
    - 时间范围筛选
    - 状态码筛选
    - API密钥ID筛选
    - API密钥名称筛选
    - 设备ID筛选
    - 播报内容关键词筛选
    """
    try:
        logs, pagination = await analytics_service.get_speak_call_logs(
            db, current_user.id, params
        )
        
        return CallLogsListResponse(
            success=True,
            data=[log.to_dict() for log in logs],
            pagination=pagination,
            message="获取speak接口调用记录成功"
        )
        
    except Exception as e:
        logger.error(f"获取speak接口调用记录失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取speak接口调用记录失败"
        )


@router.get("/speak/analytics")
async def get_speak_analytics(
    params: AnalyticsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取speak接口的详细统计分析
    
    包含：
    - 总体统计概览（调用次数、成功率、平均响应时间等）
    - 设备使用统计
    - 时间序列数据
    - 最近调用记录
    """
    try:
        analytics_data = await analytics_service.get_speak_analytics(
            db, current_user.id, params
        )
        
        return {
            "success": True,
            "data": analytics_data,
            "message": "获取speak接口统计分析成功"
        }
        
    except Exception as e:
        logger.error(f"获取speak接口统计分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取speak接口统计分析失败"
        )


@router.get("/speak/devices")
async def get_speak_devices(
    params: AnalyticsQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取speak接口的设备统计
    
    包含：
    - 各设备的调用统计
    - 设备成功率
    - 设备平均响应时间
    - 最后调用时间
    """
    try:
        device_stats = await analytics_service.get_speak_device_stats(
            db, current_user.id, params
        )
        
        return {
            "success": True,
            "data": {
                "devices": device_stats
            },
            "message": "获取speak设备统计成功"
        }
        
    except Exception as e:
        logger.error(f"获取speak设备统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取speak设备统计失败"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    健康检查接口
    
    检查：
    - 数据库连接状态
    - 服务运行状态
    """
    try:
        # 简单的数据库连接测试
        await db.execute("SELECT 1")
        
        return HealthCheckResponse(
            status="healthy",
            timestamp=datetime.now(),
            services={
                "database": "healthy",
                "analytics": "healthy"
            }
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            services={
                "database": "unhealthy",
                "analytics": "unhealthy"
            }
        )