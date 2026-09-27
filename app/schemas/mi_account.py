# -*- coding: utf-8 -*-
"""
小米账户相关的Pydantic模式
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class SyncStatusEnum(str, Enum):
    """同步状态枚举"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class CreateMiAccountRequest(BaseModel):
    """创建小米账户请求"""

    mi_username: str = Field(..., min_length=1, max_length=100, description="小米用户名")
    mi_password: str = Field(..., min_length=6, max_length=100, description="小米密码")
    device_id: str = Field(..., min_length=1, max_length=200, description="设备ID")
    user_id: str = Field(..., min_length=1, max_length=100, description="用户ID")
    pass_token: str = Field(..., min_length=1, description="通行令牌")


class SimplifiedCreateMiAccountRequest(BaseModel):
    """简化的创建小米账户请求 - 只需账号密码"""

    mi_username: str = Field(..., min_length=1, max_length=100, description="小米用户名")
    mi_password: str = Field(..., min_length=6, max_length=100, description="小米密码")

    @validator("mi_username")
    def validate_mi_username(cls, v):
        """验证小米用户名"""
        if not v.strip():
            raise ValueError("小米用户名不能为空")
        return v.strip()

    @validator("mi_password")
    def validate_mi_password(cls, v):
        """验证小米密码"""
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


class UpdateMiAccountRequest(BaseModel):
    """更新小米账户请求"""

    mi_password: Optional[str] = Field(None, min_length=6, max_length=100, description="新的小米密码")
    is_active: Optional[bool] = Field(None, description="是否启用")

    @validator("mi_password")
    def validate_mi_password(cls, v):
        """验证小米密码"""
        if v is not None and len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


