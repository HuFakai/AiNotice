# -*- coding: utf-8 -*-
"""
用户相关数据模式
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class UserProfile(BaseModel):
    """用户资料"""

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")
    display_name: str = Field(..., description="显示名称")
    is_active: bool = Field(..., description="是否激活")
    is_verified: bool = Field(..., description="是否验证")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """更新资料请求"""

    display_name: Optional[str] = Field(None, description="显示名称", max_length=100)

    class Config:
        json_json_schema_extra = {"example": {"display_name": "新的显示名称"}}


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str = Field(..., description="旧密码", min_length=1)
    new_password: str = Field(..., description="新密码", min_length=8)

    class Config:
        json_json_schema_extra = {"example": {"old_password": "old_password", "new_password": "new_password123"}}


class UserActivityResponse(BaseModel):
    """用户活动响应"""

    id: int = Field(..., description="活动ID")
    activity_type: str = Field(..., description="活动类型")
    activity_description: str = Field(..., description="活动描述")
    resource_type: Optional[str] = Field(None, description="资源类型")
    resource_id: Optional[int] = Field(None, description="资源ID")
    client_ip: Optional[str] = Field(None, description="客户端IP")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    """用户统计响应"""

    device_count: int = Field(..., description="设备数量")
    online_devices: int = Field(..., description="在线设备数")
    api_keys_count: int = Field(..., description="API密钥数量")
    active_api_keys: int = Field(..., description="活跃API密钥数")
    speak_tasks_today: int = Field(..., description="今日语音任务数")
    speak_tasks_month: int = Field(..., description="本月语音任务数")
    total_api_calls: int = Field(..., description="API总调用次数")


class LoginHistoryResponse(BaseModel):
    """登录历史记录响应"""

    id: int = Field(..., description="记录ID")
    login_time: datetime = Field(..., description="登录时间")
    ip_address: str = Field(..., description="IP地址")
    user_agent: Optional[str] = Field(None, description="用户代理")
    location: Optional[str] = Field(None, description="登录位置")
    status: str = Field(..., description="登录状态")
    
    class Config:
        from_attributes = True
