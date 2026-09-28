# -*- coding: utf-8 -*-
"""
API密钥数据模型
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ApiKey(Base):
    """API密钥模型"""

    __tablename__ = "api_keys"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="API密钥ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID"
    )

    # 密钥信息
    # 安全存储：新密钥只存 key_hash（SHA-256）与 key_prefix（掩码展示用前缀），
    # 明文 api_key 仅存在于历史数据（启动迁移会将其清空并补算哈希）
    key_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="密钥名称")
    api_key: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True,
        comment="历史明文列；迁移后的行在SQLite上存哈希副本以维持旧表NOT NULL约束，PG/MySQL为NULL"
    )
    api_secret: Mapped[Optional[str]] = mapped_column(String(255), comment="历史签名列（新密钥为空串/NULL）")
    key_hash: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, comment="API密钥SHA-256哈希（校验用）"
    )
    key_prefix: Mapped[Optional[str]] = mapped_column(String(16), comment="密钥前缀（掩码展示用）")

    # 状态和权限
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, comment="权限配置")
    # 绑定的通知渠道ID列表：用该密钥调 /notify/send 且未显式指定渠道时，
    # 自动向这里列出的启用渠道推送
    channel_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, comment="绑定的通知渠道ID列表")

    # 使用统计
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="使用次数")
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, comment="使用限制")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="最后使用时间")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="过期时间")

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="api_keys")
    speak_tasks: Mapped[list["SpeakTask"]] = relationship(
        "SpeakTask", back_populates="api_key", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引
    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_key", "api_key"),
        Index("idx_is_active", "is_active"),
        Index("idx_expires_at", "expires_at"),
        Index("idx_apikey_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, key_name='{self.key_name}', user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """是否已过期

        注意：SQLite 等后端读回的是 naive datetime，而这里用 aware UTC 比较；
        为避免 "can't compare offset-naive and offset-aware datetimes"，
        先对读回值做 UTC 归一化。
        """
        if not self.expires_at:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at

    @property
    def is_usage_exceeded(self) -> bool:
        """是否超出使用限制"""
        if not self.usage_limit:
            return False
        return self.usage_count >= self.usage_limit

    @property
    def is_valid(self) -> bool:
        """密钥是否有效"""
        return self.is_active and not self.is_expired and not self.is_usage_exceeded

    @property
    def masked_api_key(self) -> str:
        """掩码显示的API密钥（优先用存储前缀，历史明文行回退掩码）"""
        if self.key_prefix:
            return f"{self.key_prefix}••••"
        if self.api_key:
            if len(self.api_key) <= 8:
                return self.api_key
            return f"{self.api_key[:4]}****{self.api_key[-4:]}"
        return "••••"

    def has_permission(self, permission: str) -> bool:
        """检查是否具有指定权限"""
        if not self.permissions:
            return False
        return self.permissions.get(permission, False)

    def increment_usage(self) -> None:
        """增加使用次数"""
        self.usage_count += 1
        self.last_used_at = datetime.now(timezone.utc)

    def to_dict(self, include_secret: bool = False) -> dict:
        """转换为字典格式"""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "key_name": self.key_name,
            "api_key": self.masked_api_key,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "is_usage_exceeded": self.is_usage_exceeded,
            "is_valid": self.is_valid,
            "permissions": self.permissions,
            "usage_count": self.usage_count,
            "usage_limit": self.usage_limit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

        # 只在需要时包含完整密钥
        if include_secret:
            result["api_key"] = self.api_key
            result["api_secret"] = self.api_secret

        return result
