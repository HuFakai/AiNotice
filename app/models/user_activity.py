# -*- coding: utf-8 -*-
"""
用户活动日志数据模型
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, BJDateTime


class UserActivity(Base):
    """用户活动日志模型"""

    __tablename__ = "user_activities"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="活动ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )

    # 活动信息
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="活动类型")
    activity_description: Mapped[str] = mapped_column(Text, nullable=False, comment="活动描述")
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), comment="资源类型")
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, comment="资源ID")

    # 客户端信息
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), comment="客户端IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), comment="用户代理")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(BJDateTime(), server_default=func.now(), comment="创建时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="activities")

    # 索引
    __table_args__ = (
        Index("idx_user_activities_user_id", "user_id"),
        Index("idx_activity_type", "activity_type"),
        Index("idx_user_activities_created_at", "created_at"),
        Index("idx_activity_user_type", "user_id", "activity_type"),
    )

    def __repr__(self) -> str:
        return f"<UserActivity(id={self.id}, user_id={self.user_id}, type='{self.activity_type}')>"

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "activity_type": self.activity_type,
            "activity_description": self.activity_description,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# 常用活动类型常量
class ActivityType:
    """活动类型常量"""

    # 用户相关
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_UPDATE_PROFILE = "user_update_profile"

    # 小米账户相关（原文件中本组常量重复定义了两次，已合并为一组）
    MI_ACCOUNT_CREATE = "mi_account_create"
    MI_ACCOUNT_UPDATE = "mi_account_update"
    MI_ACCOUNT_DELETE = "mi_account_delete"
    MI_ACCOUNT_SYNC = "mi_account_sync"

    # 设备相关
    DEVICE_ADD = "device_add"
    DEVICE_UPDATE = "device_update"
    DEVICE_DELETE = "device_delete"
    DEVICE_SPEAK = "device_speak"

    # API密钥相关
    API_KEY_CREATE = "api_key_create"
    API_KEY_UPDATE = "api_key_update"
    API_KEY_DELETE = "api_key_delete"
    API_KEY_USE = "api_key_use"
