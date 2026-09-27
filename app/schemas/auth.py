# -*- coding: utf-8 -*-
"""
认证相关数据模式
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime


class LoginRequest(BaseModel):
    """登录请求"""

    username_or_email: str = Field(..., description="用户名或邮箱", min_length=1)
    password: str = Field(..., description="密码", min_length=1)

    class Config:
        json_json_schema_extra = {"example": {"username_or_email": "demo@xiaoai-api.com", "password": "Demo123456"}}


class RegisterRequest(BaseModel):
    """注册请求"""

    username: str = Field(..., description="用户名", min_length=3, max_length=50)
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码", min_length=8)
    display_name: Optional[str] = Field(None, description="显示名称", max_length=100)

    @validator("username")
    def validate_username(cls, v):
        """验证用户名格式"""
        if not v.replace("_", "").isalnum():
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v

    class Config:
        json_json_schema_extra = {
            "example": {
                "username": "demo_user",
                "email": "demo@xiaoai-api.com",
                "password": "Demo123456",
                "display_name": "演示用户",
            }
        }


class TokenResponse(BaseModel):
    """令牌响应"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: "UserResponse" = Field(..., description="用户信息")


class UserResponse(BaseModel):
    """用户响应"""

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱地址")
    display_name: str = Field(..., description="显示名称")
    is_active: bool = Field(..., description="是否激活")
    is_verified: bool = Field(..., description="是否验证")
    created_at: datetime = Field(..., description="创建时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")

    class Config:
        from_attributes = True


class CheckUsernameRequest(BaseModel):
    """检查用户名请求"""

    username: str = Field(..., description="用户名", min_length=3, max_length=50)


class CheckEmailRequest(BaseModel):
    """检查邮箱请求"""

    email: EmailStr = Field(..., description="邮箱地址")


class AvailabilityResponse(BaseModel):
    """可用性响应"""

    available: bool = Field(..., description="是否可用")
    message: str = Field(..., description="消息")


class SuccessResponse(BaseModel):
    """成功响应"""

    success: bool = Field(True, description="是否成功")
    message: str = Field(..., description="消息")
    data: Optional[dict] = Field(None, description="附加数据")


class ErrorResponse(BaseModel):
    """错误响应"""

    success: bool = Field(False, description="是否成功")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="错误详情")


# 更新前向引用
TokenResponse.model_rebuild()
