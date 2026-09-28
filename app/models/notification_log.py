# -*- coding: utf-8 -*-
"""
通知历史记录数据模型
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.database import Base, BJDateTime


class NotificationStatus(str, enum.Enum):
    """通知发送状态枚举（与通知服务写入的字符串值保持一致）"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class NotificationLog(Base):
    """通知日志模型"""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="日志ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )
    channel_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("notification_channels.id", ondelete="SET NULL"), nullable=True, comment="使用的通道ID"
    )
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="通道类型")
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="通道名称/临时发送")
    
    title: Mapped[Optional[str]] = mapped_column(String(200), comment="消息标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    recipient: Mapped[Optional[str]] = mapped_column(String(255), comment="接收人（例如邮箱、设备等）")
    
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(
            NotificationStatus,
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
            length=50,
        ),
        default=NotificationStatus.SUCCESS,
        comment="发送状态 (pending/success/failed)",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, comment="发送失败的错误信息")

    created_at: Mapped[datetime] = mapped_column(BJDateTime(), server_default=func.now(), comment="发送时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="notification_logs")
    channel: Mapped[Optional["NotificationChannel"]] = relationship("NotificationChannel")

    # 索引
    __table_args__ = (
        Index("idx_log_user_id", "user_id"),
        Index("idx_log_channel_type", "channel_type"),
        Index("idx_log_status", "status"),
        Index("idx_log_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog(id={self.id}, type='{self.channel_type}', status='{self.status}')>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "channel_name": self.channel_name,
            "title": self.title,
            "content": self.content,
            "recipient": self.recipient,
            "status": self.status.value if isinstance(self.status, NotificationStatus) else self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
