# -*- coding: utf-8 -*-
"""
语音播放业务逻辑服务
处理语音播放相关的业务逻辑和状态管理
"""

import asyncio
import time
import uuid
from typing import Dict, Optional, List, Set, Tuple, Any
from loguru import logger

from app.schemas.speak import SpeakRequest, SpeakResponse, SpeakStatus, DeviceInfo
from app.models.speak_task import SpeakTask, TaskStatus
from app.utils.mi_service import mi_service_wrapper
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.mi_account_service import MiAccountService
from app.utils.encryption import decrypt_password


def _load_pass_token(stored):
    """读取 pass_token：兼容明文历史数据；加密存储走统一解密（定义见 mi_account_service）"""
    from app.services.mi_account_service import _load_pass_token as _load

    return _load(stored)

# 尝试导入真实MiService
try:
    from miservice import MiAccount as MiSvcAccount, MiIOService as MiSvcMiIOService

    _MISERVICE_AVAILABLE = True
except Exception:  # pragma: no cover
    _MISERVICE_AVAILABLE = False


class SpeakService:
    """语音播放服务类"""

    def __init__(self):
        # 任务状态存储（生产环境应使用Redis）
        self._task_status: Dict[str, SpeakStatus] = {}
        # 任务归属：task_id -> user_id（用于状态/停止接口的越权校验）
        self._task_owner: Dict[str, Optional[int]] = {}
        # 播放队列
        self._play_queue: Dict[str, List[Dict]] = {}
        # 音频播放自动停止守护任务
        self._auto_stop_tasks: Set[asyncio.Task] = set()

    async def speak_text(
        self,
        request: SpeakRequest,
        user_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        api_key_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SpeakResponse:
        """
        执行语音播放

        Args:
            request: 播放请求

        Returns:
            播放响应
        """
        try:
            # 处理设备ID：支持单个设备ID或多个设备ID数组
            device_ids = []
            if request.device_id is None:
                # 未指定设备ID，使用默认设备
                use_user_account = bool(user_id)
                if use_user_account:
                    devices_info = await self.get_devices(user_id, db)
                    if not devices_info:
                        return SpeakResponse(success=False, message="未发现可用的小米设备")
                    device_ids = [devices_info[0].device_id]
                else:
                    devices = await mi_service_wrapper.get_devices()
                    if not devices:
                        return SpeakResponse(success=False, message="没有找到可用的小爱音箱设备")
                    device_ids = [devices[0].device_id]
            elif isinstance(request.device_id, str):
                # 单个设备ID
                device_ids = [request.device_id]
            elif isinstance(request.device_id, list):
                # 多个设备ID
                device_ids = request.device_id
            else:
                return SpeakResponse(success=False, message="设备ID格式错误")

            if not device_ids:
                return SpeakResponse(success=False, message="未指定有效的设备ID")

            # 验证设备ID的有效性
            use_user_account = bool(user_id)
            if use_user_account:
                devices_info = await self.get_devices(user_id, db)
                if not devices_info:
                    return SpeakResponse(success=False, message="未发现可用的小米设备")
                
                valid_device_ids = [d.device_id for d in devices_info]
                invalid_devices = [did for did in device_ids if did not in valid_device_ids]
                if invalid_devices:
                    return SpeakResponse(success=False, message=f"设备 {', '.join(invalid_devices)} 不存在或不可用")
                
                # 获取MiService实例用于播放
                service = await self._get_user_mi_service(user_id)
                if not service:
                    return SpeakResponse(success=False, message="无法获取小米服务实例")
                # 仅用于验证，验证后立即关闭释放资源
                await service.close()
            else:
                # 验证全局设备
                for device_id in device_ids:
                    device = await mi_service_wrapper.get_device_by_id(device_id)
                    if not device:
                        return SpeakResponse(success=False, message=f"设备 {device_id} 不存在或不可用")

            # 为每个设备创建任务
            task_ids = []
            for device_id in device_ids:
                task_id = str(uuid.uuid4())
                task_ids.append(task_id)

                # 创建任务状态
                task_status = SpeakStatus(
                    task_id=task_id,
                    status=TaskStatus.PENDING.value,
                    device_id=device_id,
                    text=request.text,
                    start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                self._task_status[task_id] = task_status
                self._task_owner[task_id] = user_id

                # 记录API调用日志
                if db is not None and user_id is not None:
                    try:
                        # 获取设备名称
                        device_name = None
                        if use_user_account and devices_info:
                            device_info = next(
                                (d for d in devices_info if d.device_id == device_id),
                                None
                            )
                            device_name = device_info.name if device_info else None
                        else:
                            try:
                                device_obj = await mi_service_wrapper.get_device_by_id(device_id)
                                device_name = device_obj.name if device_obj else None
                            except Exception:
                                pass
                        

                        
                        # 将日志ID存储到任务状态中，以便后续更新
                        
                    except Exception as e:
                        logger.error(f"记录API调用日志失败: {e}")

                # 异步执行播放 - 不传递数据库会话，让异步任务创建独立会话
                asyncio.create_task(
                    self._execute_speak_task(
                        task_id,
                        request,
                        device_id,
                        user_id=user_id,
                        db=None,
                        api_key_id=api_key_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            )

            # 估算播放时长（按平均每分钟150字计算）
            estimated_duration = 0 if getattr(request, "url", None) else len(request.text) / 150 * 60 / (request.speed or 1.0)

            # 根据设备数量返回相应的响应
            if len(device_ids) == 1:
                return SpeakResponse(
                    success=True,
                    message="语音播放任务已创建",
                    task_id=task_ids[0],
                    device_id=device_ids[0],
                    estimated_duration=estimated_duration,
                )
            else:
                return SpeakResponse(
                    success=True,
                    message=f"已为{len(device_ids)}个设备创建语音播放任务",
                    task_id=task_ids,
                    device_id=device_ids,
                    estimated_duration=estimated_duration,
                )

        except Exception as e:
            logger.error(f"创建语音播放任务失败: {e}")
            return SpeakResponse(success=False, message=f"创建播放任务失败: {str(e)}")

    async def _execute_speak_task(
        self,
        task_id: str,
        request: SpeakRequest,
        device_id: str,
        user_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        api_key_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        执行语音播放任务

        Args:
            task_id: 任务ID
            request: 播放请求
            device_id: 设备ID
        """
        # 为持久化引入依赖，避免循环导入
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.speak_task import SpeakTask, TaskStatus
        from app.models.device import Device as DeviceModel

        # 创建独立会话
        session: Optional[AsyncSession] = None
        service = None
        try:
            session = db if db is not None else AsyncSessionLocal()

            # 根据字符串device_id找到设备表中的整数ID（限定在当前用户下）
            device_row = None
            if user_id is not None:
                try:
                    result = await session.execute(
                        select(DeviceModel).where(
                            DeviceModel.user_id == user_id, DeviceModel.device_id == device_id
                        )
                    )
                    device_row = result.scalar_one_or_none()
                except Exception as e:
                    logger.warning(f"查询设备ID失败: user_id={user_id}, device_id={device_id}, error={e}")

            device_pk = device_row.id if device_row else None

            # 估算播放时长
            estimated_duration = 0 if getattr(request, "url", None) else len(request.text) / 150 * 60 / (request.speed or 1.0)

            # 先写入任务记录: pending -> playing
            speak_task = None
            if user_id is not None and device_pk is not None:
                speak_task = SpeakTask(
                    user_id=user_id,
                    device_id=device_pk,
                    api_key_id=api_key_id,
                    task_id=task_id,
                    text_content=request.text,
                    status=TaskStatus.PLAYING,  # 在开始执行时即标记为playing
                    estimated_duration=estimated_duration,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
                # 使用模型方法更新开始时间
                speak_task.start()

                session.add(speak_task)
                await session.commit()
            else:
                logger.warning(f"跳过持久化SpeakTask：user_id={user_id}, device_pk={device_pk}")

            # 更新内存状态为播放中
            if task_id in self._task_status:
                self._task_status[task_id].status = TaskStatus.PLAYING.value
                self._task_status[task_id].progress = 0.1

            # 获取服务实例
            use_user_account = bool(user_id)
            if use_user_account:
                if not _MISERVICE_AVAILABLE:
                    result = {"success": False, "error": "MiService库不可用"}
                    if task_id in self._task_status:
                        self._task_status[task_id].status = TaskStatus.FAILED.value
                        self._task_status[task_id].error_message = result["error"]
                        self._task_status[task_id].end_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    # 持久化失败状态
                    if speak_task is not None:
                        speak_task.fail(result["error"])  # type: ignore
                        await session.commit()
                    return

                try:
                    service = await self._get_user_mi_service(user_id, device_id)
                except Exception as e:
                    logger.error(f"获取用户专属MiService失败: {e}")
                    if task_id in self._task_status:
                        self._task_status[task_id].status = TaskStatus.FAILED.value
                        self._task_status[task_id].error_message = str(e)
                        self._task_status[task_id].end_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    # 持久化失败状态
                    if speak_task is not None:
                        speak_task.fail(str(e))  # type: ignore
                        await session.commit()
                    return
            else:
                service = mi_service_wrapper

            # 记录音量控制状态
            volume_set_success = False
            volume_restore_needed = False

            # 步骤1: 如果指定了播报音量，先设置音量
            if request.volume is not None:
                logger.info(f"设置播报音量: 设备={device_id}, 音量={request.volume}")
                try:
                    volume_result = await service.set_volume(device_id, request.volume)
                    if volume_result.get("success", False):
                        volume_set_success = True
                        logger.info(f"播报音量设置成功: {request.volume}")
                        # 等待音量设置生效
                        await asyncio.sleep(1.0)  # 增加等待时间确保音量设置生效
                    else:
                        logger.error(f"设置播报音量失败: {volume_result.get('error')}")
                        # 音量设置失败，但继续播放
                except Exception as e:
                    logger.error(f"设置播报音量异常: {e}")
                    # 音量设置异常，但继续播放

            # 步骤2: 执行语音播放（url 存在时播放在线音频，否则 TTS 文本播报）
            try:
                if getattr(request, "url", None):
                    logger.info(f"开始播放音频URL: 设备={device_id}, url={request.url[:60]}...")
                    result = await service.play_url(device_id, request.url)
                else:
                    logger.info(f"开始语音播放: 设备={device_id}, 内容={request.text[:50]}...")
                    result = await service.speak_text(
                        text=request.text,
                        device_id=device_id,
                        volume=None,  # 不在播放时再次设置音量，因为已经预先设置了
                    )

                # 播放成功且需要恢复音量
                if result.get("success", False) and request.endvolume is not None:
                    volume_restore_needed = True

            except Exception as e:
                logger.error(f"语音播放异常: {e}")
                result = {"success": False, "error": str(e)}

            # 步骤3: 如果播放成功且指定了恢复音量，等待播放完成后恢复音量
            if volume_restore_needed:
                try:
                    # 结束音量前的等待：显式 end_volume_delay 优先，否则按文本长度估算
                    if getattr(request, "end_volume_delay", None) is not None:
                        estimated_duration2 = float(request.end_volume_delay)
                    else:
                        # 使用更保守的估算：每分钟120字，加上额外的缓冲时间
                        estimated_duration2 = max(2.0, len(request.text) / 120 * 60 / (request.speed or 1.0))
                    logger.info(f"等待播放完成，预估时长: {estimated_duration2:.1f}秒")
                    await asyncio.sleep(max(0.0, estimated_duration2))

                    # 恢复音量
                    logger.info(f"恢复音量: 设备={device_id}, 音量={request.endvolume}")
                    restore_result = await service.set_volume(device_id, request.endvolume)
                    if restore_result.get("success", False):
                        logger.info(f"音量恢复成功: {request.endvolume}")
                    else:
                        logger.error(f"恢复音量失败: {restore_result.get('error')}")

                except Exception as e:
                    logger.error(f"恢复音量异常: {e}")
                    # 恢复音量失败不影响整体任务状态

            if result["success"]:
                # 播放成功，更新状态为完成
                if task_id in self._task_status:
                    self._task_status[task_id].status = TaskStatus.COMPLETED.value
                    self._task_status[task_id].progress = 1.0
                    self._task_status[task_id].end_time = time.strftime("%Y-%m-%d %H:%M:%S")

                # 计算实际时长并持久化
                actual_duration = len(request.text) / 150 * 60 / (request.speed or 1.0)
                if speak_task is not None:
                    speak_task.complete(actual_duration=actual_duration)  # type: ignore
                    await session.commit()
                

            else:
                # 播放失败
                error_msg = result.get("error", "播放失败")
                if task_id in self._task_status:
                    self._task_status[task_id].status = TaskStatus.FAILED.value
                    self._task_status[task_id].error_message = error_msg
                    self._task_status[task_id].end_time = time.strftime("%Y-%m-%d %H:%M:%S")

                if speak_task is not None:
                    speak_task.fail(error_msg)  # type: ignore
                    await session.commit()


        except Exception as e:
            logger.error(f"执行语音播放任务异常: {e}")
            # 尝试持久化失败状态
            try:
                if speak_task is not None:
                    speak_task.fail(str(e))  # type: ignore
                    await session.commit()
            except Exception as e2:
                logger.error(f"持久化失败状态时发生异常: {e2}")
        finally:
            if session is not None and db is None:
                await session.close()
            # 如果是临时创建的专属服务实例，需要手动关闭以释放 session 资源
            if use_user_account and service is not None:
                try:
                    logger.info("正在清理专属服务实例 session...")
                    await service.close()
                    logger.info("专属服务实例 session 清理完成。")
                except Exception as close_err:
                    logger.warning(f"清理专属服务实例 session 失败: {close_err}")
    

    async def get_task_status(self, task_id: str, user_id: Optional[int] = None) -> Optional[SpeakStatus]:
        """
        获取任务状态

        Args:
            task_id: 任务ID
            user_id: 当前认证用户ID；提供时会校验任务归属，非归属任务返回 None

        Returns:
            任务状态或None
        """
        status = self._task_status.get(task_id)
        if status is None:
            return None

        # 越权校验：任务记录中的 user_id 必须与当前用户一致
        if user_id is not None:
            owner_id = self._task_owner.get(task_id)
            if owner_id is not None and owner_id != user_id:
                logger.warning(f"拒绝跨用户查询任务状态: task_id={task_id}, owner={owner_id}, requester={user_id}")
                return None

        return status

    async def stop_speak(self, task_id: Optional[str] = None, device_id: Optional[str] = None, user_id: Optional[int] = None) -> Dict:
        """
        停止语音播放

        Args:
            task_id: 任务ID
            device_id: 设备ID
            user_id: 当前认证用户ID；提供时会校验任务归属，非归属任务拒绝操作

        Returns:
            操作结果
        """
        try:
            if task_id and task_id in self._task_status:
                # 越权校验：任务记录中的 user_id 必须与当前用户一致
                if user_id is not None:
                    owner_id = self._task_owner.get(task_id)
                    if owner_id is not None and owner_id != user_id:
                        logger.warning(f"拒绝跨用户停止任务: task_id={task_id}, owner={owner_id}, requester={user_id}")
                        return {"success": False, "message": "任务不存在或无权操作"}

                # 根据任务ID停止
                task_status = self._task_status[task_id]
                device_id = task_status.device_id

                # 更新任务状态
                task_status.status = TaskStatus.FAILED.value
                task_status.error_message = "任务已取消"
                task_status.end_time = time.strftime("%Y-%m-%d %H:%M:%S")

            if not device_id:
                return {"success": False, "message": "缺少设备ID或任务ID"}

            # 调用底层停止服务：
            # 有用户上下文时必须走专属实例（带该用户的账号凭据）——全局单例
            # wrapper 通常没有认证信息，此前直接用它导致设备级停止一直失败
            service = mi_service_wrapper
            own_service = False
            if user_id:
                try:
                    service = await self._get_user_mi_service(user_id, device_id)
                    own_service = service is not mi_service_wrapper
                except Exception as auth_err:
                    logger.error(f"停止播放：构建用户专属服务失败: {auth_err}")
                    return {"success": False, "message": f"停止播放失败：无法获取小米账号凭据（{str(auth_err)[:80]}）"}

            try:
                result = await service.stop_speak(device_id)
            finally:
                if own_service:
                    try:
                        await service.close()
                    except Exception as close_err:
                        logger.warning(f"关闭专属服务实例失败: {close_err}")

            if result["success"]:
                logger.info(f"设备 {device_id} 停止播放成功")
                return {"success": True, "message": "停止播放成功", "device_id": device_id}
            else:
                return {"success": False, "message": f"停止播放失败: {result.get('error')}", "device_id": device_id}

        except Exception as e:
            logger.error(f"停止播放异常: {e}")
            return {"success": False, "message": f"停止播放异常: {str(e)}"}

    async def get_devices(self, user_id: Optional[int] = None, db: Optional[AsyncSession] = None) -> List[DeviceInfo]:
        """
        获取设备列表 - 从数据库获取

        Returns:
            设备信息列表
        """
        try:
            if user_id and db:
                # 从数据库获取设备列表
                from sqlalchemy import select
                from app.models.device import Device
                
                stmt = select(Device).where(Device.user_id == user_id)
                result = await db.execute(stmt)
                devices = result.scalars().all()
                
                # 转换为DeviceInfo格式
                mapped: List[DeviceInfo] = []
                for device in devices:
                    mapped.append(
                        DeviceInfo(
                            device_id=device.device_id,
                            name=device.device_name or "小爱设备",
                            model=device.device_model or "",
                            status="online" if device.is_online else "offline",
                            volume=device.volume or 50,
                            location=device.location,
                        )
                    )
                return mapped
            
            # 兼容旧版本调用，返回空列表
            return []
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []

    async def get_device_status(self, device_id: str) -> Optional[DeviceInfo]:
        """
        获取设备状态

        Args:
            device_id: 设备ID

        Returns:
            设备信息或None
        """
        try:
            return await mi_service_wrapper.get_device_by_id(device_id)
        except Exception as e:
            logger.error(f"获取设备状态失败: {e}")
            return None

    async def set_device_volume(self, device_id: str, volume: int, user_id: Optional[int] = None, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        设置设备音量

        Args:
            device_id: 设备ID
            volume: 音量大小(0-100)
            user_id: 用户ID（可选）
            db: 数据库会话（可选）

        Returns:
            操作结果
        """
        try:
            # 验证音量范围
            if not 0 <= volume <= 100:
                return {"success": False, "error": "音量必须在0-100之间"}

            # 如果有用户ID，使用用户专属的MiService
            service = None
            if user_id:
                if not _MISERVICE_AVAILABLE:
                    return {"success": False, "error": "MiService库不可用"}
                
                try:
                    # 构建用户专属的MiService（不获取设备列表）
                    service = await self._get_user_mi_service(user_id, device_id)
                    result = await service.set_volume(device_id, volume)
                except Exception as e:
                    result = {"success": False, "error": str(e)}
                finally:
                    if service is not None:
                        try:
                            await service.close()
                        except Exception as close_err:
                            logger.warning(f"关闭专属服务实例 session 失败: {close_err}")
            else:
                # 使用全局MiService
                result = await mi_service_wrapper.set_volume(device_id, volume)

            if result["success"]:
                logger.info(f"设备 {device_id} 音量设置成功: {volume}")
                # 持久化音量，刷新后仍是设置值（此前只改设备不改库，刷新回到默认值）
                if user_id and db:
                    try:
                        from sqlalchemy import select

                        from app.models.device import Device

                        stmt = select(Device).where(Device.user_id == user_id, Device.device_id == device_id)
                        dresult = await db.execute(stmt)
                        device_row = dresult.scalar_one_or_none()
                        if device_row:
                            device_row.volume = volume
                            await db.commit()
                            logger.info(f"音量已持久化: 设备={device_id}, volume={volume}")
                    except Exception as persist_err:
                        logger.warning(f"音量持久化失败（不影响设置结果）: {persist_err}")
            else:
                logger.error(f"设备 {device_id} 音量设置失败: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"设置设备音量异常: {e}")
            return {"success": False, "error": f"设置音量异常: {str(e)}", "device_id": device_id}

    async def _get_user_mi_service(self, user_id: int, device_id: Optional[str] = None) -> Optional[object]:
        """为指定用户构建独立的MiService实例，用于播放操作"""
        if not _MISERVICE_AVAILABLE:
            logger.warning("MiService库不可用，无法创建用户专属服务")
            return None

        from app.utils.mi_service import MiServiceWrapper
        from app.database import AsyncSessionLocal

        # 使用独立数据库会话，避免与会话冲突
        session = AsyncSessionLocal()
        accounts = None
        device_mi_username = None
        try:
            # 如果提供了device_id，先查找设备对应的mi_username
            if device_id:
                from app.models.device import Device
                from sqlalchemy import select

                # 使用查询而不是get，因为device_id不是主键
                stmt = select(Device).where(Device.device_id == device_id, Device.user_id == user_id)
                result = await session.execute(stmt)
                device = result.scalar_one_or_none()

                if device:
                    device_mi_username = device.mi_username
                    logger.info(f"设备 {device_id} 对应的小米账号: {device_mi_username}")
                else:
                    logger.warning(f"未找到设备 {device_id} 或设备不属于用户 {user_id}")

            mi_acc_service = MiAccountService(session)
            accounts = await mi_acc_service.get_user_mi_accounts(user_id)
        except Exception as e:
            logger.error(f"获取用户小米账户失败: {e}")
            raise RuntimeError(f"获取用户小米账户失败: {e}") from e
        finally:
            await session.close()

        # 选择账号：如果有设备对应的mi_username，优先选择匹配的账号
        chosen = None
        if device_mi_username:
            for acc in accounts:
                if acc.mi_username == device_mi_username and acc.is_active:
                    chosen = acc
                    logger.info(f"找到设备对应的小米账号: {acc.mi_username}")
                    break
        
        # 如果没有找到匹配的账号，选择一个可用账号：启用且同步成功的优先
        if not chosen:
            for acc in accounts:
                if acc.is_active and getattr(acc, "sync_status", None) and acc.sync_status.value == "success":
                    chosen = acc
                    break
        if not chosen and accounts:
            chosen = accounts[0]
        if not chosen:
            raise RuntimeError("用户尚未绑定小米账号")

        # 使用MiServiceWrapper和账号的认证信息
        mi_service_wrapper = MiServiceWrapper()
        mi_password = decrypt_password(chosen.mi_password_encrypted)

        # 设置自定义认证信息
        mi_service_wrapper.set_custom_auth(
            username=chosen.mi_username,
            password=mi_password,
            device_id=chosen.mi_device_id,
            user_id=chosen.mi_user_id,
            pass_token=_load_pass_token(chosen.mi_pass_token),  # 存储为密文，必须解密后使用
        )

        return mi_service_wrapper

    async def _get_user_mi_service_and_devices(self, db: Optional[AsyncSession], user_id: int) -> Tuple[object, List[Dict]]:
        """为指定用户构建独立MiService实例并返回设备列表。"""
        if not _MISERVICE_AVAILABLE:
            raise RuntimeError("MiService库不可用")

        from app.utils.mi_service import MiServiceWrapper
        from app.database import AsyncSessionLocal

        # 使用独立数据库会话，避免与会话冲突
        session = AsyncSessionLocal()
        try:
            mi_acc_service = MiAccountService(session)
            accounts = await mi_acc_service.get_user_mi_accounts(user_id)
        except Exception as e:
            logger.error(f"获取用户小米账户失败: {e}")
            raise RuntimeError(f"获取用户小米账户失败: {e}") from e
        finally:
            await session.close()

        # 选择一个可用账号：启用且同步成功的优先
        chosen = None
        for acc in accounts:
            if acc.is_active and getattr(acc, "sync_status", None) and acc.sync_status.value == "success":
                chosen = acc
                break
        if not chosen and accounts:
            chosen = accounts[0]
        if not chosen:
            raise RuntimeError("用户尚未绑定小米账号")

        # 使用MiServiceWrapper和账号的认证信息
        mi_service_wrapper = MiServiceWrapper()
        mi_password = decrypt_password(chosen.mi_password_encrypted)

        # 设置自定义认证信息
        mi_service_wrapper.set_custom_auth(
            username=chosen.mi_username,
            password=mi_password,
            device_id=chosen.mi_device_id,
            user_id=chosen.mi_user_id,
            pass_token=_load_pass_token(chosen.mi_pass_token),  # 存储为密文，必须解密后使用
        )

        # 获取设备列表
        devices = await mi_service_wrapper.get_devices(force_refresh=True)

        # 转换为字典格式
        norm: List[Dict] = []
        for device in devices:
            norm.append(
                {
                    "device_id": device.device_id,
                    "did": device.device_id,
                    "name": device.name,
                    "model": device.model,
                    "ip": getattr(device, "ip", None),
                    "is_online": device.status == "online",
                    "location": device.location,
                }
            )

        return mi_service_wrapper, norm

    async def notify_play_url(
        self,
        user_id: int,
        device_ids: List[str],
        url: str,
        volume: Optional[int] = None,
        endvolume: Optional[int] = None,
        repeat: int = 1,
        interval: float = 0,
        end_volume_delay: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        通知渠道的音频 URL 播放：多设备 + 次数/间隔 + 首末音量控制 + 播完自动停止。

        LX05 等设备的 URL 播放会单曲无限循环（设备侧行为，loop 设置无法关闭），
        因此服务端估算音频时长，播放结束后由守护任务自动下发停止并恢复结束音量。
        """
        repeat = max(1, min(int(repeat or 1), 10))
        interval = max(0.0, float(interval or 0))
        failures = []

        # 估算音频时长（决定自动停止时机；失败则不守护，由用户手动停止）
        from app.utils.audio_meta import estimate_audio_duration

        duration = await estimate_audio_duration(url)
        if duration:
            logger.info(f"通知播报：音频时长约 {duration:.1f} 秒，播完后自动停止")
        else:
            logger.warning("通知播报：无法估算音频时长，播完后不会自动停止，请手动停止或更换音频")

        for device_id in device_ids:
            try:
                svc = await self._get_user_mi_service(user_id, device_id)
            except Exception as e:
                failures.append(f"{device_id}: {str(e)[:60]}")
                continue

            try:
                if volume is not None:
                    r = await svc.set_volume(device_id, volume)
                    if not r.get("success"):
                        logger.warning(f"通知播报：设置开始音量失败 device={device_id}: {r.get('error')}")

                played_ok = True
                for i in range(repeat):
                    r = await svc.play_url(device_id, url)
                    if not r.get("success"):
                        played_ok = False
                        failures.append(f"{device_id} 第{i + 1}次: {str(r.get('error'))[:60]}")
                        break
                    if i < repeat - 1 and interval > 0:
                        await asyncio.sleep(interval)

                if not played_ok:
                    continue

                # 播完自动停止 + 恢复结束音量（守护任务持有 svc，结束后释放）
                if duration:
                    total = duration * repeat + interval * (repeat - 1)
                    stop_delay = max(1.0, total + 1.5)
                    task = asyncio.create_task(
                        self._auto_stop_device(svc, device_id, stop_delay, endvolume, end_volume_delay)
                    )
                    self._auto_stop_tasks.add(task)
                    task.add_done_callback(self._auto_stop_tasks.discard)
                elif endvolume is not None:
                    # 无时长守护时维持旧语义：延迟后设置结束音量
                    delay = end_volume_delay if end_volume_delay is not None else 2.0
                    if delay > 0:
                        await asyncio.sleep(delay)
                    r = await svc.set_volume(device_id, endvolume)
                    if not r.get("success"):
                        logger.warning(f"通知播报：恢复结束音量失败 device={device_id}: {r.get('error')}")
                    try:
                        await svc.close()
                    except Exception:
                        pass
            except Exception as e:
                failures.append(f"{device_id}: {str(e)[:60]}")
                try:
                    await svc.close()
                except Exception:
                    pass

        if failures:
            return False, "；".join(failures)
        return True, (
            f"已在 {len(device_ids)} 台设备上开始播放"
            + ("，播完后将自动停止" if duration else "（无法估算音频时长，播完后请手动停止）")
        )

    async def _auto_stop_device(
        self,
        svc,
        device_id: str,
        stop_delay: float,
        endvolume: Optional[int],
        end_volume_delay: Optional[float],
    ) -> None:
        """播放结束守护：等待后下发停止并恢复结束音量，最后释放服务实例"""
        try:
            await asyncio.sleep(stop_delay)
            try:
                mina = await svc._get_mina_service()
                mid = svc._resolve_mina_device_id(device_id)
                await mina.player_stop(mid)
                logger.info(f"通知播报：音频播放结束，已自动停止 device={device_id}")
            except Exception as e:
                logger.warning(f"通知播报：自动停止失败 device={device_id}: {e}")

            if endvolume is not None:
                delay = end_volume_delay if end_volume_delay is not None else 0.0
                if delay > 0:
                    await asyncio.sleep(delay)
                try:
                    r = await svc.set_volume(device_id, endvolume)
                    if not r.get("success"):
                        logger.warning(f"通知播报：恢复结束音量失败 device={device_id}: {r.get('error')}")
                except Exception as e:
                    logger.warning(f"通知播报：恢复结束音量异常 device={device_id}: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await svc.close()
            except Exception:
                pass

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        清理旧任务记录

        Args:
            max_age_hours: 最大保存时间（小时）
        """
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        # 找出需要删除的任务
        tasks_to_remove = []
        for task_id, task_status in self._task_status.items():
            if task_status.start_time:
                task_time = time.mktime(time.strptime(task_status.start_time, "%Y-%m-%d %H:%M:%S"))
                if task_time < cutoff_time:
                    tasks_to_remove.append(task_id)

        # 删除旧任务
        for task_id in tasks_to_remove:
            del self._task_status[task_id]
            self._task_owner.pop(task_id, None)

        if tasks_to_remove:
            logger.info(f"清理了 {len(tasks_to_remove)} 个旧任务记录")


# 全局服务实例
speak_service = SpeakService()
