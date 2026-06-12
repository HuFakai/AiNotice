# -*- coding: utf-8 -*-
"""
模拟小米设备控制服务
用于在MiService库不可用时提供基本的API测试功能
"""

import asyncio
import json
import time
import uuid
from typing import List, Optional, Dict, Any
from loguru import logger

from app.config import get_settings
from app.models.speak import DeviceInfo


class MockMiService:
    """模拟小米设备控制服务类"""

    def __init__(self):
        self.settings = get_settings()
        self._devices_cache: Dict[str, DeviceInfo] = {}
        self._is_initialized = False

        # 模拟设备数据
        self._mock_devices = [
            {"did": "mock_device_001", "name": "客厅小爱音箱", "model": "L06A", "isOnline": True, "location": "living_room"},
            {"did": "mock_device_002", "name": "卧室小爱音箱", "model": "L05G", "isOnline": True, "location": "bedroom"},
            {"did": "mock_device_003", "name": "书房小爱音箱", "model": "L15A", "isOnline": False, "location": "study"},
        ]

    async def _initialize(self):
        """初始化服务"""
        if not self._is_initialized:
            logger.info("初始化模拟小米服务...")
            # 模拟登录延迟
            await asyncio.sleep(0.5)

            # 检查配置
            if not self.settings.mi_user or not self.settings.mi_pass:
                logger.warning("小米账户配置为空，使用模拟数据")
            else:
                logger.info(f"模拟登录小米账户: {self.settings.mi_user}")

            self._is_initialized = True
            logger.success("模拟小米服务初始化完成")

    async def get_devices(self, force_refresh: bool = False) -> List[DeviceInfo]:
        """
        获取设备列表

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            设备信息列表
        """
        await self._initialize()

        if force_refresh or not self._devices_cache:
            logger.info("获取设备列表...")
            # 模拟网络延迟
            await asyncio.sleep(1.0)

            devices = []
            self._devices_cache.clear()

            for device_data in self._mock_devices:
                device_info = DeviceInfo(
                    device_id=device_data["did"],
                    name=device_data["name"],
                    model=device_data["model"],
                    status="online" if device_data["isOnline"] else "offline",
                    volume=80,  # 默认音量
                    location=device_data.get("location"),
                    last_seen=time.strftime("%Y-%m-%d %H:%M:%S") if device_data["isOnline"] else None,
                )
                devices.append(device_info)
                self._devices_cache[device_info.device_id] = device_info

            logger.info(f"获取到 {len(devices)} 个模拟设备")
            return devices

        return list(self._devices_cache.values())

    async def get_device_by_id(self, device_id: str) -> Optional[DeviceInfo]:
        """
        根据设备ID获取设备信息

        Args:
            device_id: 设备ID

        Returns:
            设备信息或None
        """
        devices = await self.get_devices()
        return next((device for device in devices if device.device_id == device_id), None)

    async def speak_text(self, text: str, device_id: Optional[str] = None, volume: int = 80) -> Dict[str, Any]:
        """
        模拟让小爱音箱播放文字内容

        Args:
            text: 要播放的文字
            device_id: 设备ID，如果不指定则使用第一个可用设备
            volume: 音量大小(0-100)

        Returns:
            播放结果
        """
        try:
            await self._initialize()

            # 获取目标设备
            if device_id:
                device = await self.get_device_by_id(device_id)
                if not device:
                    raise ValueError(f"设备 {device_id} 不存在")
            else:
                devices = await self.get_devices()
                online_devices = [d for d in devices if d.status == "online"]
                if not online_devices:
                    raise ValueError("没有找到在线的小爱音箱设备")
                device = online_devices[0]  # 使用第一个在线设备

            # 检查设备状态
            if device.status != "online":
                raise ValueError(f"设备 {device.device_id} 不在线")

            # 生成任务ID
            task_id = str(uuid.uuid4())

            # 模拟播放过程
            logger.info(f"模拟设备 {device.name} 开始播放: {text[:50]}...")

            # 模拟播放延迟
            await asyncio.sleep(0.2)

            # 模拟成功播放
            logger.success(f"模拟播放成功: {device.name}")

            return {
                "success": True,
                "task_id": task_id,
                "device_id": device.device_id,
                "device_name": device.name,
                "text": text,
                "volume": volume,
                "result": "模拟播放成功",
            }

        except Exception as e:
            logger.error(f"模拟播放失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}

    async def stop_speak(self, device_id: str) -> Dict[str, Any]:
        """
        模拟停止播放

        Args:
            device_id: 设备ID

        Returns:
            操作结果
        """
        try:
            await self._initialize()

            device = await self.get_device_by_id(device_id)
            if not device:
                raise ValueError(f"设备 {device_id} 不存在")

            # 模拟停止操作
            logger.info(f"模拟设备 {device.name} 停止播放")
            await asyncio.sleep(0.1)

            return {"success": True, "device_id": device_id, "result": "模拟停止成功"}

        except Exception as e:
            logger.error(f"模拟停止播放失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}

    async def set_volume(self, device_id: str, volume: int) -> Dict[str, Any]:
        """
        模拟设置设备音量

        Args:
            device_id: 设备ID
            volume: 音量(0-100)

        Returns:
            操作结果
        """
        try:
            await self._initialize()

            device = await self.get_device_by_id(device_id)
            if not device:
                raise ValueError(f"设备 {device_id} 不存在")

            # 模拟设置音量
            logger.info(f"模拟设备 {device.name} 音量设置为 {volume}")
            await asyncio.sleep(0.1)

            # 更新缓存中的音量
            if device_id in self._devices_cache:
                self._devices_cache[device_id].volume = volume

            return {"success": True, "device_id": device_id, "volume": volume, "result": "模拟音量设置成功"}

        except Exception as e:
            logger.error(f"模拟设置音量失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}


class MiServiceLiteWrapper:
    """
    基于mi-service-lite思路的小米服务封装
    如果需要真实的小米服务，可以在这里实现
    """

    def __init__(self):
        self.settings = get_settings()
        self._initialized = False

    async def _get_real_mi_service(self):
        """获取真实的小米服务实例（待实现）"""
        # 这里可以实现真实的小米服务连接
        # 参考mi-service-lite的实现方式
        logger.info("真实小米服务连接功能待实现")
        return None

    async def get_devices(self, force_refresh: bool = False) -> List[DeviceInfo]:
        """获取设备列表（真实实现）"""
        # TODO: 实现真实的设备获取逻辑
        logger.warning("使用模拟服务，如需真实设备请实现真实的小米服务连接")
        mock_service = MockMiService()
        return await mock_service.get_devices(force_refresh)

    async def speak_text(self, text: str, device_id: Optional[str] = None, volume: int = 80) -> Dict[str, Any]:
        """播放文字（真实实现）"""
        # TODO: 实现真实的播放逻辑
        logger.warning("使用模拟播放，如需真实播放请实现真实的小米服务连接")
        mock_service = MockMiService()
        return await mock_service.speak_text(text, device_id, volume)


# 全局实例 - 使用模拟服务
mi_service_wrapper = MockMiService()

# 如果需要真实服务，可以取消注释下面的行
# mi_service_wrapper = MiServiceLiteWrapper()
