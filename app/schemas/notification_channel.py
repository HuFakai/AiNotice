# -*- coding: utf-8 -*-
"""
通知渠道相关的 Pydantic 模式
"""

import re
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator

# 敏感字段名关键字（大小写不敏感）
SENSITIVE_KEYWORDS = ("password", "secret", "token", "key", "pass")
# URL 中的敏感 query 参数（打码值，保留参数名）
URL_SENSITIVE_PARAMS = ("access_token", "key", "sign", "secret", "token")
_URL_PARAM_RE = re.compile(
    r"(access_token|key|sign|secret|token)=([^&\s]+)", re.IGNORECASE
)
# header 中需要整体打码的字段
SENSITIVE_HEADER_NAMES = ("authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token")

MASK = "******"


def _mask_url(value: str) -> str:
    """对 URL query 中 access_token/key/sign 等参数值打码"""
    return _URL_PARAM_RE.sub(lambda m: f"{m.group(1)}={MASK}", value)


def _is_sensitive_key(key: str) -> bool:
    kl = key.lower()
    return any(keyword in kl for keyword in SENSITIVE_KEYWORDS)


def mask_sensitive_config(value: Any, key: Optional[str] = None) -> Any:
    """
    递归脱敏配置结构。

    规则：
    - dict / list 逐层递归处理；
    - 字段名含 password/secret/token/key/pass 且值为非空字符串 → "******";
    - 字段名以 _url 结尾、等于 url/webhook_url、或以 _webhook 结尾的字符串
      → 对 query 中的 access_token/key/sign/secret/token 参数值打码；
    - headers/header 子字典中的 authorization/cookie 值整体打码。
    """
    if isinstance(value, dict):
        # headers/header 子字典做特殊处理（authorization/cookie 整体打码），支持任意层级
        if key is not None and key.lower() in ("headers", "header"):
            return _mask_headers(value)
        result: Dict[str, Any] = {}
        for k, v in value.items():
            result[k] = mask_sensitive_config(v, k)
        return result

    if isinstance(value, list):
        return [mask_sensitive_config(item, key) for item in value]

    if not isinstance(value, str):
        return value

    kl = (key or "").lower()

    # 整体打码：字段名本身敏感
    if value and _is_sensitive_key(kl):
        # URL 型敏感字段（如 webhook_url?access_token=）保留结构只打码参数
        if kl.endswith("_url") or kl.endswith("url") or kl.endswith("_webhook") or kl == "webhook":
            return _mask_url(value)
        return MASK

    # URL 型字段：对 query 敏感参数打码
    if kl.endswith("_url") or kl == "url" or kl.endswith("_webhook") or kl == "webhook_url":
        return _mask_url(value)

    return value


def _mask_headers(headers: Any) -> Any:
    """headers 子字典：authorization/cookie 等值整体打码"""
    if not isinstance(headers, dict):
        return headers
    masked: Dict[str, Any] = {}
    for k, v in headers.items():
        if isinstance(v, str) and k.lower() in SENSITIVE_HEADER_NAMES:
            masked[k] = MASK
        else:
            masked[k] = mask_sensitive_config(v, k)
    return masked


def mask_channel_config(config: Any) -> Dict[str, Any]:
    """对整份通道配置做递归脱敏，返回可直接序列化的 dict"""
    if not isinstance(config, dict):
        return {}
    masked = mask_sensitive_config(config)
    return masked if isinstance(masked, dict) else {}


class NotificationChannelCreate(BaseModel):
    """创建通知渠道请求"""

    name: str = Field(..., description="通道名称", min_length=1, max_length=100)
    channel_type: str = Field(..., description="通道类型: email/dingtalk/wechat/feishu/webhook/speak")
    config: Dict[str, Any] = Field(
        ...,
        description=(
            "通道配置字典。更新时（NotificationChannelUpdate）语义如下："
            "字段值为 null、空字符串或 \"******\" 表示保留原值；"
            "值为 \"__DELETE__\" 表示删除该字段；其余值直接覆盖。"
        ),
    )
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
    config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "通道配置（增量合并）。值为 null、空字符串或 \"******\" 的字段保留原值；"
            "值为 \"__DELETE__\" 的字段会被删除；其余字段直接覆盖。"
            "嵌套 dict（如 webhook 的 headers）递归应用同样规则。"
        ),
    )
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
    config: Dict[str, Any] = Field(..., description="脱敏后的通道配置（敏感值显示为 ******）")
    is_active: bool = Field(..., description="是否启用")
    config_error: Optional[str] = Field(
        default=None, description="配置解密/读取失败时的提示；此时 config 为空对象"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_masked(cls, obj: Any) -> "NotificationChannelResponse":
        """从 ORM 对象构建响应并进行递归敏感数据脱敏（解密失败时返回空配置 + config_error）"""
        import json
        from loguru import logger
        from app.utils.encryption import decrypt_password

        config: Dict[str, Any] = {}
        config_error: Optional[str] = None
        try:
            decrypted = decrypt_password(obj.config_json)
            parsed = json.loads(decrypted)
            if isinstance(parsed, dict):
                config = parsed
        except Exception as e:
            logger.warning(f"渠道配置解密失败 (ID={getattr(obj, 'id', None)}): {e}")
            config_error = "渠道配置解密失败，请重新保存该渠道"
            config = {}

        masked_config = mask_channel_config(config)

        return cls(
            id=obj.id,
            name=obj.name,
            channel_type=obj.channel_type,
            config=masked_config,
            is_active=obj.is_active,
            config_error=config_error,
            created_at=obj.created_at,
            updated_at=obj.updated_at
        )