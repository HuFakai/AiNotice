# -*- coding: utf-8 -*-
"""
小米账户管理服务
"""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from loguru import logger
import asyncio

from app.models.user import User
from app.models.mi_account import MiAccount, SyncStatus
from app.models.device import Device
from app.models.user_activity import ActivityType
from app.services.user_service import UserService
from app.utils.mi_service import mi_service_wrapper

try:
    # 尝试导入真实MiService库
    from miservice import MiAccount as MiSvcAccount, MiIOService as MiSvcMiIOService

    _MISERVICE_AVAILABLE = True
except Exception:  # pragma: no cover
    _MISERVICE_AVAILABLE = False
from app.utils.encryption import encrypt_password, decrypt_password
import tempfile
import os
import sys
import aiohttp

# 添加Login模块到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../Login'))

try:
    from Login.mi_account import MiAccountManager
    from Login.utils import extract_token_info
    _LOGIN_MODULE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Login模块不可用: {e}")
    _LOGIN_MODULE_AVAILABLE = False


class MiAccountService:
    """小米账户服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def create_mi_account(
        self,
        user_id: int,
        mi_username: str,
        mi_password: str,
        device_id: str,
        user_id_mi: str,
        pass_token: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        创建小米账户

        Args:
            user_id: 用户ID
            mi_username: 小米用户名
            mi_password: 小米密码
            device_id: 小米设备ID
            user_id_mi: 小米用户ID
            pass_token: 小米认证令牌
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息, 账户数据)
        """
        try:
            # 检查用户是否存在
            user = await self.user_service.get_user_by_id(user_id)
            if not user:
                return False, "用户不存在", None

            # 检查是否已存在相同的小米账户
            existing_account = await self._get_mi_account_by_username(user_id, mi_username)
            if existing_account:
                return False, "该小米账户已绑定", None

            # 加密密码
            encrypted_password = encrypt_password(mi_password)

            # 创建小米账户记录
            mi_account = MiAccount(
                user_id=user_id,
                mi_username=mi_username,
                mi_password_encrypted=encrypted_password,
                mi_device_id=device_id,
                mi_user_id=user_id_mi,
                mi_pass_token=pass_token,
                sync_status=SyncStatus.PENDING,
            )

            self.db.add(mi_account)
            await self.db.flush()

            # 获取ID
            account_id = mi_account.id

            # 提交数据库事务
            await self.db.commit()

            # 记录活动日志
            try:
                # 兼容：UserService现有方法为 _log_user_activity
                if hasattr(self.user_service, "_log_user_activity"):
                    await self.user_service._log_user_activity(
                        user_id,
                        ActivityType.MI_ACCOUNT_CREATE,
                        f"添加小米账户: {mi_username}",
                        resource_type="mi_account",
                        resource_id=account_id,
                        client_ip=client_ip,
                        user_agent=user_agent,
                    )
                    await self.db.commit()
                elif hasattr(self.user_service, "log_user_activity"):
                    await self.user_service.log_user_activity(
                        user_id=user_id,
                        activity_type=ActivityType.MI_ACCOUNT_CREATE,
                        activity_description=f"添加小米账户: {mi_username}",
                        client_ip=client_ip,
                        user_agent=user_agent,
                    )
                else:
                    logger.warning("UserService 未提供活动日志方法，已跳过记录")
            except Exception as e:
                logger.warning(f"记录活动日志失败: {e}")

            logger.info(f"小米账户创建成功: {mi_username} (用户: {user.username})")

            # 异步执行认证和设备同步
            asyncio.create_task(self._sync_mi_account_async(account_id))

            return (
                True,
                "小米账户添加成功，正在同步设备信息",
                {
                    "id": account_id,
                    "mi_username": mi_username,
                    "sync_status": SyncStatus.PENDING.value,
                    "created_at": datetime.utcnow(),
                },
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建小米账户失败: {e}")
            return False, "创建小米账户失败", None

    async def create_mi_account_simplified(
        self,
        user_id: int,
        mi_username: str,
        mi_password: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        使用Login模块创建小米账户（简化版本）
        只需要小米账号和密码，自动获取其他参数
        
        Args:
            user_id: 用户ID
            mi_username: 小米用户名
            mi_password: 小米密码
            client_ip: 客户端IP
            user_agent: 用户代理
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 消息, 账户数据)
        """
        if not _LOGIN_MODULE_AVAILABLE:
            return False, "Login模块不可用，请使用传统方式添加账户", None
            
        # 检查用户名是否已存在
        existing_account = await self._get_mi_account_by_username(user_id, mi_username)
        if existing_account:
            return False, "该小米账户已存在", None

        # 创建临时token文件
        token_fd, token_path = tempfile.mkstemp(suffix='.json', prefix='mi_token_')
        os.close(token_fd)  # 关闭文件描述符，只保留路径
        
        try:
            # 使用Login模块进行认证
            async with aiohttp.ClientSession() as session:
                manager = MiAccountManager(mi_username, mi_password, token_path)
                success = await manager.login(session)
                
                if not success:
                    return False, "小米账号认证失败，请检查用户名和密码", None
                
                # 提取关键信息
                token_info = extract_token_info(token_path)
                if not token_info:
                    return False, "无法提取认证信息，请重试", None
                    
                device_id = token_info.get('deviceId', '')
                user_id_mi = token_info.get('userId', '')
                pass_token = token_info.get('passToken', '')
                
                if not all([device_id, user_id_mi, pass_token]):
                    return False, "认证信息不完整，请重试", None
                
                logger.info(f"Login模块认证成功，用户: {mi_username}, deviceId: {device_id[:8]}...")
                
                # 调用原有的创建方法
                return await self.create_mi_account(
                    user_id, mi_username, mi_password,
                    device_id, user_id_mi, pass_token,
                    client_ip, user_agent
                )
                
        except Exception as e:
            logger.error(f"使用Login模块创建小米账户失败: {e}")
            return False, f"创建账户失败: {str(e)}", None
            
        finally:
            # 清理临时文件
            try:
                if os.path.exists(token_path):
                    os.unlink(token_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

    async def get_user_mi_accounts(self, user_id: int) -> List[MiAccount]:
        """获取用户的小米账户列表"""
        try:
            stmt = (
                select(MiAccount)
                .where(MiAccount.user_id == user_id)
                .options(selectinload(MiAccount.devices))
                .order_by(MiAccount.created_at.desc())
            )

            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"获取用户小米账户列表失败: {e}")
            return []

    async def get_mi_account_by_id(self, user_id: int, account_id: int) -> Optional[MiAccount]:
        """根据ID获取小米账户"""
        try:
            stmt = (
                select(MiAccount)
                .where(and_(MiAccount.id == account_id, MiAccount.user_id == user_id))
                .options(selectinload(MiAccount.devices))
            )

            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"获取小米账户失败: {e}")
            return None

    async def sync_mi_account(self, user_id: int, account_id: int) -> Tuple[bool, str]:
        """手动同步小米账户"""
        try:
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return False, "小米账户不存在"

            # 更新同步状态
            mi_account.sync_status = SyncStatus.PENDING
            mi_account.error_message = None
            await self.db.commit()

            # 异步执行同步
            asyncio.create_task(self._sync_mi_account_async(account_id))

            return True, "同步已开始，请稍后查看结果"

        except Exception as e:
            logger.error(f"手动同步小米账户失败: {e}")
            return False, "同步失败"

    async def delete_mi_account(
        self, user_id: int, account_id: int, client_ip: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Tuple[bool, str]:
        """删除小米账户"""
        try:
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return False, "小米账户不存在"

            mi_username = mi_account.mi_username

            # 删除账户（级联删除相关设备）
            await self.db.delete(mi_account)
            await self.db.commit()

            # 记录活动日志
            try:
                await self.user_service.log_user_activity(
                    user_id=user_id,
                    activity_type=ActivityType.MI_ACCOUNT_DELETE,
                    activity_description=f"删除小米账户: {mi_username}",
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.warning(f"记录活动日志失败: {e}")

            logger.info(f"小米账户删除成功: {mi_username}")
            return True, "小米账户删除成功"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"删除小米账户失败: {e}")
            return False, "删除失败"

    async def update_mi_account_status(self, user_id: int, account_id: int, is_active: bool) -> Tuple[bool, str]:
        """更新小米账户状态"""
        try:
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return False, "小米账户不存在"

            mi_account.is_active = is_active
            mi_account.updated_at = datetime.utcnow()
            await self.db.commit()

            status_text = "启用" if is_active else "禁用"
            return True, f"小米账户已{status_text}"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新小米账户状态失败: {e}")
            return False, "更新状态失败"

    async def test_mi_account_connection(self, user_id: int, account_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """测试小米账户连接"""
        try:
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return False, "小米账户不存在", None

            if not mi_account.is_active:
                return False, "小米账户未启用", None

            # 解密密码
            mi_password = decrypt_password(mi_account.mi_password_encrypted)

            # 测试连接
            test_result = await self._test_mi_service_connection(mi_account.mi_username, mi_password)

            return test_result["success"], test_result["message"], test_result.get("data")

        except Exception as e:
            logger.error(f"测试小米账户连接失败: {e}")
            return False, "连接测试失败", None

    async def get_account_devices(self, user_id: int, account_id: int) -> List[Device]:
        """获取账户下的设备"""
        try:
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return []

            return mi_account.devices

        except Exception as e:
            logger.error(f"获取账户设备失败: {e}")
            return []

    async def refresh_account_devices(self, user_id: int, account_id: int) -> Tuple[bool, str]:
        """刷新指定账户的设备列表"""
        try:
            # 获取小米账户
            mi_account = await self.get_mi_account_by_id(user_id, account_id)
            if not mi_account:
                return False, "小米账户不存在"

            if not mi_account.is_active:
                return False, "小米账户未激活"

            # 同步设备
            await self._sync_devices(self.db, mi_account)
            await self.db.commit()

            logger.info(f"刷新账户设备成功: {mi_account.mi_username}")
            return True, "设备列表刷新成功"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"刷新账户设备失败: {e}")
            return False, f"刷新设备失败: {str(e)}"

    async def refresh_all_devices(self, user_id: int) -> Tuple[bool, str]:
        """刷新用户所有账户的设备列表"""
        try:
            # 获取用户所有激活的小米账户
            mi_accounts = await self.get_user_mi_accounts(user_id)
            active_accounts = [acc for acc in mi_accounts if acc.is_active]

            if not active_accounts:
                return False, "没有激活的小米账户"

            success_count = 0
            total_count = len(active_accounts)

            # 逐个刷新每个账户的设备
            for mi_account in active_accounts:
                try:
                    await self._sync_devices(self.db, mi_account)
                    success_count += 1
                    logger.info(f"刷新账户设备成功: {mi_account.mi_username}")
                except Exception as e:
                    logger.error(f"刷新账户设备失败 {mi_account.mi_username}: {e}")

            await self.db.commit()

            if success_count == total_count:
                return True, f"所有设备列表刷新成功 ({success_count}/{total_count})"
            elif success_count > 0:
                return True, f"部分设备列表刷新成功 ({success_count}/{total_count})"
            else:
                return False, "所有设备列表刷新失败"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"刷新所有设备失败: {e}")
            return False, f"刷新设备失败: {str(e)}"



    # 私有方法
    async def _get_mi_account_by_username(self, user_id: int, mi_username: str) -> Optional[MiAccount]:
        """根据用户名获取小米账户"""
        try:
            stmt = select(MiAccount).where(and_(MiAccount.user_id == user_id, MiAccount.mi_username == mi_username))

            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"查询小米账户失败: {e}")
            return None

    async def _sync_mi_account_async(self, account_id: int):
        """异步同步小米账户"""
        # 在异步任务中使用独立的数据库会话，避免会话冲突
        from app.database import get_database_session

        async for session in get_database_session():
            try:
                # 重新获取账户信息
                stmt = select(MiAccount).where(MiAccount.id == account_id)
                result = await session.execute(stmt)
                mi_account = result.scalar_one_or_none()

                if not mi_account:
                    logger.error(f"同步时未找到小米账户: {account_id}")
                    return

                logger.info(f"开始同步小米账户: {mi_account.mi_username}")

                try:
                    # 解密密码
                    mi_password = decrypt_password(mi_account.mi_password_encrypted)

                    # 执行认证
                    auth_result = await self._authenticate_mi_account(mi_account, mi_password)

                    if auth_result["success"]:
                        # 更新认证信息（仅在新登录验证时更新）
                        if auth_result["message"] != "使用已存储的认证信息":
                            mi_account.mi_device_id = auth_result["data"].get("device_id")
                            mi_account.mi_user_id = auth_result["data"].get("user_id")
                            mi_account.mi_pass_token = auth_result["data"].get("pass_token")
                        mi_account.sync_status = SyncStatus.SUCCESS
                        mi_account.error_message = None
                        mi_account.last_sync_at = datetime.utcnow()

                        # 同步设备
                        await self._sync_devices(session, mi_account)

                        logger.info(f"小米账户同步成功: {mi_account.mi_username}")
                    else:
                        # 同步失败
                        mi_account.sync_status = SyncStatus.FAILED
                        mi_account.error_message = auth_result["message"]
                        mi_account.last_sync_at = datetime.utcnow()

                        logger.error(f"小米账户认证失败: {auth_result['message']}")

                    await session.commit()

                except Exception as sync_error:
                    # 同步异常
                    mi_account.sync_status = SyncStatus.FAILED
                    mi_account.error_message = f"同步异常: {str(sync_error)}"
                    mi_account.last_sync_at = datetime.utcnow()

                    await session.commit()
                    logger.error(f"小米账户同步异常: {sync_error}")

            except Exception as e:
                logger.error(f"异步同步小米账户失败: {e}")
                await session.rollback()

    async def _authenticate_mi_account(self, mi_account: MiAccount, mi_password: str) -> Dict[str, Any]:
        """认证小米账户（使用MiServiceWrapper）"""
        try:
            # 检查是否已有完整的认证信息，如果有则先尝试验证是否有效
            if (mi_account.mi_device_id and 
                mi_account.mi_user_id and 
                mi_account.mi_pass_token):
                logger.info(f"验证已存储的认证信息: {mi_account.mi_username}")
                
                # 先尝试使用已存储的认证信息进行简单验证
                from app.utils.mi_service import MiServiceWrapper
                test_wrapper = MiServiceWrapper()
                test_wrapper.set_custom_auth(
                    username=mi_account.mi_username,
                    password=mi_password,
                    device_id=mi_account.mi_device_id,
                    user_id=mi_account.mi_user_id,
                    pass_token=mi_account.mi_pass_token,
                )
                
                try:
                    # 尝试获取设备列表来验证认证信息是否有效
                    devices = await test_wrapper.get_devices(force_refresh=False)
                    test_wrapper.clear_custom_auth()
                    logger.info(f"已存储的认证信息有效: {mi_account.mi_username}")
                    return {
                        "success": True,
                        "message": "使用已存储的认证信息",
                        "data": {
                            "device_id": mi_account.mi_device_id,
                            "user_id": mi_account.mi_user_id,
                            "pass_token": mi_account.mi_pass_token
                        },
                    }
                except Exception as verify_error:
                    test_wrapper.clear_custom_auth()
                    logger.warning(f"已存储的认证信息无效，需要重新登录: {verify_error}")
                    # 继续执行新的登录验证
            
            # 如果没有完整认证信息或认证信息无效，进行新的登录验证
            logger.info(f"执行新的登录验证: {mi_account.mi_username}")
            from app.utils.mi_service import MiServiceWrapper

            # 创建独立的MiServiceWrapper实例进行认证测试
            mi_service_wrapper = MiServiceWrapper()

            # 设置自定义认证信息
            mi_service_wrapper.set_custom_auth(username=mi_account.mi_username, password=mi_password)

            # 尝试获取设备列表来验证认证
            try:
                devices = await mi_service_wrapper.get_devices(force_refresh=True)
                logger.info(f"认证成功，获取到 {len(devices)} 个设备")

                # 获取认证信息（从MiAccount中提取token信息）
                mi_service_account = mi_service_wrapper._mi_account
                if mi_service_account and hasattr(mi_service_account, "token"):
                    token = getattr(mi_service_account, "token", None) or {}
                    device_id = token.get("deviceId")
                    user_id = token.get("userId")
                    pass_token = token.get("passToken")

                    # 清除自定义认证信息
                    mi_service_wrapper.clear_custom_auth()

                    return {
                        "success": True,
                        "message": "认证成功",
                        "data": {"device_id": device_id, "user_id": user_id, "pass_token": pass_token},
                    }
                else:
                    # 清除自定义认证信息
                    mi_service_wrapper.clear_custom_auth()
                    return {"success": False, "message": "认证失败：未获取到token信息", "data": None}

            except Exception as auth_error:
                # 清除自定义认证信息
                mi_service_wrapper.clear_custom_auth()
                logger.error(f"认证过程中出错: {auth_error}")
                return {"success": False, "message": f"认证失败: {str(auth_error)}", "data": None}

        except Exception as e:
            logger.error(f"小米账户认证失败: {e}")
            return {"success": False, "message": f"认证失败: {str(e)}", "data": None}

    async def _sync_devices(self, session: AsyncSession, mi_account: MiAccount):
        """同步设备信息"""
        try:
            # 获取设备列表 - 使用自定义的MiServiceWrapper
            devices_data = await self._get_mi_devices_with_wrapper(mi_account)

            # 清除旧设备
            stmt = select(Device).where(Device.mi_account_id == mi_account.id)
            result = await session.execute(stmt)
            old_devices = result.scalars().all()

            for old_device in old_devices:
                await session.delete(old_device)
            
            # 提交删除操作
            await session.flush()

            # 添加新设备
            for device_data in devices_data:
                device = Device(
                    user_id=mi_account.user_id,
                    mi_account_id=mi_account.id,
                    device_id=device_data["device_id"],
                    device_name=device_data["name"],
                    device_model=device_data.get("model"),
                    device_type="xiaomi_speaker",
                    location=device_data.get("location"),
                    mi_username=mi_account.mi_username,
                    is_online=device_data.get("is_online", False),
                    volume=device_data.get("volume", 50),
                    device_info=device_data,
                )
                session.add(device)

            logger.info(f"同步了 {len(devices_data)} 个设备")

        except Exception as e:
            logger.error(f"同步设备失败: {e}")

    async def _get_mi_devices_with_wrapper(self, mi_account: MiAccount) -> List[Dict[str, Any]]:
        """使用MiServiceWrapper获取小米设备列表"""
        try:
            from app.utils.mi_service import MiServiceWrapper

            # 创建独立的MiServiceWrapper实例
            mi_service_wrapper = MiServiceWrapper()

            # 解密密码
            mi_password = decrypt_password(mi_account.mi_password_encrypted)

            # 设置自定义认证信息
            mi_service_wrapper.set_custom_auth(
                username=mi_account.mi_username,
                password=mi_password,
                device_id=mi_account.mi_device_id,
                user_id=mi_account.mi_user_id,
                pass_token=mi_account.mi_pass_token,
            )

            # 获取设备列表
            devices = await mi_service_wrapper.get_devices(force_refresh=True)

            # 转换为字典格式
            normalized: List[Dict[str, Any]] = []
            for device in devices:
                normalized.append(
                    {
                        "device_id": device.device_id,
                        "name": device.name,
                        "model": device.model,
                        "location": device.location,
                        "is_online": device.status == "online",
                        "volume": device.volume,
                        "ip": getattr(device, "ip", None),
                    }
                )

            # 清除自定义认证信息
            mi_service_wrapper.clear_custom_auth()

            return normalized

        except Exception as e:
            logger.error(f"获取小米设备失败: {e}")
            return []

    async def _get_mi_devices(self, mi_account: MiAccount) -> List[Dict[str, Any]]:
        """获取小米设备列表（真实MiService）- 保留原方法作为备用"""
        try:
            if not _MISERVICE_AVAILABLE:
                raise RuntimeError("MiService库不可用，请确认已正确安装并在运行环境中可用")

            # 使用账户名+解密后的密码重新建立会话
            mi_password = decrypt_password(mi_account.mi_password_encrypted)
            account = MiSvcAccount(
                session=None, username=mi_account.mi_username, password=mi_password, token_store=None
            )
            service = MiSvcMiIOService(account)
            devices = await service.device_list()

            normalized: List[Dict[str, Any]] = []
            for d in devices or []:
                # 兼容不同对象结构
                did = (
                    getattr(d, "did", None) or getattr(d, "device_id", None) or d.get("did")
                    if isinstance(d, dict)
                    else None
                )
                name = getattr(d, "name", None) or (d.get("name") if isinstance(d, dict) else None)
                model = getattr(d, "model", None) or (d.get("model") if isinstance(d, dict) else None)
                ip = getattr(d, "ip", None) or (d.get("ip") if isinstance(d, dict) else None)
                online = getattr(d, "online", None)
                if online is None and isinstance(d, dict):
                    online = d.get("is_online") or d.get("online")
                normalized.append(
                    {
                        "device_id": did or "",
                        "name": name or "小爱设备",
                        "model": model,
                        "location": None,
                        "is_online": bool(online) if online is not None else True,
                        "volume": 50,
                        "ip": ip,
                    }
                )

            return normalized

        except Exception as e:
            logger.error(f"获取小米设备失败: {e}")
            return []

    async def _test_mi_service_connection(self, mi_username: str, mi_password: str) -> Dict[str, Any]:
        """测试小米服务连接"""
        try:
            # 这里应该调用真实的连接测试
            # 目前返回模拟结果
            await asyncio.sleep(1)  # 模拟网络延迟

            return {"success": True, "message": "连接正常", "data": {"ping_time": "150ms", "server_status": "正常"}}

        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            return {"success": False, "message": f"连接失败: {str(e)}", "data": None}
