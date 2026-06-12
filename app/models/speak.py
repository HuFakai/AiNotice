# -*- coding: utf-8 -*-
"""
语音播放相关数据模型
定义语音播放请求和响应的数据结构
"""

from typing import Optional, Literal, Union, List
from pydantic import BaseModel, Field, validator


class SpeakRequest(BaseModel):
    """语音播放请求模型"""

    text: str = Field(..., min_length=1, max_length=500, description="要播放的文字内容")
    device_id: Optional[Union[str, List[str]]] = Field(default=None, description="指定设备ID，支持单个设备ID(字符串)或多个设备ID(数组)，不指定则使用默认设备")
    volume: Optional[int] = Field(default=None, ge=0, le=100, description="播报时音量大小(0-100)，不指定则不调整音量")
    endvolume: Optional[int] = Field(default=None, ge=0, le=100, description="播报完成后恢复的音量(0-100)，不指定则不恢复音量")
    speed: Optional[float] = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率(0.5-2.0)")
    voice_type: Optional[Literal["male", "female", "child"]] = Field(default="female", description="音色类型")

    @validator("text")
    def validate_text(cls, v):
        """验证文字内容"""
        if not v.strip():
            raise ValueError("文字内容不能为空")
        return v.strip()


class SpeakResponse(BaseModel):
    """语音播放响应模型"""

    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="响应消息")
    task_id: Optional[Union[str, List[str]]] = Field(default=None, description="任务ID，单个任务返回字符串，多个任务返回字符串列表")
    device_id: Optional[Union[str, List[str]]] = Field(default=None, description="实际使用的设备ID，单个或多个")
    estimated_duration: Optional[float] = Field(default=None, description="预估播放时长(秒)")


class SpeakStatus(BaseModel):
    """语音播放状态模型"""

    task_id: str = Field(..., description="任务ID")
    status: Literal["pending", "playing", "completed", "failed"] = Field(..., description="播放状态")
    device_id: str = Field(..., description="设备ID")
    text: str = Field(..., description="播放文字内容")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="播放进度(0-1)")
    start_time: Optional[str] = Field(default=None, description="开始时间")
    end_time: Optional[str] = Field(default=None, description="结束时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    api_log_id: Optional[int] = Field(default=None, description="API调用日志ID")


class DeviceInfo(BaseModel):
    """设备信息模型"""

    device_id: str = Field(..., description="设备ID")
    name: str = Field(..., description="设备名称")
    model: str = Field(..., description="设备型号")
    status: Literal["online", "offline", "unknown"] = Field(..., description="设备状态")
    volume: int = Field(default=80, ge=0, le=100, description="当前音量")
    location: Optional[str] = Field(default=None, description="设备位置")
    last_seen: Optional[str] = Field(default=None, description="最后在线时间")


class DeviceListResponse(BaseModel):
    """设备列表响应模型"""

    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="响应消息")
    devices: list[DeviceInfo] = Field(default=[], description="设备列表")
    total: int = Field(default=0, description="设备总数")
