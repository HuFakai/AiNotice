# -*- coding: utf-8 -*-
"""
用户服务
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from datetime import datetime
from loguru import logger

from app.models.user import User
from app.models.user_activity import UserActivity, ActivityType
from app.utils.auth import hash_password, verify_password, validate_password_strength


class UserService:
    """用户服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[User]:
        """
        创建新用户

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            display_name: 显示名称
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            创建的用户对象，如果失败返回None
        """
        try:
            # 验证用户名和邮箱是否已存在
            if await self.check_username_exists(username):
                logger.warning(f"用户名已存在: {username}")
                return None

            if await self.check_email_exists(email):
                logger.warning(f"邮箱已存在: {email}")
                return None

            # 验证密码强度
            password_check = validate_password_strength(password)
            if not password_check["valid"]:
                logger.warning(f"密码强度不足: {password_check['issues']}")
                return None

            # 创建用户
            password_hash = hash_password(password)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                display_name=display_name or username,
                is_active=True,
                is_verified=False,
            )

            self.db.add(user)
            await self.db.flush()  # 获取用户ID

            # 记录用户注册活动
            await self._log_user_activity(
                user.id, ActivityType.USER_REGISTER, f"用户注册成功: {username}", client_ip=client_ip, user_agent=user_agent
            )

            await self.db.commit()
            logger.info(f"用户创建成功: {username} (ID: {user.id})")
            return user

        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建用户失败: {e}")
            return None

    async def authenticate_user(self, username_or_email: str, password: str) -> Optional[User]:
        """
        用户认证

        Args:
            username_or_email: 用户名或邮箱
            password: 密码

        Returns:
            认证成功的用户对象，失败返回None
        """
        try:
            # 查找用户（支持用户名或邮箱登录）
            stmt = select(User).where(
                and_(or_(User.username == username_or_email, User.email == username_or_email), User.is_active == True)
            )
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"用户不存在或已禁用: {username_or_email}")
                return None

            # 验证密码
            if not verify_password(password, user.password_hash):
                logger.warning(f"密码错误: {username_or_email}")
                return None

            # 更新最后登录时间
            user.last_login_at = datetime.utcnow()
            await self.db.commit()

            logger.info(f"用户认证成功: {user.username} (ID: {user.id})")
            return user

        except Exception as e:
            await self.db.rollback()
            logger.error(f"用户认证失败: {e}")
            return None

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据ID获取用户

        Args:
            user_id: 用户ID

        Returns:
            用户对象，不存在返回None
        """
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            用户对象，不存在返回None
        """
        try:
            stmt = select(User).where(User.username == username)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱获取用户

        Args:
            email: 邮箱

        Returns:
            用户对象，不存在返回None
        """
        try:
            stmt = select(User).where(User.email == email)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    async def check_username_exists(self, username: str) -> bool:
        """
        检查用户名是否存在

        Args:
            username: 用户名

        Returns:
            是否存在
        """
        try:
            stmt = select(func.count(User.id)).where(User.username == username)
            result = await self.db.execute(stmt)
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"检查用户名失败: {e}")
            return True  # 出错时返回True，防止重复创建

    async def check_email_exists(self, email: str) -> bool:
        """
        检查邮箱是否存在

        Args:
            email: 邮箱

        Returns:
            是否存在
        """
        try:
            stmt = select(func.count(User.id)).where(User.email == email)
            result = await self.db.execute(stmt)
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"检查邮箱失败: {e}")
            return True  # 出错时返回True，防止重复创建

    async def update_user_profile(
        self,
        user_id: int,
        display_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        更新用户资料

        Args:
            user_id: 用户ID
            display_name: 显示名称
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            是否更新成功
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            if display_name is not None:
                user.display_name = display_name

            # 记录活动
            await self._log_user_activity(
                user_id, ActivityType.USER_UPDATE_PROFILE, "更新用户资料", client_ip=client_ip, user_agent=user_agent
            )

            await self.db.commit()
            logger.info(f"用户资料更新成功: {user.username}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新用户资料失败: {e}")
            return False

    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        修改密码

        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            是否修改成功
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            # 验证旧密码
            if not verify_password(old_password, user.password_hash):
                logger.warning(f"旧密码错误: {user.username}")
                return False

            # 验证新密码强度
            password_check = validate_password_strength(new_password)
            if not password_check["valid"]:
                logger.warning(f"新密码强度不足: {password_check['issues']}")
                return False

            # 更新密码
            user.password_hash = hash_password(new_password)

            # 记录活动
            await self._log_user_activity(
                user_id, ActivityType.USER_UPDATE_PROFILE, "修改密码", client_ip=client_ip, user_agent=user_agent
            )

            await self.db.commit()
            logger.info(f"密码修改成功: {user.username}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改密码失败: {e}")
            return False

    async def get_user_activities(self, user_id: int, limit: int = 50, offset: int = 0) -> List[UserActivity]:
        """
        获取用户活动记录

        Args:
            user_id: 用户ID
            limit: 限制数量
            offset: 偏移量

        Returns:
            活动记录列表
        """
        try:
            stmt = (
                select(UserActivity)
                .where(UserActivity.user_id == user_id)
                .order_by(UserActivity.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取用户活动失败: {e}")
            return []

    async def _log_user_activity(
        self,
        user_id: int,
        activity_type: str,
        description: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        记录用户活动

        Args:
            user_id: 用户ID
            activity_type: 活动类型
            description: 活动描述
            resource_type: 资源类型
            resource_id: 资源ID
            client_ip: 客户端IP
            user_agent: 用户代理
        """
        try:
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                activity_description=description,
                resource_type=resource_type,
                resource_id=resource_id,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            self.db.add(activity)
        except Exception as e:
            logger.error(f"记录用户活动失败: {e}")
