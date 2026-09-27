# -*- coding: utf-8 -*-
"""
统一消息推送验证模式
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class NotificationSendRequest(BaseModel):
    """统一通知发送请求"""

    channel_id: Optional[int] = Field(default=None, description="已配置的通道ID（与 channel_type 二选一）")
    channel_type: Optional[str] = Field(default=None, description="通道类型: email/dingtalk/wechat/feishu/webhook/speak")
    config: Optional[Dict[str, Any]] = Field(default=None, description="临时通道配置（适用于 ad-hoc 发送）")
    
    title: Optional[str] = Field(default=None, description="消息标题（如邮件主题，部分通道支持）", max_length=200)
    content: str = Field(..., description="推送的消息正文内容", min_length=1)
    recipient: Optional[str] = Field(default=None, description="具体接收对象（如特定邮箱、特定音箱设备ID，不指定则使用通道默认值）")
    
    extra: Optional[Dict[str, Any]] = Field(default=None, description="其它通道特定参数（如小爱音箱的 volume / endvolume）")

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_types = ["email", "dingtalk", "wechat", "feishu", "webhook", "speak"]
        if v not in valid_types:
            raise ValueError(f"无效的通道类型. 必须是以下之一: {', '.join(valid_types)}")
        return v


class NotificationSendResponse(BaseModel):
    """统一通知发送响应"""

    success: bool = Field(..., description="是否发送成功")
    message: str = Field(..., description="状态或响应说明")
    log_id: Optional[int] = Field(default=None, description="生成的通知日志记录ID")
    detail: Optional[Any] = Field(default=None, description="底层通道返回的详细回执")
