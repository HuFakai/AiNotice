# -*- coding: utf-8 -*-
"""
小米账户数据模型
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class SyncStatus(str, enum.Enum):
    """同步状态枚举（与API响应模型保持一致，使用小写）"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class MiAccount(Base):
    """小米账户模型"""

    __tablename__ = "mi_accounts"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="小米账户ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )

    # 小米账户信息
    mi_username: Mapped[str] = mapped_column(String(100), nullable=False, comment="小米用户名")
    mi_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False, comment="加密的小米密码")

    # 小米认证信息
    mi_device_id: Mapped[Optional[str]] = mapped_column(String(100), comment="小米设备ID")
    mi_user_id: Mapped[Optional[str]] = mapped_column(String(100), comment="小米用户ID")
    mi_pass_token: Mapped[Optional[str]] = mapped_column(Text, comment="小米PassToken")

    # 状态字段
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    sync_status: Mapped[SyncStatus] = mapped_column(
        SQLEnum(SyncStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=SyncStatus.PENDING,
        comment="同步状态",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="最后同步时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="mi_accounts")
    devices: Mapped[List["Device"]] = relationship(
        "Device", back_populates="mi_account", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引
    __table_args__ = (
        Index("idx_mi_accounts_user_id", "user_id"),
        Index("idx_mi_accounts_mi_username", "mi_username"),
        Index("idx_sync_status", "sync_status"),
    )

    def __repr__(self) -> str:
        return f"<MiAccount(id={self.id}, user_id={self.user_id}, mi_username='{self.mi_username}')>"

    @property
    def device_count(self) -> int:
        """音箱设备数量（只统计wifispeaker设备）"""
        if not self.devices:
            return 0
        # 只统计包含wifispeaker的音箱设备
        speaker_devices = [device for device in self.devices 
                          if device.device_model and 'wifispeaker' in device.device_model.lower()]
        return len(speaker_devices)

    @property
    def is_synced(self) -> bool:
        """是否同步成功"""
        return self.sync_status == SyncStatus.SUCCESS

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mi_username": self.mi_username,
            "mi_device_id": self.mi_device_id,
            "mi_user_id": self.mi_user_id,
            "is_active": self.is_active,
            "sync_status": self.sync_status.value,
            "error_message": self.error_message,
            "device_count": self.device_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
        }
