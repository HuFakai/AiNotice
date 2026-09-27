# -*- coding: utf-8 -*-
"""
语音任务数据模型
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Float, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""

    PENDING = "pending"
    PLAYING = "playing"
    COMPLETED = "completed"
    FAILED = "failed"


class SpeakTask(Base):
    """语音任务模型"""

    __tablename__ = "speak_tasks"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="任务ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, comment="关联设备ID"
    )
    api_key_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), comment="调用API密钥ID"
    )

    # 任务信息
    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="任务唯一标识")
    text_content: Mapped[str] = mapped_column(Text, nullable=False, comment="播放文本内容")
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.PENDING,
        comment="任务状态",
    )

    # 时长信息
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float, comment="预计播放时长(秒)")
    actual_duration: Mapped[Optional[float]] = mapped_column(Float, comment="实际播放时长(秒)")

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息")

    # 客户端信息
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), comment="客户端IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), comment="用户代理")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="开始时间")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="完成时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="speak_tasks")
    device: Mapped["Device"] = relationship("Device", back_populates="speak_tasks")
    api_key: Mapped[Optional["ApiKey"]] = relationship("ApiKey", back_populates="speak_tasks")

    # 索引
    __table_args__ = (
        Index("idx_speak_tasks_user_id", "user_id"),
        Index("idx_speak_tasks_device_id", "device_id"),
        Index("idx_task_id", "task_id"),
        Index("idx_status", "status"),
        Index("idx_speak_tasks_created_at", "created_at"),
        Index("idx_task_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<SpeakTask(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"

    @property
    def is_completed(self) -> bool:
        """任务是否完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]

    @property
    def is_running(self) -> bool:
        """任务是否正在运行"""
        return self.status == TaskStatus.PLAYING

    @property
    def duration_seconds(self) -> Optional[float]:
        """任务执行时长(秒)"""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.now(timezone.utc)
        # started_at 若来自 SQLite 读回则为 naive，此处做 UTC 归一化避免 aware/naive 混算
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        started_at = self.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return (end_time - started_at).total_seconds()

    @property
    def text_preview(self) -> str:
        """文本预览（前50个字符）"""
        if len(self.text_content) <= 50:
            return self.text_content
        return f"{self.text_content[:50]}..."

    def start(self) -> None:
        """开始任务"""
        self.status = TaskStatus.PLAYING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, actual_duration: Optional[float] = None) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if actual_duration is not None:
            self.actual_duration = actual_duration

    def fail(self, error_message: str) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "api_key_id": self.api_key_id,
            "task_id": self.task_id,
            "text_content": self.text_content,
            "text_preview": self.text_preview,
            "status": self.status.value,
            "is_completed": self.is_completed,
            "is_running": self.is_running,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
