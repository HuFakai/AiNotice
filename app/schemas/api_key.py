# -*- coding: utf-8 -*-
"""
API密钥相关数据模式
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class CreateApiKeyRequest(BaseModel):
    """创建API密钥请求"""

    key_name: str = Field(..., description="密钥名称", min_length=1, max_length=100)
    permissions: Optional[Dict[str, bool]] = Field(None, description="权限配置")
    expires_in_days: Optional[int] = Field(None, description="过期天数", gt=0, le=365)
    usage_limit: Optional[int] = Field(None, description="使用限制", gt=0)
    channel_ids: Optional[List[int]] = Field(None, description="绑定的通知渠道ID列表（调用 /notify/send 未指定渠道时向这些渠道推送）")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        """验证权限配置"""
        if v is None:
            return v

        valid_permissions = {
            "speak",
            "get_devices",
            "manage_devices",
            "stop_speak",
            "set_volume",
            "get_status",
            "send_notify",
        }

        for perm in v.keys():
            if perm not in valid_permissions:
                raise ValueError(f"无效的权限类型: {perm}")

        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "key_name": "生产环境密钥",
                "permissions": {
                    "speak": True,
                    "get_devices": True,
                    "manage_devices": False,
                    "stop_speak": True,
                    "set_volume": False,
                    "get_status": True,
                    "send_notify": True,
                },
                "expires_in_days": 90,
                "usage_limit": 10000,
            }
        }
    }


class UpdateApiKeyRequest(BaseModel):
    """更新API密钥请求"""

    key_name: Optional[str] = Field(None, description="密钥名称", min_length=1, max_length=100)
    permissions: Optional[Dict[str, bool]] = Field(None, description="权限配置")
    is_active: Optional[bool] = Field(None, description="是否激活")
    usage_limit: Optional[int] = Field(None, description="使用限制", gt=0)
    channel_ids: Optional[List[int]] = Field(None, description="绑定的通知渠道ID列表（整体替换语义）")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        """验证权限配置"""
        if v is None:
            return v

        valid_permissions = {
            "speak",
            "get_devices",
            "manage_devices",
            "stop_speak",
            "set_volume",
            "get_status",
            "send_notify",
        }

        for perm in v.keys():
            if perm not in valid_permissions:
                raise ValueError(f"无效的权限类型: {perm}")

        return v


class ApiKeyResponse(BaseModel):
    """API密钥响应"""

    id: int = Field(..., description="密钥ID")
    key_name: str = Field(..., description="密钥名称")
    api_key: str = Field(..., description="API密钥（明文）")
    is_active: bool = Field(..., description="是否激活")
    is_expired: bool = Field(..., description="是否过期")
    is_usage_exceeded: bool = Field(..., description="是否超出使用限制")
    is_valid: bool = Field(..., description="是否有效")
    permissions: Optional[Dict[str, Any]] = Field(None, description="权限配置")
    channel_ids: Optional[List[int]] = Field(None, description="绑定的通知渠道ID列表")
    usage_count: int = Field(..., description="使用次数")
    usage_limit: Optional[int] = Field(None, description="使用限制")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """API密钥创建响应"""

    id: int = Field(..., description="密钥ID")
    key_name: str = Field(..., description="密钥名称")
    api_key: str = Field(..., description="API密钥（明文）")
    permissions: Dict[str, bool] = Field(..., description="权限配置")
    channel_ids: Optional[List[int]] = Field(None, description="绑定的通知渠道ID列表")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    usage_limit: Optional[int] = Field(None, description="使用限制")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "key_name": "生产环境密钥",
                "api_key": "xai_sk_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "permissions": {
                    "speak": True,
                    "get_devices": True,
                    "manage_devices": False,
                    "stop_speak": True,
                    "set_volume": False,
                    "get_status": True,
                    "send_notify": True,
                },
                "expires_at": "2025-05-11T10:00:00Z",
                "usage_limit": 10000,
                "created_at": "2025-02-11T10:00:00Z",
            }
        }
    }
