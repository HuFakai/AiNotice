# -*- coding: utf-8 -*-
"""
API调用统计分析服务
提供API调用记录的统计分析功能
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text, case
from sqlalchemy.orm import selectinload
from loguru import logger
import asyncio
from collections import defaultdict

from app.models.api_call_log import ApiCallLog
from app.database import BJ_TZ
from app.models.api_call_log import ApiUsageStats, ApiQuota
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.analytics import (
    PeriodType, GroupByType, CallLogsQueryParams, AnalyticsQueryParams,
    TimeSeriesDataPoint, EndpointStats, ErrorDistribution, OverviewStats,
    PerformanceStats, QuotaUsage, RealTimeStats
)


class AnalyticsService:
    """统计分析服务"""

    async def get_call_logs(
        self,
        session: AsyncSession,
        user_id: int,
        params: CallLogsQueryParams
    ) -> Tuple[List[ApiCallLog], Dict[str, Any]]:
        """获取API调用记录列表"""
        try:
            # 构建查询条件
            conditions = [ApiCallLog.user_id == user_id]
            
            if params.start_date:
                start_dt = datetime.strptime(params.start_date, '%Y-%m-%d')
                conditions.append(ApiCallLog.created_at >= start_dt)
            
            if params.end_date:
                end_dt = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
                conditions.append(ApiCallLog.created_at < end_dt)
            
            if params.endpoint:
                conditions.append(ApiCallLog.endpoint.ilike(f"%{params.endpoint}%"))
            
            if params.status_code:
                conditions.append(ApiCallLog.status_code == params.status_code)
            
            if params.api_key_id:
                conditions.append(ApiCallLog.api_key_id == params.api_key_id)
            
            if params.api_key_name:
                # 通过关联查询API密钥名称
                conditions.append(ApiCallLog.api_key.has(ApiKey.key_name.ilike(f"%{params.api_key_name}%")))
            
            if params.method:
                conditions.append(ApiCallLog.method == params.method.upper())
            
            if params.speak_text:
                conditions.append(ApiCallLog.speak_text.ilike(f"%{params.speak_text}%"))
            
            # 计算总数
            count_stmt = select(func.count(ApiCallLog.id)).where(and_(*conditions))
            total_result = await session.execute(count_stmt)
            total = total_result.scalar()
            
            # 分页查询，包含API密钥关联
            offset = (params.page - 1) * params.limit
            stmt = (
                select(ApiCallLog)
                .options(selectinload(ApiCallLog.api_key))
                .where(and_(*conditions))
                .order_by(desc(ApiCallLog.created_at))
                .offset(offset)
                .limit(params.limit)
            )
            
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
            # 分页信息
            pagination = {
                "page": params.page,
                "limit": params.limit,
                "total": total,
                "pages": (total + params.limit - 1) // params.limit,
                "has_next": params.page * params.limit < total,
                "has_prev": params.page > 1
            }
            
            return list(logs), pagination
            
        except Exception as e:
            logger.error(f"获取调用记录失败: {e}")
            raise

    async def get_overview_stats(
        self,
        session: AsyncSession,
        user_id: int,
        params: AnalyticsQueryParams
    ) -> Tuple[OverviewStats, List[TimeSeriesDataPoint]]:
        """获取统计概览"""
        try:
            # 计算时间范围
            if params.start_date and params.end_date:
                # 自定义日期范围
                start_time = datetime.strptime(params.start_date, '%Y-%m-%d')
                end_time = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                # 使用预设时间周期，以当前日期的结束时间为结束时间点
                now = datetime.now(BJ_TZ)
                # 对于按天分组的周期，使用当天的结束时间
                if params.period in [PeriodType.DAY_7, PeriodType.DAY_30, PeriodType.DAY_90]:
                    end_time = datetime.combine(now.date(), datetime.max.time(), tzinfo=BJ_TZ)
                elif params.period == PeriodType.HOUR_24:
                    # 24小时数据使用当前时间作为结束时间
                    end_time = now
                else:
                    end_time = now
                start_time = self._calculate_start_time(end_time, params.period)
            
            # 基础查询条件
            base_conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.created_at >= start_time,
                ApiCallLog.created_at < end_time
            ]
            
            if params.endpoint:
                base_conditions.append(ApiCallLog.endpoint == params.endpoint)
            
            # 获取总体统计
            overview_stats = await self._get_overview_statistics(session, base_conditions)
            
            # 根据时间范围自动选择分组方式
            time_diff = end_time - start_time
            if time_diff.total_seconds() <= 24 * 3600:  # 24小时内按小时分组
                group_by = GroupByType.HOUR
            else:  # 超过24小时按天分组
                group_by = GroupByType.DAY
            
            # 获取时间序列数据
            time_series = await self._get_time_series_data(
                session, base_conditions, group_by, start_time, end_time
            )
            
            return overview_stats, time_series
            
        except Exception as e:
            logger.error(f"获取统计概览失败: {e}")
            raise

    async def get_endpoint_analytics(
        self,
        session: AsyncSession,
        user_id: int,
        params: AnalyticsQueryParams
    ) -> Tuple[List[EndpointStats], List[TimeSeriesDataPoint]]:
        """获取端点分析"""
        try:
            # 计算时间范围
            if params.start_date and params.end_date:
                # 自定义日期范围
                start_time = datetime.strptime(params.start_date, '%Y-%m-%d')
                end_time = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                # 使用预设时间周期，以当前日期的结束时间为结束时间点
                now = datetime.now(BJ_TZ)
                # 对于按天分组的周期，使用当天的结束时间
                if params.period in [PeriodType.DAY_7, PeriodType.DAY_30, PeriodType.DAY_90]:
                    end_time = datetime.combine(now.date(), datetime.max.time(), tzinfo=BJ_TZ)
                elif params.period == PeriodType.HOUR_24:
                    # 24小时数据：使用当前小时的59分59秒作为结束时间，确保包含完整的当前小时数据
                    end_time = now.replace(minute=59, second=59, microsecond=999999)
                else:
                    end_time = now
                start_time = self._calculate_start_time(end_time, params.period)
            
            # 按端点分组统计
            stmt = (
                select(
                    ApiCallLog.endpoint,
                    func.count(ApiCallLog.id).label('total_calls'),
                    func.sum(
                        case((
                            and_(ApiCallLog.status_code >= 200, ApiCallLog.status_code < 300), 1
                        ), else_=0)
                    ).label('success_calls'),
                    func.sum(
                        case((ApiCallLog.status_code >= 400, 1), else_=0)
                    ).label('error_calls'),
                    func.avg(ApiCallLog.response_time_ms).label('avg_response_time'),
                    func.sum(ApiCallLog.request_size).label('total_request_size'),
                    func.sum(ApiCallLog.response_size).label('total_response_size')
                )
                .where(
                    ApiCallLog.user_id == user_id,
                    ApiCallLog.created_at >= start_time,
                    ApiCallLog.created_at < end_time
                )
                .group_by(ApiCallLog.endpoint)
                .order_by(desc('total_calls'))
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            endpoint_stats = []
            for row in rows:
                success_rate = (row.success_calls / row.total_calls * 100) if row.total_calls > 0 else 0
                endpoint_stats.append(EndpointStats(
                    endpoint=row.endpoint,
                    total_calls=row.total_calls,
                    success_calls=row.success_calls,
                    error_calls=row.error_calls,
                    success_rate=round(success_rate, 2),
                    avg_response_time=round(float(row.avg_response_time or 0), 2),
                    total_request_size=row.total_request_size or 0,
                    total_response_size=row.total_response_size or 0
                ))
            
            # 获取时间序列数据
            base_conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.created_at >= start_time,
                ApiCallLog.created_at < end_time
            ]
            
            time_series = await self._get_time_series_data(
                session, base_conditions, params.group_by, start_time, end_time
            )
            
            return endpoint_stats, time_series
            
        except Exception as e:
            logger.error(f"获取端点分析失败: {e}")
            raise

    async def get_performance_analytics(
        self,
        session: AsyncSession,
        user_id: int,
        params: AnalyticsQueryParams
    ) -> Tuple[List[PerformanceStats], List[TimeSeriesDataPoint]]:
        """获取性能分析"""
        try:
            # 计算时间范围
            if params.start_date and params.end_date:
                # 自定义日期范围
                start_time = datetime.strptime(params.start_date, '%Y-%m-%d')
                end_time = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                # 使用预设时间周期，以当前日期的结束时间为结束时间点
                now = datetime.now(BJ_TZ)
                # 对于按天分组的周期，使用当天的结束时间
                if params.period in [PeriodType.DAY_7, PeriodType.DAY_30, PeriodType.DAY_90]:
                    end_time = datetime.combine(now.date(), datetime.max.time(), tzinfo=BJ_TZ)
                elif params.period == PeriodType.HOUR_24:
                    # 24小时数据：使用当前时间的59分59秒作为结束时间，确保包含最新记录
                    end_time = now.replace(minute=59, second=59, microsecond=999999)
                else:
                    end_time = now
                start_time = self._calculate_start_time(end_time, params.period)
            
            # 构建查询条件
            conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.created_at >= start_time,
                ApiCallLog.created_at < end_time
            ]
            
            if params.endpoint:
                conditions.append(ApiCallLog.endpoint == params.endpoint)
            
            # 按端点分组的性能统计
            # percentile_cont 仅 PostgreSQL 支持；SQLite/MySQL 降级占位避免报错
            from app.database import engine as _engine, BJ_TZ
            _use_pct = _engine.dialect.name in ('postgresql', 'postgres')
            if _use_pct:
                _p50 = func.percentile_cont(0.5).within_group(ApiCallLog.response_time_ms)
                _p95 = func.percentile_cont(0.95).within_group(ApiCallLog.response_time_ms)
                _p99 = func.percentile_cont(0.99).within_group(ApiCallLog.response_time_ms)
            else:
                _p50 = func.avg(ApiCallLog.response_time_ms)
                _p95 = func.max(ApiCallLog.response_time_ms)
                _p99 = func.max(ApiCallLog.response_time_ms)
            stmt = (
                select(
                    ApiCallLog.endpoint,
                    func.avg(ApiCallLog.response_time_ms).label('avg_response_time'),
                    _p50.label('p50_response_time'),
                    _p95.label('p95_response_time'),
                    _p99.label('p99_response_time'),
                    func.min(ApiCallLog.response_time_ms).label('min_response_time'),
                    func.max(ApiCallLog.response_time_ms).label('max_response_time'),
                    func.count(ApiCallLog.id).label('total_calls')
                )
                .where(and_(*conditions))
                .group_by(ApiCallLog.endpoint)
                .order_by(desc('avg_response_time'))
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            # 计算时间跨度（秒）
            time_span_seconds = (end_time - start_time).total_seconds()
            
            performance_stats = []
            for row in rows:
                qps = row.total_calls / time_span_seconds if time_span_seconds > 0 else 0
                performance_stats.append(PerformanceStats(
                    endpoint=row.endpoint,
                    avg_response_time=round(float(row.avg_response_time or 0), 2),
                    p50_response_time=round(float(row.p50_response_time or 0), 2),
                    p95_response_time=round(float(row.p95_response_time or 0), 2),
                    p99_response_time=round(float(row.p99_response_time or 0), 2),
                    min_response_time=row.min_response_time or 0,
                    max_response_time=row.max_response_time or 0,
                    total_calls=row.total_calls,
                    qps=round(qps, 2)
                ))
            
            # 根据时间范围自动选择分组方式
            time_diff = end_time - start_time
            if time_diff.total_seconds() <= 24 * 3600:  # 24小时内按小时分组
                group_by = GroupByType.HOUR
            else:  # 超过24小时按天分组
                group_by = GroupByType.DAY
            
            # 获取时间序列数据
            time_series = await self._get_time_series_data(
                session, conditions, group_by, start_time, end_time
            )
            
            return performance_stats, time_series
            
        except Exception as e:
            logger.error(f"获取性能分析失败: {e}")
            raise

    async def get_quota_analytics(
        self,
        session: AsyncSession,
        user_id: int
    ) -> List[QuotaUsage]:
        """获取配额分析"""
        try:
            stmt = (
                select(ApiQuota)
                .where(ApiQuota.user_id == user_id)
                .order_by(ApiQuota.endpoint, ApiQuota.quota_type)
            )
            
            result = await session.execute(stmt)
            quotas = result.scalars().all()
            
            quota_usage = []
            for quota in quotas:
                quota_usage.append(QuotaUsage(
                    id=quota.id,
                    endpoint=quota.endpoint,
                    quota_type=quota.quota_type,
                    quota_limit=quota.quota_limit,
                    quota_used=quota.quota_used,
                    quota_remaining=quota.quota_remaining,
                    usage_percentage=quota.usage_percentage,
                    is_exceeded=quota.is_exceeded,
                    reset_date=quota.reset_date
                ))
            
            return quota_usage
            
        except Exception as e:
            logger.error(f"获取配额分析失败: {e}")
            raise

    async def get_real_time_stats(
        self,
        session: AsyncSession,
        user_id: int
    ) -> RealTimeStats:
        """获取实时统计"""
        try:
            # 最近1小时的数据
            one_hour_ago = datetime.now(BJ_TZ) - timedelta(hours=1)
            
            # 计算当前QPS（最近5分钟）
            five_minutes_ago = datetime.now(BJ_TZ) - timedelta(minutes=5)
            qps_stmt = (
                select(func.count(ApiCallLog.id))
                .where(
                    ApiCallLog.user_id == user_id,
                    ApiCallLog.created_at >= five_minutes_ago
                )
            )
            qps_result = await session.execute(qps_stmt)
            recent_calls_count = qps_result.scalar() or 0
            current_qps = recent_calls_count / 300  # 5分钟 = 300秒
            
            # 活跃用户数（最近1小时有调用的用户）
            active_users_stmt = (
                select(func.count(func.distinct(ApiCallLog.user_id)))
                .where(ApiCallLog.created_at >= one_hour_ago)
            )
            active_users_result = await session.execute(active_users_stmt)
            active_users = active_users_result.scalar() or 0
            
            # 最近调用记录
            recent_calls_stmt = (
                select(ApiCallLog)
                .where(ApiCallLog.user_id == user_id)
                .order_by(desc(ApiCallLog.created_at))
                .limit(10)
            )
            recent_calls_result = await session.execute(recent_calls_stmt)
            recent_calls = list(recent_calls_result.scalars().all())
            
            # 系统健康状态
            system_health = {
                "database": "healthy",
                "api": "healthy",
                "cache": "healthy"
            }
            
            # 告警信息
            alerts = []
            
            # 检查配额使用情况
            # 注意：usage_percentage 是 Python @property（非数据库列），
            # 因此这里必须用列表达式计算使用率；quota_limit 可能为 0，用 NULLIF 避免除零。
            quota_usage_pct = ApiQuota.quota_used * 100.0 / func.nullif(ApiQuota.quota_limit, 0)
            quota_stmt = (
                select(ApiQuota)
                .where(
                    ApiQuota.user_id == user_id,
                    quota_usage_pct > 80
                )
            )
            quota_result = await session.execute(quota_stmt)
            high_usage_quotas = quota_result.scalars().all()
            
            for quota in high_usage_quotas:
                alerts.append({
                    "type": "quota_warning",
                    "message": f"端点 {quota.endpoint} 的{quota.quota_type}配额使用率已达 {quota.usage_percentage:.1f}%",
                    "severity": "warning" if quota.usage_percentage < 95 else "critical"
                })
            
            return RealTimeStats(
                current_qps=round(current_qps, 2),
                active_users=active_users,
                recent_calls=[log for log in recent_calls],
                system_health=system_health,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"获取实时统计失败: {e}")
            raise

    async def get_speak_call_logs(
        self,
        session: AsyncSession,
        user_id: int,
        params: CallLogsQueryParams
    ) -> Tuple[List[ApiCallLog], Dict[str, Any]]:
        """获取speak接口的调用记录"""
        try:
            # 基础条件：只查询speak接口
            conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.endpoint == "/api/v1/speak"
            ]
            
            # 时间范围过滤
            if params.start_date:
                start_dt = datetime.strptime(params.start_date, '%Y-%m-%d')
                conditions.append(ApiCallLog.created_at >= start_dt)
            
            if params.end_date:
                end_dt = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
                conditions.append(ApiCallLog.created_at < end_dt)
            
            # 状态码过滤
            if params.status_code:
                conditions.append(ApiCallLog.status_code == params.status_code)
            
            # API密钥过滤
            if params.api_key_id:
                conditions.append(ApiCallLog.api_key_id == params.api_key_id)
            
            # API密钥名称过滤
            if params.api_key_name:
                conditions.append(ApiCallLog.api_key.has(ApiKey.key_name.ilike(f"%{params.api_key_name}%")))
            
            # 设备过滤
            if params.device_id:
                conditions.append(ApiCallLog.device_id == params.device_id)
            
            # 播报内容关键词过滤
            if params.speak_text:
                conditions.append(ApiCallLog.speak_text.ilike(f"%{params.speak_text}%"))
            
            # 计算总数
            count_stmt = select(func.count(ApiCallLog.id)).where(and_(*conditions))
            total_result = await session.execute(count_stmt)
            total = total_result.scalar()
            
            # 分页查询，包含API密钥关联
            offset = (params.page - 1) * params.limit
            stmt = (
                select(ApiCallLog)
                .options(selectinload(ApiCallLog.api_key))
                .where(and_(*conditions))
                .order_by(desc(ApiCallLog.created_at))
                .offset(offset)
                .limit(params.limit)
            )
            
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
            # 分页信息
            pagination = {
                "page": params.page,
                "limit": params.limit,
                "total": total,
                "pages": (total + params.limit - 1) // params.limit,
                "has_next": params.page * params.limit < total,
                "has_prev": params.page > 1
            }
            
            return list(logs), pagination
            
        except Exception as e:
            logger.error(f"获取speak接口调用记录失败: {e}")
            raise

    async def get_speak_analytics(
        self,
        session: AsyncSession,
        user_id: int,
        params: AnalyticsQueryParams
    ) -> Dict[str, Any]:
        """获取speak接口的详细统计分析"""
        try:
            # 计算时间范围
            if params.start_date and params.end_date:
                # 自定义日期范围
                start_time = datetime.strptime(params.start_date, '%Y-%m-%d')
                end_time = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                # 使用预设时间周期，以当前日期的结束时间为结束时间点
                now = datetime.now(BJ_TZ)
                # 对于按天分组的周期，使用当天的结束时间
                if params.period in [PeriodType.DAY_7, PeriodType.DAY_30, PeriodType.DAY_90]:
                    end_time = datetime.combine(now.date(), datetime.max.time(), tzinfo=BJ_TZ)
                else:
                    end_time = now
                start_time = self._calculate_start_time(end_time, params.period)
            
            # 基础条件：只查询speak接口
            conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.endpoint == "/api/v1/speak",
                ApiCallLog.created_at >= start_time,
                ApiCallLog.created_at < end_time
            ]
            
            # 添加设备筛选条件
            if params.device_id:
                conditions.append(ApiCallLog.device_id == params.device_id)
            
            # 获取基础统计
            overview_stats = await self._get_speak_overview_statistics(session, conditions)
            
            # 获取设备使用统计
            device_stats = await self._get_device_usage_stats(session, conditions)
            
            # 根据时间周期自动确定分组方式
            time_diff = end_time - start_time
            if time_diff.days <= 1:  # 24小时内按小时分组
                group_by = GroupByType.HOUR
            else:  # 超过24小时按天分组
                group_by = GroupByType.DAY
            
            # 获取时间序列数据
            time_series = await self._get_time_series_data(
                session, conditions, group_by, start_time, end_time
            )
            
            # 获取最近的调用记录
            recent_calls_stmt = (
                select(ApiCallLog)
                .where(and_(*conditions))
                .order_by(desc(ApiCallLog.created_at))
                .limit(10)
            )
            recent_calls_result = await session.execute(recent_calls_stmt)
            recent_calls = recent_calls_result.scalars().all()
            
            return {
                "overview": overview_stats,
                "device_stats": device_stats,
                "time_series": time_series,
                "recent_calls": list(recent_calls)
            }
            
        except Exception as e:
            logger.error(f"获取speak接口统计分析失败: {e}")
            raise

    async def _get_speak_overview_statistics(
        self,
        session: AsyncSession,
        conditions: List
    ) -> Dict[str, Any]:
        """获取speak接口概览统计"""
        # 基础统计
        basic_stmt = (
            select(
                func.count(ApiCallLog.id).label('total_calls'),
                func.sum(
                    case(
                        (ApiCallLog.status_code == 200, 1),
                        else_=0
                    )
                ).label('success_calls'),
                func.avg(ApiCallLog.response_time_ms).label('avg_response_time'),
                func.count(func.distinct(ApiCallLog.device_id)).label('unique_devices')
            )
            .where(and_(*conditions))
        )
        
        basic_result = await session.execute(basic_stmt)
        basic_row = basic_result.first()
        
        total_calls = basic_row.total_calls or 0
        success_calls = basic_row.success_calls or 0
        success_rate = (success_calls / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": total_calls - success_calls,
            "success_rate": round(success_rate, 2),
            "avg_response_time_ms": round(float(basic_row.avg_response_time or 0), 2),
            "unique_devices": basic_row.unique_devices or 0
        }

    async def _get_device_usage_stats(
        self,
        session: AsyncSession,
        conditions: List
    ) -> List[Dict[str, Any]]:
        """获取设备使用统计"""
        stmt = (
            select(
                ApiCallLog.device_id,
                func.count(ApiCallLog.id).label("call_count"),
                func.avg(ApiCallLog.response_time_ms).label("avg_response_time"),
                func.sum(
                    case((ApiCallLog.status_code == 200, 1), else_=0)
                ).label("success_count")
            )
            .where(and_(*conditions))
            .group_by(ApiCallLog.device_id)
            .order_by(desc("call_count"))
        )
        
        result = await session.execute(stmt)
        rows = result.all()
        
        device_stats = []
        for row in rows:
            success_rate = round(row.success_count / row.call_count * 100, 2) if row.call_count > 0 else 0
            device_stats.append({
                "device_id": row.device_id,
                "call_count": row.call_count,
                "success_calls": row.success_count,
                "avg_response_time_ms": round(float(row.avg_response_time or 0), 2),
                "success_rate": success_rate
            })
        
        return device_stats

    async def get_speak_device_stats(
        self,
        session: AsyncSession,
        user_id: int,
        params: AnalyticsQueryParams
    ) -> List[Dict[str, Any]]:
        """获取speak接口的设备统计"""
        try:
            # 计算时间范围
            if params.start_date and params.end_date:
                # 自定义日期范围
                start_time = datetime.strptime(params.start_date, '%Y-%m-%d')
                end_time = datetime.strptime(params.end_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                # 使用预设时间周期，以当前日期的结束时间为结束时间点
                now = datetime.now(BJ_TZ)
                # 对于按天分组的周期，使用当天的结束时间
                if params.period in [PeriodType.DAY_7, PeriodType.DAY_30, PeriodType.DAY_90]:
                    end_time = datetime.combine(now.date(), datetime.max.time(), tzinfo=BJ_TZ)
                else:
                    end_time = now
                start_time = self._calculate_start_time(end_time, params.period)
            
            # 基础条件：只查询speak接口
            conditions = [
                ApiCallLog.user_id == user_id,
                ApiCallLog.endpoint == "/api/v1/speak",
                ApiCallLog.created_at >= start_time,
                ApiCallLog.created_at < end_time
            ]
            
            # 设备过滤
            if params.device_id:
                conditions.append(ApiCallLog.device_id == params.device_id)
            
            # 获取设备统计
            stmt = (
                select(
                    ApiCallLog.device_id,
                    ApiCallLog.device_name,
                    func.count(ApiCallLog.id).label("total_calls"),
                    func.sum(
                        case((ApiCallLog.status_code == 200, 1), else_=0)
                    ).label("success_count"),
                    func.avg(ApiCallLog.response_time_ms).label("avg_response_time"),
                    func.max(ApiCallLog.created_at).label("last_call_time")
                )
                .where(and_(*conditions))
                .group_by(ApiCallLog.device_id, ApiCallLog.device_name)
                .order_by(desc("total_calls"))
            )
            
            result = await session.execute(stmt)
            rows = result.all()
            
            device_stats = []
            for row in rows:
                success_rate = round(row.success_count / row.total_calls * 100, 2) if row.total_calls > 0 else 0
                device_stats.append({
                    "device_id": row.device_id,
                    "device_name": row.device_name or row.device_id,
                    "total_calls": row.total_calls,
                    "success_count": row.success_count,
                    "success_rate": success_rate,
                    "avg_response_time": round(float(row.avg_response_time or 0), 2),
                    "last_call_time": row.last_call_time
                })
            
            return device_stats
            
        except Exception as e:
            logger.error(f"获取speak设备统计失败: {e}")
            raise

    def _calculate_start_time(self, end_time: datetime, period: PeriodType) -> datetime:
        """计算开始时间"""
        if period == PeriodType.HOUR_1:
            return end_time - timedelta(hours=1)
        elif period == PeriodType.HOUR_24:
            # 24小时数据：从24小时前开始到当前时间
            # 例如：现在是8月13日07:59，显示8月12日07:59到8月13日07:59的24小时数据
            return end_time - timedelta(hours=24)
        elif period == PeriodType.DAY_7:
            # 7天数据：从今天往前推6天，这样包含今天在内共7天
            # 例如：今天是8月13日，那么应该显示8月7日到8月13日
            today = end_time.date()
            start_date = today - timedelta(days=6)
            return datetime.combine(start_date, datetime.min.time(), tzinfo=BJ_TZ)
        elif period == PeriodType.DAY_30:
            # 30天数据：从今天往前推29天
            today = end_time.date()
            start_date = today - timedelta(days=29)
            return datetime.combine(start_date, datetime.min.time(), tzinfo=BJ_TZ)
        elif period == PeriodType.DAY_90:
            # 90天数据：从今天往前推89天
            today = end_time.date()
            start_date = today - timedelta(days=89)
            return datetime.combine(start_date, datetime.min.time(), tzinfo=BJ_TZ)
        else:
            return end_time - timedelta(days=7)

    async def _get_overview_statistics(
        self,
        session: AsyncSession,
        conditions: List
    ) -> OverviewStats:
        """获取总体统计"""
        # 基础统计
        basic_stmt = (
            select(
                func.count(ApiCallLog.id).label('total_calls'),
                func.sum(
                    case((
                        and_(ApiCallLog.status_code >= 200, ApiCallLog.status_code < 300), 1
                    ), else_=0)
                ).label('success_calls'),
                func.avg(ApiCallLog.response_time_ms).label('avg_response_time'),
                func.sum(ApiCallLog.request_size).label('total_request_size'),
                func.sum(ApiCallLog.response_size).label('total_response_size')
            )
            .where(and_(*conditions))
        )
        
        basic_result = await session.execute(basic_stmt)
        basic_row = basic_result.first()
        
        total_calls = basic_row.total_calls or 0
        success_calls = basic_row.success_calls or 0
        success_rate = (success_calls / total_calls * 100) if total_calls > 0 else 0
        
        # 热门端点
        top_endpoints_stmt = (
            select(
                ApiCallLog.endpoint,
                func.count(ApiCallLog.id).label('total_calls'),
                func.sum(
                    case((
                        and_(ApiCallLog.status_code >= 200, ApiCallLog.status_code < 300), 1
                    ), else_=0)
                ).label('success_calls'),
                func.sum(
                    case((ApiCallLog.status_code >= 400, 1), else_=0)
                ).label('error_calls'),
                func.avg(ApiCallLog.response_time_ms).label('avg_response_time'),
                func.sum(ApiCallLog.request_size).label('total_request_size'),
                func.sum(ApiCallLog.response_size).label('total_response_size')
            )
            .where(and_(*conditions))
            .group_by(ApiCallLog.endpoint)
            .order_by(desc('total_calls'))
            .limit(5)
        )
        
        top_endpoints_result = await session.execute(top_endpoints_stmt)
        top_endpoints_rows = top_endpoints_result.all()
        
        top_endpoints = []
        for row in top_endpoints_rows:
            endpoint_success_rate = (row.success_calls / row.total_calls * 100) if row.total_calls > 0 else 0
            top_endpoints.append(EndpointStats(
                endpoint=row.endpoint,
                total_calls=row.total_calls,
                success_calls=row.success_calls,
                error_calls=row.error_calls,
                success_rate=round(endpoint_success_rate, 2),
                avg_response_time=round(float(row.avg_response_time or 0), 2),
                total_request_size=row.total_request_size or 0,
                total_response_size=row.total_response_size or 0
            ))
        
        # 错误分布
        error_stmt = (
            select(
                ApiCallLog.status_code,
                func.count(ApiCallLog.id).label('count')
            )
            .where(
                and_(*conditions),
                ApiCallLog.status_code >= 400
            )
            .group_by(ApiCallLog.status_code)
            .order_by(desc('count'))
        )
        
        error_result = await session.execute(error_stmt)
        error_rows = error_result.all()
        
        error_distribution = []
        total_errors = sum(row.count for row in error_rows)
        for row in error_rows:
            percentage = (row.count / total_errors * 100) if total_errors > 0 else 0
            error_distribution.append(ErrorDistribution(
                status_code=row.status_code,
                count=row.count,
                percentage=round(percentage, 2)
            ))
        
        return OverviewStats(
            total_calls=total_calls,
            success_rate=round(success_rate, 2),
            avg_response_time=round(float(basic_row.avg_response_time or 0), 2),
            total_request_size=basic_row.total_request_size or 0,
            total_response_size=basic_row.total_response_size or 0,
            top_endpoints=top_endpoints,
            error_distribution=error_distribution
        )

    async def _get_time_series_data(
        self,
        session: AsyncSession,
        conditions: List,
        group_by: GroupByType,
        start_time: datetime,
        end_time: datetime
    ) -> List[TimeSeriesDataPoint]:
        """获取时间序列数据（北京时间分桶，Python 聚合——库内存 UTC，SQL 日期函数会错日界）"""
        try:
            _hour = (group_by == GroupByType.HOUR)

            # 取范围内的明细（只取需要的列），在 Python 侧按北京时间分桶
            stmt = select(
                ApiCallLog.created_at,
                ApiCallLog.status_code,
                ApiCallLog.response_time_ms,
                ApiCallLog.request_size,
                ApiCallLog.response_size,
            ).where(and_(*conditions))
            result = await session.execute(stmt)
            rows = result.all()

            def _bucket_key(dt: datetime) -> str:
                # created_at 经 BJDateTime 读出即为北京时间 aware
                if _hour:
                    return dt.strftime('%Y-%m-%d %H:00:00')
                return dt.strftime('%Y-%m-%d 00:00:00')

            data_dict: Dict[str, Dict] = {}
            for created_at, status_code, rt, req_size, resp_size in rows:
                if created_at is None:
                    continue
                key = _bucket_key(created_at)
                d = data_dict.setdefault(key, {
                    'total_calls': 0, 'success_calls': 0, 'error_calls': 0,
                    'rt_sum': 0.0, 'rt_n': 0,
                    'total_request_size': 0, 'total_response_size': 0,
                })
                d['total_calls'] += 1
                if 200 <= status_code < 300:
                    d['success_calls'] += 1
                if status_code >= 400:
                    d['error_calls'] += 1
                d['rt_sum'] += float(rt or 0)
                d['rt_n'] += 1
                d['total_request_size'] += req_size or 0
                d['total_response_size'] += resp_size or 0

            # 生成完整时间序列（含空白补零）
            time_series = []
            current_time = start_time
            step = timedelta(hours=1) if _hour else timedelta(days=1)
            while current_time <= end_time:
                if _hour:
                    time_key = current_time.strftime('%Y-%m-%d %H:00:00')
                else:
                    time_key = current_time.strftime('%Y-%m-%d 00:00:00')
                d = data_dict.get(time_key, {
                    'total_calls': 0, 'success_calls': 0, 'error_calls': 0,
                    'rt_sum': 0.0, 'rt_n': 0,
                    'total_request_size': 0, 'total_response_size': 0,
                })
                time_series.append(TimeSeriesDataPoint(
                    timestamp=time_key,
                    calls=d['total_calls'],
                    success_calls=d['success_calls'],
                    error_calls=d['error_calls'],
                    avg_response_time=round(d['rt_sum'] / d['rt_n'], 2) if d['rt_n'] else 0.0,
                    total_request_size=d['total_request_size'],
                    total_response_size=d['total_response_size'],
                ))
                current_time = current_time + step

            return time_series

        except Exception as e:
            logger.error(f"获取时间序列数据失败: {e}")
            return []


# 创建服务实例
analytics_service = AnalyticsService()