# -*- coding: utf-8 -*-
"""
API调用统计分析相关的数据模式
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class PeriodType(str, Enum):
    """时间周期类型"""
    HOUR_1 = "1h"
    HOUR_24 = "24h"
    DAY_7 = "7d"
    DAY_30 = "30d"
    DAY_90 = "90d"


class GroupByType(str, Enum):
    """分组类型"""
    ENDPOINT = "endpoint"
    STATUS = "status"
    HOUR = "hour"
    DAY = "day"
    USER = "user"


class QuotaType(str, Enum):
    """配额类型"""
    DAILY = "daily"
    MONTHLY = "monthly"
    TOTAL = "total"


# 请求模式
class CallLogsQueryParams(BaseModel):
    """调用记录查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    limit: int = Field(default=20, ge=1, le=100, description="每页数量")
    start_date: Optional[str] = Field(default=None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")
    endpoint: Optional[str] = Field(default=None, description="API端点")
    status_code: Optional[int] = Field(default=None, description="HTTP状态码")
    api_key_id: Optional[int] = Field(default=None, description="API密钥ID")
    api_key_name: Optional[str] = Field(default=None, description="API密钥名称")
    method: Optional[str] = Field(default=None, description="HTTP方法")
    device_id: Optional[str] = Field(default=None, description="设备ID")
    speak_text: Optional[str] = Field(default=None, description="播报内容关键词")

    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('日期格式必须为 YYYY-MM-DD')
        return v


class AnalyticsQueryParams(BaseModel):
    """统计分析查询参数"""
    period: PeriodType = Field(default=PeriodType.DAY_7, description="时间周期")
    start_date: Optional[str] = Field(default=None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")
    endpoint: Optional[str] = Field(default=None, description="API端点")
    group_by: GroupByType = Field(default=GroupByType.DAY, description="分组方式")
    device_id: Optional[str] = Field(default=None, description="设备ID")


# 响应模式
class ApiCallLogResponse(BaseModel):
    """API调用记录响应模式"""
    id: int
    user_id: int
    api_key_id: Optional[int]
    api_key_name: Optional[str] = None
    endpoint: str
    method: str
    request_ip: Optional[str]
    user_agent: Optional[str]
    request_size: int
    response_size: int
    status_code: int
    response_time_ms: int
    error_message: Optional[str]
    request_params: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    created_at: datetime
    is_success: bool
    # speak接口专用字段
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    speak_text: Optional[str] = None
    task_end_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class CallLogsListResponse(BaseModel):
    """调用记录列表响应"""
    success: bool = True
    data: List[ApiCallLogResponse]
    pagination: Dict[str, Any]
    message: str = "获取调用记录成功"


class TimeSeriesDataPoint(BaseModel):
    """时间序列数据点"""
    timestamp: Union[datetime, str]
    calls: int
    success_calls: int
    error_calls: int
    avg_response_time: float
    total_request_size: int
    total_response_size: int


class EndpointStats(BaseModel):
    """端点统计"""
    endpoint: str
    total_calls: int
    success_calls: int
    error_calls: int
    success_rate: float
    avg_response_time: float
    total_request_size: int
    total_response_size: int


class ErrorDistribution(BaseModel):
    """错误分布"""
    status_code: int
    count: int
    percentage: float


class OverviewStats(BaseModel):
    """概览统计"""
    total_calls: int
    success_rate: float
    avg_response_time: float
    total_request_size: int
    total_response_size: int
    top_endpoints: List[EndpointStats]
    error_distribution: List[ErrorDistribution]
    period_comparison: Optional[Dict[str, Any]] = None


class AnalyticsOverviewResponse(BaseModel):
    """统计概览响应"""
    success: bool = True
    data: OverviewStats
    time_series: List[TimeSeriesDataPoint]
    message: str = "获取统计概览成功"


class EndpointAnalyticsResponse(BaseModel):
    """端点分析响应"""
    success: bool = True
    data: List[EndpointStats]
    time_series: List[TimeSeriesDataPoint]
    message: str = "获取端点统计成功"


class PerformanceStats(BaseModel):
    """性能统计"""
    endpoint: str
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: int
    max_response_time: int
    total_calls: int
    qps: float  # 每秒请求数


class PerformanceAnalyticsResponse(BaseModel):
    """性能分析响应"""
    success: bool = True
    data: List[PerformanceStats]
    time_series: List[TimeSeriesDataPoint]
    message: str = "获取性能统计成功"


class QuotaUsage(BaseModel):
    """配额使用情况"""
    id: int
    endpoint: str
    quota_type: str
    quota_limit: int
    quota_used: int
    quota_remaining: int
    usage_percentage: float
    is_exceeded: bool
    reset_date: Optional[date]

    class Config:
        from_attributes = True


class QuotaAnalyticsResponse(BaseModel):
    """配额分析响应"""
    success: bool = True
    data: List[QuotaUsage]
    message: str = "获取配额统计成功"


class UsageStatsResponse(BaseModel):
    """使用统计响应"""
    id: int
    user_id: int
    date: date
    endpoint: str
    total_calls: int
    success_calls: int
    error_calls: int
    success_rate: float
    error_rate: float
    avg_response_time_ms: float
    total_request_size: int
    total_response_size: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageStatsListResponse(BaseModel):
    """使用统计列表响应"""
    success: bool = True
    data: List[UsageStatsResponse]
    pagination: Dict[str, Any]
    message: str = "获取使用统计成功"





class RealTimeStats(BaseModel):
    """实时统计"""
    current_qps: float
    active_users: int
    recent_calls: List[ApiCallLogResponse]
    system_health: Dict[str, Any]
    alerts: List[Dict[str, Any]]


class RealTimeStatsResponse(BaseModel):
    """实时统计响应"""
    success: bool = True
    data: RealTimeStats
    message: str = "获取实时统计成功"
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    success: bool = True
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, str] = Field(default_factory=dict)
    message: str = "服务运行正常"