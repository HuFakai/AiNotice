# -*- coding: utf-8 -*-
"""
设备数据模型
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Device(Base):
    """设备模型"""

    __tablename__ = "devices"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="设备ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )
    mi_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mi_accounts.id", ondelete="CASCADE"), nullable=False, comment="关联小米账户ID"
    )

    # 设备信息
    device_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="设备唯一标识")
    device_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="设备名称")
    device_model: Mapped[Optional[str]] = mapped_column(String(50), comment="设备型号")
    device_type: Mapped[str] = mapped_column(String(50), default="xiaomi_speaker", comment="设备类型")
    location: Mapped[Optional[str]] = mapped_column(String(100), comment="设备位置")
    mi_username: Mapped[str] = mapped_column(String(100), nullable=False, comment="关联的小米账号用户名")

    # 状态字段
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否在线")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否收藏")
    volume: Mapped[int] = mapped_column(Integer, default=50, comment="音量级别")

    # 扩展信息
    device_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, comment="设备详细信息")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="最后在线时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="devices")
    mi_account: Mapped["MiAccount"] = relationship("MiAccount", back_populates="devices")
    speak_tasks: Mapped[list["SpeakTask"]] = relationship(
        "SpeakTask", back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引和约束
    __table_args__ = (
        Index("idx_devices_user_id", "user_id"),
        Index("idx_devices_device_id", "device_id"),
        Index("idx_is_online", "is_online"),
        Index("idx_devices_mi_username", "mi_username"),
        Index("idx_device_user_status", "user_id", "is_online"),
        Index("idx_user_mi_username", "user_id", "mi_username"),
        # 确保同一用户下设备ID唯一
        Index("uk_user_device", "user_id", "device_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, device_name='{self.device_name}', device_id='{self.device_id}')>"

    @property
    def status_text(self) -> str:
        """状态文本"""
        return "在线" if self.is_online else "离线"

    @property
    def display_location(self) -> str:
        """显示位置"""
        return self.location or "未设置位置"

    def update_online_status(self, is_online: bool) -> None:
        """更新在线状态"""
        self.is_online = is_online
        if is_online:
            self.last_seen_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "mi_account_id": self.mi_account_id,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_model": self.device_model,
            "device_type": self.device_type,
            "location": self.location,
            "is_online": self.is_online,
            "is_favorite": self.is_favorite,
            "volume": self.volume,
            "status_text": self.status_text,
            "display_location": self.display_location,
            "device_info": self.device_info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }
