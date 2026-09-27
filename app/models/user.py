# -*- coding: utf-8 -*-
"""
用户数据模型
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="用户名")
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="邮箱地址")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    display_name: Mapped[Optional[str]] = mapped_column(String(100), comment="显示名称")

    # 状态字段
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, comment="邮箱是否验证")
    # 令牌版本：登出/修改密码时递增，使所有已签发 JWT 立即失效
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="JWT令牌版本")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="最后登录时间")

    # 关系映射
    # 统一 lazy="select"：认证热路径不连带查询整张关系图；
    # 需要关系数据的调用方显式使用 selectinload 或聚合查询
    mi_accounts: Mapped[List["MiAccount"]] = relationship(
        "MiAccount", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    devices: Mapped[List["Device"]] = relationship(
        "Device", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    speak_tasks: Mapped[List["SpeakTask"]] = relationship(
        "SpeakTask", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    activities: Mapped[List["UserActivity"]] = relationship(
        "UserActivity", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    notification_channels: Mapped[List["NotificationChannel"]] = relationship(
        "NotificationChannel", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    notification_logs: Mapped[List["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    # 索引
    # 注：idx_username / idx_email 与列上 unique=True 自动生成的唯一索引重复，已删除。
    __table_args__ = (
        Index("idx_users_created_at", "created_at"),
        Index("idx_user_created_at", "id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    @property
    def display_username(self) -> str:
        """显示用户名"""
        return self.display_name or self.username

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
