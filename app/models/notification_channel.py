# -*- coding: utf-8 -*-
"""
通知渠道数据模型
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, BJDateTime


class NotificationChannel(Base):
    """通知渠道模型"""

    __tablename__ = "notification_channels"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="通道ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="通道名称")
    channel_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="通道类型 (email/dingtalk/wechat/feishu/webhook/speak)"
    )
    config_json: Mapped[str] = mapped_column(Text, nullable=False, comment="加密的配置 JSON 字符串")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(BJDateTime(), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="notification_channels")

    # 索引
    __table_args__ = (
        Index("idx_channel_user_id", "user_id"),
        Index("idx_channel_type", "channel_type"),
        Index("idx_channel_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<NotificationChannel(id={self.id}, name='{self.name}', type='{self.channel_type}')>"
