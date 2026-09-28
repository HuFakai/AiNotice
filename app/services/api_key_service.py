# -*- coding: utf-8 -*-
"""
API密钥服务
"""

from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from datetime import datetime, timedelta, timezone
from loguru import logger

from app.models.user import User
from app.models.api_key import ApiKey
from app.models.user_activity import ActivityType
from app.services.user_service import UserService
from app.utils.api_key import (
    generate_api_key,
    build_key_metadata,
    hash_api_key,
    validate_api_key_permissions,
    get_default_permissions,
)
from app.config import settings


class ApiKeyService:
    """API密钥服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def create_api_key(
        self,
        user_id: int,
        key_name: str,
        permissions: Optional[Dict[str, bool]] = None,
        expires_in_days: Optional[int] = None,
        usage_limit: Optional[int] = None,
        channel_ids: Optional[List[int]] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        创建API密钥

        Args:
            user_id: 用户ID
            key_name: 密钥名称
            permissions: 权限配置
            expires_in_days: 过期天数
            usage_limit: 使用限制
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息, 密钥数据)
        """
        try:
            # 检查用户是否存在
            user = await self.user_service.get_user_by_id(user_id)
            if not user:
                return False, "用户不存在", None

            # 检查密钥数量限制
            existing_count = await self._get_user_api_key_count(user_id)
            if existing_count >= settings.max_api_keys_per_user:
                return False, f"每个用户最多只能创建{settings.max_api_keys_per_user}个API密钥", None

            # 检查密钥名称是否重复
            if await self._check_key_name_exists(user_id, key_name):
                return False, "密钥名称已存在", None

            # 验证权限配置（validate_api_key_permissions会处理None的情况）
            perm_result = validate_api_key_permissions(permissions)
            if not perm_result["valid"]:
                return False, f"权限配置错误: {', '.join(perm_result['issues'])}", None

            # 校验绑定的通知渠道归属与存在性
            valid_channel_ids = None
            if channel_ids:
                ok, err = await self._validate_channel_ids(user_id, channel_ids)
                if not ok:
                    return False, err, None
                valid_channel_ids = channel_ids

            # 生成API密钥（数据库只存哈希与前缀，明文仅在创建响应中返回一次）
            api_key = generate_api_key()
            metadata = build_key_metadata(api_key)

            # 计算过期时间
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

            # 创建密钥记录
            api_key_obj = ApiKey(
                user_id=user_id,
                key_name=key_name,
                # 明文存储（产品决策：卡片直接展示+点击复制）；key_hash 同时保留用于校验
                api_key=api_key,
                api_secret="",
                key_hash=metadata["key_hash"],
                key_prefix=metadata["key_prefix"],
                is_active=True,
                permissions=perm_result["permissions"],
                channel_ids=valid_channel_ids,
                usage_limit=usage_limit,
                expires_at=expires_at,
            )

            # 在添加到数据库之前保存ID（如果需要的话）
            self.db.add(api_key_obj)
            await self.db.flush()  # 获取数据库生成的ID

            # 立即获取ID，避免后续访问数据库对象
            obj_id = api_key_obj.id

            # 提交事务
            await self.db.commit()

            # TODO: 活动日志记录功能暂时跳过，避免事务冲突
            logger.info(f"跳过活动日志记录: 创建API密钥 {key_name}")

            logger.info(f"API密钥创建成功: {key_name} (用户: {user.username})")

            # 使用预先获取的值构建返回数据，避免访问数据库对象
            created_at = datetime.now(timezone.utc)
            result_data = {
                "id": obj_id,  # 使用预先获取的ID
                "key_name": key_name,
                "api_key": api_key,
                "permissions": perm_result["permissions"],
                "channel_ids": valid_channel_ids,
                "expires_at": expires_at,  # 直接传datetime对象
                "usage_limit": usage_limit,
                "created_at": created_at,  # 传datetime对象
            }

            logger.info(f"返回数据构建成功")
            return True, "API密钥创建成功", result_data

        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建API密钥失败: {e}")
            return False, "创建API密钥失败", None

    async def verify_api_key(self, api_key: str) -> Tuple[bool, Optional[User], Optional[ApiKey]]:
        """
        验证API密钥（按 SHA-256 哈希查找，兼容历史明文行）

        Args:
            api_key: 完整API密钥

        Returns:
            (是否有效, 用户对象, 密钥对象)
        """
        key_hint = api_key[:10] if api_key else ""
        try:
            key_hash = hash_api_key(api_key)

            # 优先按哈希查找；历史明文行（key_hash 为空）回退按明文列查找
            stmt = select(ApiKey).where(
                and_(
                    or_(ApiKey.key_hash == key_hash, and_(ApiKey.key_hash.is_(None), ApiKey.api_key == api_key)),
                    ApiKey.is_active == True,  # noqa: E712
                )
            )
            result = await self.db.execute(stmt)
            api_key_obj = result.scalar_one_or_none()

            if not api_key_obj:
                logger.warning(f"API密钥不存在或已禁用: {key_hint}...")
                return False, None, None

            # 检查是否过期
            if api_key_obj.is_expired:
                logger.warning(f"API密钥已过期: {key_hint}...")
                return False, None, None

            # 检查使用限制
            if api_key_obj.is_usage_exceeded:
                logger.warning(f"API密钥使用次数超限: {key_hint}...")
                return False, None, None

            # 获取用户
            user = await self.user_service.get_user_by_id(api_key_obj.user_id)
            if not user or not user.is_active:
                logger.warning(f"API密钥关联的用户不存在或已禁用: {key_hint}...")
                return False, None, None

            # 更新使用统计
            api_key_obj.increment_usage()
            await self.db.commit()

            return True, user, api_key_obj

        except Exception as e:
            logger.error(f"验证API密钥失败: {e}")
            return False, None, None

    async def get_user_api_keys(self, user_id: int) -> List[ApiKey]:
        """
        获取用户的API密钥列表

        Args:
            user_id: 用户ID

        Returns:
            API密钥列表
        """
        try:
            stmt = select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取用户API密钥失败: {e}")
            return []

    async def update_api_key(
        self,
        api_key_id: int,
        user_id: int,
        key_name: Optional[str] = None,
        permissions: Optional[Dict[str, bool]] = None,
        is_active: Optional[bool] = None,
        usage_limit: Optional[int] = None,
        channel_ids: Optional[List[int]] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        更新API密钥

        Args:
            api_key_id: 密钥ID
            user_id: 用户ID
            key_name: 密钥名称
            permissions: 权限配置
            is_active: 是否激活
            usage_limit: 使用限制
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息)
        """
        try:
            # 获取API密钥
            api_key_obj = await self._get_api_key_by_id(api_key_id)
            if not api_key_obj or api_key_obj.user_id != user_id:
                return False, "API密钥不存在"

            # 更新字段
            if key_name is not None:
                # 检查名称是否重复
                if await self._check_key_name_exists(user_id, key_name, exclude_id=api_key_id):
                    return False, "密钥名称已存在"
                api_key_obj.key_name = key_name

            if permissions is not None:
                perm_result = validate_api_key_permissions(permissions)
                if not perm_result["valid"]:
                    return False, f"权限配置错误: {', '.join(perm_result['issues'])}"
                api_key_obj.permissions = perm_result["permissions"]

            if is_active is not None:
                api_key_obj.is_active = is_active

            if usage_limit is not None:
                api_key_obj.usage_limit = usage_limit

            if channel_ids is not None:
                # 整体替换语义；传空列表 = 清空绑定
                if channel_ids:
                    ok, err = await self._validate_channel_ids(user_id, channel_ids)
                    if not ok:
                        return False, err
                    api_key_obj.channel_ids = channel_ids
                else:
                    api_key_obj.channel_ids = []

            # 记录活动
            await self.user_service._log_user_activity(
                user_id,
                ActivityType.API_KEY_UPDATE,
                f"更新API密钥: {api_key_obj.key_name}",
                resource_type="api_key",
                resource_id=api_key_id,
                client_ip=client_ip,
                user_agent=user_agent,
            )

            await self.db.commit()

            logger.info(f"API密钥更新成功: {api_key_obj.key_name}")
            return True, "API密钥更新成功"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新API密钥失败: {e}")
            return False, "更新API密钥失败"

    async def delete_api_key(
        self, api_key_id: int, user_id: int, client_ip: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        删除API密钥

        Args:
            api_key_id: 密钥ID
            user_id: 用户ID
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息)
        """
        try:
            # 获取API密钥
            api_key_obj = await self._get_api_key_by_id(api_key_id)
            if not api_key_obj or api_key_obj.user_id != user_id:
                return False, "API密钥不存在"

            key_name = api_key_obj.key_name

            # 记录活动
            await self.user_service._log_user_activity(
                user_id,
                ActivityType.API_KEY_DELETE,
                f"删除API密钥: {key_name}",
                resource_type="api_key",
                resource_id=api_key_id,
                client_ip=client_ip,
                user_agent=user_agent,
            )

            # 删除密钥
            await self.db.delete(api_key_obj)
            await self.db.commit()

            logger.info(f"API密钥删除成功: {key_name}")
            return True, "API密钥删除成功"

        except Exception as e:
            await self.db.rollback()
            logger.error(f"删除API密钥失败: {e}")
            return False, "删除API密钥失败"

    async def _get_api_key_by_id(self, api_key_id: int) -> Optional[ApiKey]:
        """根据ID获取API密钥"""
        try:
            stmt = select(ApiKey).where(ApiKey.id == api_key_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取API密钥失败: {e}")
            return None

    async def _get_user_api_key_count(self, user_id: int) -> int:
        """获取用户的API密钥数量"""
        try:
            stmt = select(func.count(ApiKey.id)).where(ApiKey.user_id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"获取API密钥数量失败: {e}")
            return 0

    async def _validate_channel_ids(self, user_id: int, channel_ids: List[int]) -> Tuple[bool, Optional[str]]:
        """校验通知渠道归属：必须全部存在且属于该用户"""
        from app.models.notification_channel import NotificationChannel

        try:
            stmt = select(NotificationChannel.id).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.id.in_(list(set(channel_ids))),
            )
            result = await self.db.execute(stmt)
            found = {row[0] for row in result.all()}
            missing = [cid for cid in set(channel_ids) if cid not in found]
            if missing:
                return False, f"通知渠道不存在或不属于当前用户: {sorted(missing)}"
            return True, None
        except Exception as e:
            logger.error(f"校验通知渠道归属失败: {e}")
            return False, "校验通知渠道失败"

    async def _check_key_name_exists(self, user_id: int, key_name: str, exclude_id: Optional[int] = None) -> bool:
        """检查密钥名称是否存在"""
        try:
            stmt = select(func.count(ApiKey.id)).where(and_(ApiKey.user_id == user_id, ApiKey.key_name == key_name))
            if exclude_id:
                stmt = stmt.where(ApiKey.id != exclude_id)

            result = await self.db.execute(stmt)
            count = result.scalar() or 0
            return count > 0
        except Exception as e:
            logger.error(f"检查密钥名称失败: {e}")
            return True
