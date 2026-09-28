# -*- coding: utf-8 -*-
"""
API调用记录数据模型
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Boolean, DateTime, Text, Index, BigInteger, DECIMAL, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey

from app.database import Base, BJDateTime


class ApiCallLog(Base):
    """API调用记录模型"""

    __tablename__ = "api_call_logs"

    # 基础字段
    # 说明：id 使用 BigInteger 以满足调用量增长需求；SQLite 只有 INTEGER
    # 主键才能自增（BIGINT 主键插入 NULL 会违反 NOT NULL），因此对 sqlite
    # 方言降级为 INTEGER，其它方言仍为 BIGINT。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        comment="记录ID",
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    api_key_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("api_keys.id"), comment="API密钥ID")
    
    # 请求信息
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, comment="API端点")
    method: Mapped[str] = mapped_column(String(10), nullable=False, comment="HTTP方法")
    request_ip: Mapped[Optional[str]] = mapped_column(String(45), comment="请求IP地址")
    user_agent: Mapped[Optional[str]] = mapped_column(Text, comment="用户代理")
    
    # 数据大小
    request_size: Mapped[int] = mapped_column(Integer, default=0, comment="请求大小(字节)")
    response_size: Mapped[int] = mapped_column(Integer, default=0, comment="响应大小(字节)")
    
    # 响应信息
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="HTTP状态码")
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, comment="响应时间(毫秒)")
    error_message: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息")
    
    # JSON数据
    request_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, comment="请求参数")
    response_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, comment="响应数据")
    
    # Speak接口专用字段
    device_id: Mapped[Optional[str]] = mapped_column(String(100), comment="设备ID")
    device_name: Mapped[Optional[str]] = mapped_column(String(100), comment="设备名称")
    speak_text: Mapped[Optional[str]] = mapped_column(Text, comment="语音播报内容")
    task_end_time: Mapped[Optional[datetime]] = mapped_column(BJDateTime(), comment="任务结束时间")
    
    # 时间字段
    created_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), comment="创建时间"
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", lazy="select")
    api_key: Mapped[Optional["ApiKey"]] = relationship("ApiKey", lazy="select")

    # 索引优化
    __table_args__ = (
        Index("idx_api_call_logs_user_id", "user_id"),
        Index("idx_api_call_logs_created_at", "created_at"),
        Index("idx_api_call_logs_endpoint", "endpoint"),
        Index("idx_api_call_logs_status_code", "status_code"),
        Index("idx_api_call_logs_user_created", "user_id", "created_at"),
        Index("idx_api_call_logs_endpoint_created", "endpoint", "created_at"),
        Index("idx_api_call_logs_device_id", "device_id"),
        Index("idx_api_call_logs_speak_endpoint", "endpoint", "device_id"),
    )

    def __repr__(self) -> str:
        return f"<ApiCallLog(id={self.id}, endpoint='{self.endpoint}', method='{self.method}', status={self.status_code})>"

    @property
    def is_success(self) -> bool:
        """判断是否成功"""
        return 200 <= self.status_code < 300

    @property
    def is_client_error(self) -> bool:
        """判断是否客户端错误"""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """判断是否服务器错误"""
        return self.status_code >= 500

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
            "api_key_name": self.api_key.key_name if self.api_key else None,
            "endpoint": self.endpoint,
            "method": self.method,
            "request_ip": str(self.request_ip) if self.request_ip else None,
            "user_agent": self.user_agent,
            "request_size": self.request_size,
            "response_size": self.response_size,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "request_params": self.request_params,
            "response_data": self.response_data,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "speak_text": self.speak_text,
            "task_end_time": self.task_end_time.isoformat() if self.task_end_time else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_success": self.is_success,
        }


class ApiUsageStats(Base):
    """API使用统计模型"""

    __tablename__ = "api_usage_stats"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="统计ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment="统计日期")
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, comment="API端点")
    
    # 统计数据
    total_calls: Mapped[int] = mapped_column(Integer, default=0, comment="总调用次数")
    success_calls: Mapped[int] = mapped_column(Integer, default=0, comment="成功调用次数")
    error_calls: Mapped[int] = mapped_column(Integer, default=0, comment="错误调用次数")
    avg_response_time_ms: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0, comment="平均响应时间(毫秒)")
    total_request_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="总请求大小(字节)")
    total_response_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="总响应大小(字节)")
    
    # 时间字段
    created_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", lazy="select")

    # 唯一约束和索引
    __table_args__ = (
        Index("idx_api_usage_stats_user_date", "user_id", "date"),
        Index("idx_api_usage_stats_endpoint", "endpoint"),
        Index("idx_api_usage_stats_unique", "user_id", "date", "endpoint", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ApiUsageStats(id={self.id}, user_id={self.user_id}, date={self.date}, endpoint='{self.endpoint}')>"

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_calls == 0:
            return 0.0
        return (self.success_calls / self.total_calls) * 100

    @property
    def error_rate(self) -> float:
        """错误率"""
        if self.total_calls == 0:
            return 0.0
        return (self.error_calls / self.total_calls) * 100

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "endpoint": self.endpoint,
            "total_calls": self.total_calls,
            "success_calls": self.success_calls,
            "error_calls": self.error_calls,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "avg_response_time_ms": float(self.avg_response_time_ms),
            "total_request_size": self.total_request_size,
            "total_response_size": self.total_response_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ApiQuota(Base):
    """API配额管理模型"""

    __tablename__ = "api_quotas"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="配额ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False, comment="API端点")
    quota_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="配额类型: daily, monthly, total")
    
    # 配额信息
    quota_limit: Mapped[int] = mapped_column(Integer, nullable=False, comment="配额限制")
    quota_used: Mapped[int] = mapped_column(Integer, default=0, comment="已使用配额")
    reset_date: Mapped[Optional[datetime.date]] = mapped_column(Date, comment="重置日期")
    
    # 时间字段
    created_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", lazy="select")

    # 唯一约束和索引
    __table_args__ = (
        Index("idx_api_quotas_user_endpoint", "user_id", "endpoint"),
        Index("idx_api_quotas_unique", "user_id", "endpoint", "quota_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ApiQuota(id={self.id}, user_id={self.user_id}, endpoint='{self.endpoint}', type='{self.quota_type}')>"

    @property
    def quota_remaining(self) -> int:
        """剩余配额"""
        return max(0, self.quota_limit - self.quota_used)

    @property
    def usage_percentage(self) -> float:
        """使用率百分比"""
        if self.quota_limit == 0:
            return 0.0
        return (self.quota_used / self.quota_limit) * 100

    @property
    def is_exceeded(self) -> bool:
        """是否超出配额"""
        return self.quota_used >= self.quota_limit

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "quota_type": self.quota_type,
            "quota_limit": self.quota_limit,
            "quota_used": self.quota_used,
            "quota_remaining": self.quota_remaining,
            "usage_percentage": self.usage_percentage,
            "is_exceeded": self.is_exceeded,
            "reset_date": self.reset_date.isoformat() if self.reset_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }