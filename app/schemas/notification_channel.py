# -*- coding: utf-8 -*-
"""
通知渠道相关的 Pydantic 模式
"""

from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class NotificationChannelCreate(BaseModel):
    """创建通知渠道请求"""

    name: str = Field(..., description="通道名称", min_length=1, max_length=100)
    channel_type: str = Field(..., description="通道类型: email/dingtalk/wechat/feishu/webhook/speak")
    config: Dict[str, Any] = Field(..., description="通道配置字典")
    is_active: bool = Field(default=True, description="是否启用")

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        valid_types = ["email", "dingtalk", "wechat", "feishu", "webhook", "speak"]
        if v not in valid_types:
            raise ValueError(f"无效的通道类型. 必须是以下之一: {', '.join(valid_types)}")
        return v

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: Dict[str, Any], info: Any) -> Dict[str, Any]:
        # 可以根据类型做基本字段校验，但不强制限制结构以保持扩展性
        return v


class NotificationChannelUpdate(BaseModel):
    """修改通知渠道请求"""

    name: Optional[str] = Field(None, description="通道名称", min_length=1, max_length=100)
    channel_type: Optional[str] = Field(None, description="通道类型")
    config: Optional[Dict[str, Any]] = Field(None, description="通道配置字典")
    is_active: Optional[bool] = Field(None, description="是否启用")

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_types = ["email", "dingtalk", "wechat", "feishu", "webhook", "speak"]
        if v not in valid_types:
            raise ValueError(f"无效的通道类型. 必须是以下之一: {', '.join(valid_types)}")
        return v


class NotificationChannelResponse(BaseModel):
    """通知渠道响应模型"""

    id: int = Field(..., description="渠道ID")
    name: str = Field(..., description="渠道名称")
    channel_type: str = Field(..., description="渠道类型")
    config: Dict[str, Any] = Field(..., description="脱敏后的通道配置")
    is_active: bool = Field(..., description="是否启用")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_masked(cls, obj: Any) -> "NotificationChannelResponse":
        """从 ORM 对象构建响应并进行敏感数据脱敏"""
        import json
        from app.utils.encryption import decrypt_password
        try:
            decrypted = decrypt_password(obj.config_json)
            config = json.loads(decrypted)
        except Exception:
            config = {}
            
        # 脱敏敏感字段
        masked_config = config.copy()
        for k in masked_config:
            kl = k.lower()
            if any(keyword in kl for keyword in ("password", "secret", "token", "key", "pass")):
                if isinstance(masked_config[k], str) and masked_config[k]:
                    masked_config[k] = "******"
                    
        return cls(
            id=obj.id,
            name=obj.name,
            channel_type=obj.channel_type,
            config=masked_config,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )
