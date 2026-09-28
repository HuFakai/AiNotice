# -*- coding: utf-8 -*-
"""
小米设备控制服务封装
基于MiService库实现小爱音箱控制功能
"""

import asyncio
import json
import time
import uuid
import ssl
import aiohttp
from typing import List, Optional, Dict, Any
from loguru import logger

# 尝试导入MiService，如果失败则使用模拟服务
try:
    from miservice import MiIOService, MiAccount, MiNAService

    MISERVICE_AVAILABLE = True
    logger.info("MiService库可用，将使用真实的小米服务")
except ImportError:
    # 创建虚拟类用于类型注解
    class MiIOService:
        pass

    class MiAccount:
        pass

    class MiNAService:
        pass

    MISERVICE_AVAILABLE = False
    logger.warning("MiService库不可用，将使用模拟服务")

from app.config import get_settings
from app.schemas.speak import DeviceInfo


class MiServiceWrapper:
    """小米设备控制服务封装类"""

    def __init__(self):
        self.settings = get_settings()
        self._mi_service: Optional[MiIOService] = None
        self._mi_account: Optional[MiAccount] = None
        self._mina_service: Optional[MiNAService] = None
        # MiNA deviceId 与 MiIO did 的映射（MiNA ubus 需要 MiNA id，MiIO 操作用 did）
        self._mina_did_map: Dict[str, str] = {}
        self._devices_cache: Dict[str, DeviceInfo] = {}
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 缓存5分钟
        self._use_mock = not MISERVICE_AVAILABLE
        # 动态认证参数
        self._custom_auth: Optional[Dict[str, str]] = None

        if self._use_mock:
            # 导入并初始化模拟服务
            from app.utils.mock_mi_service import MockMiService

            self._mock_service = MockMiService()
            logger.info("使用模拟小米服务")
        else:
            logger.info("使用真实小米服务")
    def set_custom_auth(
        self, username: str, password: str, device_id: str = None, user_id: str = None, pass_token: str = None
    ):
        """设置自定义认证信息"""
        # 确保先关闭旧的 session 以及 connector，防止连接和会话泄漏
        if self._mi_account and hasattr(self._mi_account, 'session') and self._mi_account.session:
            try:
                session = self._mi_account.session
                connector = getattr(session, 'connector', None)
                
                async def _async_close():
                    try:
                        # 强行关闭未被第三方库释放的 acquired 连接，防止连接泄露警告
                        if connector and hasattr(connector, '_acquired') and connector._acquired:
                            for conn in list(connector._acquired):
                                try:
                                    conn.close()
                                except Exception:
                                    pass
                            try:
                                connector._acquired.clear()
                            except Exception:
                                pass
                        await session.close()
                        if connector:
                            await connector.close()
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.warning(f"异步关闭旧 session/connector 异常: {e}")
                
                loop = asyncio.get_running_loop()
                loop.create_task(_async_close())
            except RuntimeError:
                pass
            except Exception as e:
                logger.warning(f"调度关闭旧 session 异常: {e}")

        self._custom_auth = {
            "username": username,
            "password": password,
            "device_id": device_id,
            "user_id": user_id,
            "pass_token": pass_token,
        }
        # 清除缓存的服务实例，强制重新创建
        self._mi_service = None
        self._mi_account = None
        self._mina_service = None
        self._mina_did_map = {}
        self._devices_cache.clear()
        logger.info(f"设置自定义认证信息: {username}")

    def clear_custom_auth(self):
        """清除自定义认证信息"""
        self._custom_auth = None
        # 清除缓存的服务实例，强制重新创建
        # 清除缓存的服务实例，强制重新创建，同时关闭 session 和 connector
        if self._mi_account and hasattr(self._mi_account, 'session') and self._mi_account.session:
            try:
                session = self._mi_account.session
                connector = getattr(session, 'connector', None)
                
                async def _async_close():
                    try:
                        # 强行关闭未被第三方库释放的 acquired 连接，防止连接泄露警告
                        if connector and hasattr(connector, '_acquired') and connector._acquired:
                            for conn in list(connector._acquired):
                                try:
                                    conn.close()
                                except Exception:
                                    pass
                            try:
                                connector._acquired.clear()
                            except Exception:
                                pass
                        await session.close()
                        if connector:
                            await connector.close()
                        await asyncio.sleep(0.1)
                    except Exception:
                        pass
                
                loop = asyncio.get_running_loop()
                loop.create_task(_async_close())
            except RuntimeError:
                pass
        self._mi_service = None
        self._mi_account = None
        self._mina_service = None
        self._mina_did_map = {}
        self._devices_cache.clear()
        logger.info("清除自定义认证信息")

    async def close(self):
        """异步关闭 aiohttp session 以及自定义的 connector"""
        if self._mi_account and hasattr(self._mi_account, 'session') and self._mi_account.session:
            try:
                # 获取关联 of connector
                connector = getattr(self._mi_account.session, 'connector', None)
                # 强行关闭未被第三方库释放的 acquired 连接，防止 "Unclosed client session" 警告
                if connector and hasattr(connector, '_acquired') and connector._acquired:
                    for conn in list(connector._acquired):
                        try:
                            conn.close()
                        except Exception:
                            pass
                    try:
                        connector._acquired.clear()
                    except Exception:
                        pass
                await self._mi_account.session.close()
                if connector:
                    await connector.close()
                # 极其重要：等待 100ms 允许 asyncio 循环迭代并彻底释放底层连接句柄，防止抛出警告
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"关闭 session/connector 异常: {e}")
        self._mi_service = None
        self._mi_account = None
        self._mina_service = None
        self._devices_cache.clear()

    async def _get_mina_service(self) -> MiNAService:
        """获取 MiNAService 实例（小爱音箱原生 API：TTS/URL播放/音量/停止，走 mina 通道）"""
        if self._mina_service is None:
            await self._get_mi_service()  # 确保 MiAccount 已构建
            self._mina_service = MiNAService(self._mi_account)
            # 构建 miotDID -> MiNA deviceID 映射：
            # 平台设备表存的是 MiIO did（来自 miio device_list），而 MiNA ubus
            # 只认 MiNA 的 deviceID，需要转换（此前直接传 did 导致 invalid admin）
            try:
                data = await self._mina_service.device_list()
                items = data.get("devices") if isinstance(data, dict) else (data or [])
                self._mina_did_map = {
                    str(item.get("miotDID")): item.get("deviceID")
                    for item in (items or [])
                    if item.get("miotDID") and item.get("deviceID")
                }
            except Exception as e:
                logger.warning(f"构建 MiNA 设备映射失败（后续按原ID尝试）: {type(e).__name__}: {e}")
                self._mina_did_map = {}
        return self._mina_service

    def _resolve_mina_device_id(self, device_id: str) -> str:
        """把 MiIO did 解析为 MiNA deviceID（无映射时原样返回）"""
        return self._mina_did_map.get(str(device_id), device_id)

    async def _get_mi_service(self) -> MiIOService:
        """获取MiIOService实例"""
        if self._mi_service is None:
            try:
                # 创建账户和服务实例
                if self._mi_account is None:
                    # 只有在有自定义认证信息时才创建MiAccount
                    if self._custom_auth:
                        # 使用自定义认证信息，直接传递给MiAccount而不设置环境变量
                        # 创建账户时传递认证信息，不使用token_store文件
                        # 创建SSL上下文，跳过证书验证
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        
                        # 创建aiohttp连接器，使用自定义SSL上下文
                        connector = aiohttp.TCPConnector(ssl=ssl_context)
                        session = aiohttp.ClientSession(connector=connector)
                        
                        self._mi_account = MiAccount(
                            session=session,  # 使用自定义session
                            username=self._custom_auth["username"],
                            password=self._custom_auth["password"],
                            token_store=None,  # 不使用文件存储token
                        )

                        # 如果有认证令牌信息，设置到账户中
                        if (
                            self._custom_auth.get("device_id")
                            and self._custom_auth.get("user_id")
                            and self._custom_auth.get("pass_token")
                        ):
                            # 直接设置token信息到MiAccount实例，确保所有值都是字符串
                            self._mi_account.token = {
                                "deviceId": str(self._custom_auth["device_id"]),
                                "userId": str(self._custom_auth["user_id"]),
                                "passToken": str(self._custom_auth["pass_token"]),
                            }

                        logger.info(f"使用自定义认证信息创建MiAccount: {self._custom_auth['username']}")
                    else:
                        # 没有认证信息时，不创建MiAccount
                        raise ValueError("没有可用的小米账号认证信息，请先添加小米账号")

                # 创建MiIOService
                self._mi_service = MiIOService(self._mi_account)
                logger.info("MiIOService初始化成功")
            except Exception as e:
                # 如果初始化失败，确保关闭session
                if self._mi_account and hasattr(self._mi_account, 'session') and self._mi_account.session:
                    await self._mi_account.session.close()
                logger.error(f"MiIOService初始化失败: {e}")
                raise
        return self._mi_service

    async def get_devices(self, force_refresh: bool = False) -> List[DeviceInfo]:
        """
        获取设备列表

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            设备信息列表
        """
        # 如果使用模拟服务
        if self._use_mock:
            return await self._mock_service.get_devices(force_refresh)

        # 真实服务逻辑
        current_time = time.time()

        # 检查缓存是否有效
        if not force_refresh and self._devices_cache and (current_time - self._cache_timestamp) < self._cache_ttl:
            logger.debug("使用缓存的设备列表")
            return list(self._devices_cache.values())

        try:
            mi_service = await self._get_mi_service()

            # 调用异步方法获取设备列表
            devices_data = await mi_service.device_list()

            devices = []
            self._devices_cache.clear()

            for device_data in devices_data:
                # 只处理小爱音箱相关设备
                if self._is_xiaoai_device(device_data):
                    device_info = self._parse_device_info(device_data)
                    devices.append(device_info)
                    self._devices_cache[device_info.device_id] = device_info

            self._cache_timestamp = current_time
            logger.info(f"获取到 {len(devices)} 个小爱音箱设备")
            return devices

        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            raise

    async def get_device_by_id(self, device_id: str) -> Optional[DeviceInfo]:
        """
        根据设备ID获取设备信息

        Args:
            device_id: 设备ID

        Returns:
            设备信息或None
        """
        if self._use_mock:
            return await self._mock_service.get_device_by_id(device_id)

        devices = await self.get_devices()
        return next((device for device in devices if device.device_id == device_id), None)

    async def speak_text(self, text: str, device_id: Optional[str] = None, volume: int = 80) -> Dict[str, Any]:
        """
        让小爱音箱播放文字内容

        Args:
            text: 要播放的文字
            device_id: 设备ID，如果不指定则使用第一个可用设备
            volume: 音量大小(0-100)

        Returns:
            播放结果
        """
        if self._use_mock:
            return await self._mock_service.speak_text(text, device_id, volume)

        try:
            # 获取目标设备
            if device_id:
                # 对于指定的device_id，直接使用，不再验证设备是否存在
                # 这避免了不必要的get_devices()调用
                target_device_id = device_id
                target_device_name = f"设备_{device_id}"
            else:
                devices = await self.get_devices()
                if not devices:
                    raise ValueError("没有找到可用的小爱音箱设备")
                device = devices[0]  # 使用第一个设备
                target_device_id = device.device_id
                target_device_name = device.name

            mina = await self._get_mina_service()

            # 生成任务ID
            task_id = str(uuid.uuid4())

            # 执行TTS播放：优先走 MiNA 原生通道（text_to_speech，小爱音箱官方路径），
            # 失败时回退到 MIoT action（siid=5 播放服务 aiid=1 TTS 动作）。
            # 参考：Yonsm/MiService 的 MiNAService 与 Do1e/mijia-api 的实现。
            mina_ok = False
            try:
                mina_ok = await mina.text_to_speech(self._resolve_mina_device_id(target_device_id), text)
            except Exception as mina_err:
                logger.warning(f"MiNA text_to_speech 失败: {type(mina_err).__name__}: {mina_err}，回退 MIoT")

            if mina_ok:
                result = {"mina": True, "method": "text_to_speech"}
            else:
                mi_service = await self._get_mi_service()
                result = await mi_service.miot_action(
                    target_device_id,
                    {"siid": 5, "aiid": 1},
                    [text],
                )

            logger.info(f"设备 {target_device_id} 开始播放: {text[:50]}...")

            return {
                "success": True,
                "task_id": task_id,
                "device_id": target_device_id,
                "device_name": target_device_name,
                "text": text,
                "volume": volume,
                "result": result,
            }

        except Exception as e:
            logger.error(f"播放失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}

    async def play_url(self, device_id: str, url: str) -> Dict[str, Any]:
        """让小爱音箱播放在线音频 URL（MiNA play_by_url；LX04/LX05/X08A 等型号
        由 MiNAService 自动切换 player_play_music 通道）"""
        if self._use_mock:
            return {"success": True, "device_id": device_id, "url": url}
        try:
            mina = await self._get_mina_service()
            ok = await mina.play_by_url(self._resolve_mina_device_id(device_id), url)
            if ok:
                logger.info(f"设备 {device_id} 开始播放音频: {url[:60]}")
                return {"success": True, "device_id": device_id, "url": url, "method": "play_by_url"}
            return {"success": False, "error": "设备返回播放失败", "device_id": device_id}
        except Exception as e:
            logger.error(f"播放URL失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}

    async def stop_speak(self, device_id: str) -> Dict[str, Any]:
        """
        停止播放

        Args:
            device_id: 设备ID

        Returns:
            操作结果
        """
        if self._use_mock:
            return await self._mock_service.stop_speak(device_id)

        try:
            # 对于指定的device_id，直接使用，不再验证设备是否存在
            # 这避免了不必要的get_devices()调用
            mina = await self._get_mina_service()
            stopped = False
            try:
                stopped = await mina.player_stop(self._resolve_mina_device_id(device_id))
            except Exception as mina_err:
                logger.warning(f"MiNA player_stop 失败: {type(mina_err).__name__}: {mina_err}，回退 MIoT")

            if not stopped:
                mi_service = await self._get_mi_service()
                # siid=3为播放控制服务，aiid=1为暂停动作
                result = await mi_service.miot_action(device_id, "3-1", [])
            else:
                result = {"mina": True, "method": "player_stop"}

            logger.info(f"设备 {device_id} 停止播放")

            return {"success": True, "device_id": device_id, "result": result}

        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return {"success": False, "error": str(e), "device_id": device_id}

    async def set_volume(self, device_id: str, volume: int, retry_count: int = 3) -> Dict[str, Any]:
        """设置设备音量
        
        Args:
            device_id: 设备ID
            volume: 音量大小(0-100)
            retry_count: 重试次数
            
        Returns:
            操作结果
        """
        if self._use_mock:
            return await self._mock_service.set_volume(device_id, volume)
            
        # 验证音量范围
        if not 0 <= volume <= 100:
            return {
                "success": False,
                "error": f"音量值 {volume} 超出范围 [0-100]",
                "device_id": device_id
            }
            
        last_error = None
        
        for attempt in range(retry_count):
            try:
                # 对于指定的device_id，直接使用，不再验证设备是否存在
                # 这避免了不必要的get_devices()调用
                # 优先走 MiNA 原生 player_set_volume（ubus mediaplayer，音箱官方通道），
                # 失败回退 MIoT 属性设置（siid=2 音频服务 piid=1 音量）
                volume_ok = False
                try:
                    mina = await self._get_mina_service()
                    volume_ok = await mina.player_set_volume(self._resolve_mina_device_id(device_id), volume)
                except Exception as mina_err:
                    logger.warning(f"MiNA player_set_volume 失败: {type(mina_err).__name__}: {mina_err}，回退 MIoT")

                if volume_ok:
                    result = 0
                else:
                    mi_service = await self._get_mi_service()
                    result = await mi_service.miot_set_prop(device_id, (2, 1), volume)

                if result == 0:
                    logger.info(f"设备 {device_id} 音量设置为 {volume} (尝试 {attempt + 1}/{retry_count})")
                    return {
                        "success": True,
                        "device_id": device_id,
                        "device_name": device_id,  # 使用device_id作为设备名称
                        "volume": volume,
                        "result": result,
                        "attempts": attempt + 1
                    }
                else:
                    last_error = f"设置音量失败，错误码: {result}"
                    logger.warning(f"设备 {device_id} 设置音量失败 (尝试 {attempt + 1}/{retry_count}): {last_error}")
                    
                    # 如果不是最后一次尝试，等待一段时间再重试
                    if attempt < retry_count - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # 递增等待时间
                        
            except Exception as e:
                last_error = str(e)
                logger.error(f"设备 {device_id} 设置音量异常 (尝试 {attempt + 1}/{retry_count}): {e}")
                
                # 如果不是最后一次尝试，等待一段时间再重试
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 递增等待时间
        
        # 所有尝试都失败了
        return {
            "success": False,
            "error": f"设置音量失败，已重试 {retry_count} 次。最后错误: {last_error}",
            "device_id": device_id,
            "attempts": retry_count
        }

    async def _set_volume(self, mi_service: MiIOService, device_id: str, volume: int):
        """内部设置设备音量方法"""
        try:
            # 使用MIoT协议设置音量
            # siid=2为音频服务，piid=1为音量属性
            result = await mi_service.miot_set_prop(device_id, (2, 1), volume)
            if result == 0:
                logger.debug(f"设备 {device_id} 音量设置为 {volume}")
            else:
                logger.warning(f"设置音量返回错误码: {result}")
        except Exception as e:
            logger.warning(f"设置音量失败: {e}")

    def _is_xiaoai_device(self, device_data: Dict) -> bool:
        """判断是否为小爱音箱设备"""
        device_name = device_data.get("name", "").lower()
        device_model = device_data.get("model", "").lower()

        # 小爱音箱关键词
        xiaoai_keywords = ["小爱音箱", "xiaoai", "xiaomi", "音箱", "speaker", "miai", "小爱", "ai speaker", "smart speaker"]

        return any(keyword in device_name or keyword in device_model for keyword in xiaoai_keywords)

    def _parse_device_info(self, device_data: Dict) -> DeviceInfo:
        """解析设备信息"""
        # 处理真实的小米设备数据格式
        is_online = device_data.get("isOnline", True)  # 默认在线
        if isinstance(is_online, str):
            is_online = is_online.lower() == "true"

        return DeviceInfo(
            device_id=device_data.get("did", ""),
            name=device_data.get("name", "未知设备"),
            model=device_data.get("model", ""),
            status="online" if is_online else "offline",
            volume=80,  # 默认音量，实际音量需要单独查询
            location=device_data.get("location"),
            last_seen=device_data.get("updateTime") or device_data.get("last_ip_time"),
        )


# 全局实例
mi_service_wrapper = MiServiceWrapper()
