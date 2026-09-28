# -*- coding: utf-8 -*-
"""
语音播放相关数据模型（Pydantic Schema）
定义语音播放请求和响应的数据结构

注：本文件由 app/models/speak.py 迁移而来。它只包含 Pydantic
请求/响应模型、与数据库无关，因此放在 schemas 包中。
"""

from typing import Optional, Literal, Union, List
from pydantic import BaseModel, Field, validator, root_validator


class SpeakRequest(BaseModel):
    """语音播放请求模型"""

    text: Optional[str] = Field(None, min_length=1, max_length=500, description="要播放的文字内容（与 url 二选一）")
    url: Optional[str] = Field(None, max_length=1000, description="在线音频URL（提供时播放该音频而不是TTS）")
    device_id: Optional[Union[str, List[str]]] = Field(default=None, description="指定设备ID，支持单个设备ID(字符串)或多个设备ID(数组)，不指定则使用默认设备")
    volume: Optional[int] = Field(default=None, ge=0, le=100, description="播报时音量大小(0-100)，不指定则不调整音量")
    endvolume: Optional[int] = Field(default=None, ge=0, le=100, description="播报完成后恢复的音量(0-100)，不指定则不恢复音量")
    speed: Optional[float] = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率(0.5-2.0)")
    voice_type: Optional[Literal["male", "female", "child"]] = Field(default="female", description="音色类型")

    @validator("url")
    def validate_url(cls, v, values):
        """URL 必须是 http/https"""
        if v is not None and not v.lower().startswith(("http://", "https://")):
            raise ValueError("url 必须以 http:// 或 https:// 开头")
        return v

    @root_validator(skip_on_failure=True)
    def validate_text_or_url(cls, values):
        """text 与 url 至少提供一个"""
        text = (values.get("text") or "").strip()
        if not text and not values.get("url"):
            raise ValueError("text 与 url 必须至少提供一个")
        if text and not values.get("url"):
            values["text"] = text
        return values


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