class MiAccountResponse(BaseModel):
    """小米账户响应"""

    id: int = Field(..., description="账户ID")
    mi_username: str = Field(..., description="小米用户名")
    mi_device_id: Optional[str] = Field(None, description="小米设备ID")
    mi_user_id: Optional[str] = Field(None, description="小米用户ID")
    is_active: bool = Field(..., description="是否启用")
    sync_status: SyncStatusEnum = Field(..., description="同步状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    device_count: int = Field(0, description="设备数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_sync_at: Optional[datetime] = Field(None, description="最后同步时间")

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @classmethod
    def from_orm(cls, obj):
        """从ORM对象创建响应"""
        return cls(
            id=obj.id,
            mi_username=obj.mi_username,
            mi_device_id=obj.mi_device_id,
            mi_user_id=obj.mi_user_id,
            is_active=obj.is_active,
            sync_status=obj.sync_status,
            error_message=obj.error_message,
            device_count=obj.device_count,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            last_sync_at=obj.last_sync_at,
        )


class MiAccountCreatedResponse(BaseModel):
    """小米账户创建成功响应"""

    id: int = Field(..., description="账户ID")
    mi_username: str = Field(..., description="小米用户名")
    sync_status: SyncStatusEnum = Field(..., description="同步状态")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class MiAccountDetailResponse(BaseModel):
    """小米账户详情响应"""

    id: int = Field(..., description="账户ID")
    mi_username: str = Field(..., description="小米用户名")
    mi_device_id: Optional[str] = Field(None, description="小米设备ID")
    mi_user_id: Optional[str] = Field(None, description="小米用户ID")
    is_active: bool = Field(..., description="是否启用")
    sync_status: SyncStatusEnum = Field(..., description="同步状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    device_count: int = Field(0, description="设备数量")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="设备列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_sync_at: Optional[datetime] = Field(None, description="最后同步时间")

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @classmethod
    def from_orm_with_devices(cls, obj):
        """从ORM对象创建详情响应（包含设备）"""
        devices_data = []
        if obj.devices:
            for device in obj.devices:
                devices_data.append(
                    {
                        "id": device.id,
                        "device_id": device.device_id,
                        "device_name": device.device_name,
                        "device_model": device.device_model,
                        "device_type": device.device_type,
                        "location": device.location,
                        "is_online": device.is_online,
                        "is_favorite": device.is_favorite,
                        "volume": device.volume,
                        "created_at": device.created_at.isoformat() if device.created_at else None,
                        "updated_at": device.updated_at.isoformat() if device.updated_at else None,
                    }
                )

        return cls(
            id=obj.id,
            mi_username=obj.mi_username,
            mi_device_id=obj.mi_device_id,
            mi_user_id=obj.mi_user_id,
            is_active=obj.is_active,
            sync_status=obj.sync_status,
            error_message=obj.error_message,
            device_count=obj.device_count,
            devices=devices_data,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            last_sync_at=obj.last_sync_at,
        )


class TestConnectionRequest(BaseModel):
    """测试连接请求"""

    mi_username: str = Field(..., min_length=1, max_length=100, description="小米用户名")
    mi_password: str = Field(..., min_length=6, max_length=100, description="小米密码")


class TestConnectionResponse(BaseModel):
    """测试连接响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")


class SyncAccountRequest(BaseModel):
    """同步账户请求"""

    account_id: int = Field(..., description="账户ID")


class SyncAccountResponse(BaseModel):
    """同步账户响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")


class MiAccountStatsResponse(BaseModel):
    """小米账户统计响应"""

    total_accounts: int = Field(0, description="总账户数")
    active_accounts: int = Field(0, description="活跃账户数")
    synced_accounts: int = Field(0, description="已同步账户数")
    total_devices: int = Field(0, description="总设备数")
    online_devices: int = Field(0, description="在线设备数")


class AuthenticationTestRequest(BaseModel):
    """认证测试请求"""

    mi_username: str = Field(..., description="小米用户名")
    mi_password: str = Field(..., description="小米密码")


class AuthenticationTestResponse(BaseModel):
    """认证测试响应"""

    success: bool = Field(..., description="认证是否成功")
    message: str = Field(..., description="响应消息")
    auth_data: Optional[Dict[str, str]] = Field(None, description="认证数据")
    device_count: Optional[int] = Field(None, description="发现的设备数量")
    devices_preview: Optional[List[Dict[str, str]]] = Field(None, description="设备预览")


class QrCreateRequest(BaseModel):
    """发起扫码登录请求"""

    name: Optional[str] = Field(None, max_length=100, description="账户备注名（可选，默认用小米用户ID命名）")


class QrCreateResponse(BaseModel):
    """扫码登录会话信息"""

    session_id: str = Field(..., description="扫码会话ID")
    qr_image_url: str = Field(..., description="二维码图片地址（后端代理）")
    login_url: str = Field("", description="备用登录链接（手机浏览器打开）")
    expires_in: int = Field(..., description="二维码有效期（秒）")


class QrStatusResponse(BaseModel):
    """扫码登录轮询状态"""

    status: str = Field(..., description="状态: waiting/confirmed/expired/error")
    message: Optional[str] = Field(None, description="提示信息")
    account_id: Optional[int] = Field(None, description="登录成功后创建的小米账户ID")
    mi_username: Optional[str] = Field(None, description="登录成功后的账户名称")


class DeviceResponse(BaseModel):
    """设备响应"""

    id: int = Field(..., description="设备ID")
    device_id: str = Field(..., description="设备唯一标识")
    device_name: str = Field(..., description="设备名称")
    device_model: Optional[str] = Field(None, description="设备型号")
    device_type: str = Field(..., description="设备类型")
    location: Optional[str] = Field(None, description="设备位置")
    is_online: bool = Field(..., description="是否在线")
    is_favorite: bool = Field(..., description="是否收藏")
    volume: int = Field(..., description="音量级别")
    mi_account_id: int = Field(..., description="关联的小米账户ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}

    @classmethod
    def from_orm(cls, obj):
        """从ORM对象创建响应"""
        return cls(
            id=obj.id,
            device_id=obj.device_id,
            device_name=obj.device_name,
            device_model=obj.device_model,
            device_type=obj.device_type,
            location=obj.location,
            is_online=obj.is_online,
            is_favorite=obj.is_favorite,
            volume=obj.volume,
            mi_account_id=obj.mi_account_id,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
