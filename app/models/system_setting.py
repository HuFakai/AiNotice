# -*- coding: utf-8 -*-
"""
系统配置数据模型
"""

from datetime import datetime
from typing import Optional, Any, Union
from sqlalchemy import Integer, String, DateTime, Text, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import enum
import json

from app.database import Base


class SettingType(str, enum.Enum):
    """配置类型枚举"""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"


class SystemSetting(Base):
    """系统配置模型"""

    __tablename__ = "system_settings"

    # 基础字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="配置ID")
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="配置键")
    setting_value: Mapped[Optional[str]] = mapped_column(Text, comment="配置值")
    setting_type: Mapped[SettingType] = mapped_column(SQLEnum(SettingType), default=SettingType.STRING, comment="配置类型")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="配置描述")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否公开可见")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 索引
    __table_args__ = (
        Index("idx_setting_key", "setting_key"),
        Index("idx_is_public", "is_public"),
    )

    def __repr__(self) -> str:
        return f"<SystemSetting(key='{self.setting_key}', value='{self.setting_value}')>"

    @property
    def typed_value(self) -> Any:
        """返回类型化的配置值"""
        if self.setting_value is None:
            return None

        try:
            if self.setting_type == SettingType.STRING:
                return str(self.setting_value)
            elif self.setting_type == SettingType.INT:
                return int(self.setting_value)
            elif self.setting_type == SettingType.FLOAT:
                return float(self.setting_value)
            elif self.setting_type == SettingType.BOOLEAN:
                return self.setting_value.lower() in ("true", "1", "yes", "on")
            elif self.setting_type == SettingType.JSON:
                return json.loads(self.setting_value)
        except (ValueError, json.JSONDecodeError):
            # 如果转换失败，返回原始字符串
            return self.setting_value

        return self.setting_value

    def set_typed_value(self, value: Any) -> None:
        """设置类型化的配置值"""
        if value is None:
            self.setting_value = None
            return

        if self.setting_type == SettingType.JSON:
            self.setting_value = json.dumps(value, ensure_ascii=False)
        else:
            self.setting_value = str(value)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "typed_value": self.typed_value,
            "setting_type": self.setting_type.value,
            "description": self.description,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 系统配置键常量
class SettingKey:
    """系统配置键常量"""

    # 平台基础配置
    PLATFORM_NAME = "platform_name"
    PLATFORM_VERSION = "platform_version"

    # 注册和认证配置
    REGISTRATION_ENABLED = "registration_enabled"
    EMAIL_VERIFICATION_REQUIRED = "email_verification_required"

    # 限制配置
    API_RATE_LIMIT = "api_rate_limit"
    MAX_DEVICES_PER_USER = "max_devices_per_user"
    MAX_API_KEYS_PER_USER = "max_api_keys_per_user"

    # JWT配置
    JWT_SECRET_KEY = "jwt_secret_key"
    JWT_EXPIRE_HOURS = "jwt_expire_hours"

    # 邮件配置
    EMAIL_SMTP_HOST = "email_smtp_host"
    EMAIL_SMTP_PORT = "email_smtp_port"
    EMAIL_SMTP_USER = "email_smtp_user"
    EMAIL_SMTP_PASSWORD = "email_smtp_password"
    EMAIL_FROM_ADDRESS = "email_from_address"
