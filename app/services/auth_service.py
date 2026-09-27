# -*- coding: utf-8 -*-
"""
认证服务
"""

from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from loguru import logger

from app.models.user import User
from app.models.user_activity import ActivityType
from app.services.user_service import UserService
from app.utils.auth import create_user_token, verify_access_token, get_user_id_from_token


class AuthService:
    """认证服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        用户注册

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            display_name: 显示名称
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息, 用户数据)
        """
        try:
            # 检查用户名是否存在
            if await self.user_service.check_username_exists(username):
                return False, "用户名已存在", None

            # 检查邮箱是否存在
            if await self.user_service.check_email_exists(email):
                return False, "邮箱已存在", None

            # 创建用户
            user = await self.user_service.create_user(
                username=username,
                email=email,
                password=password,
                display_name=display_name,
                client_ip=client_ip,
                user_agent=user_agent,
            )

            if not user:
                return False, "用户创建失败", None

            logger.info(f"用户注册成功: {username}")
            return (
                True,
                "注册成功",
                {"user_id": user.id, "username": user.username, "email": user.email, "display_name": user.display_name},
            )

        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            return False, "注册失败，请稍后重试", None

    async def login_user(
        self, username_or_email: str, password: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        用户登录

        Args:
            username_or_email: 用户名或邮箱
            password: 密码
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            (是否成功, 消息, 登录数据)
        """
        try:
            # 用户认证
            user = await self.user_service.authenticate_user(username_or_email, password)
            if not user:
                return False, "用户名或密码错误", None

            # 生成JWT令牌（携带令牌版本，登出/改密后旧令牌自动失效）
            access_token = create_user_token(
                user.id, user.username, user.email, token_version=getattr(user, "token_version", 0) or 0
            )

            # 记录登录活动
            await self.user_service._log_user_activity(
                user.id, ActivityType.USER_LOGIN, f"用户登录: {user.username}", client_ip=client_ip, user_agent=user_agent
            )
            await self.db.commit()

            logger.info(f"用户登录成功: {user.username}")
            return (
                True,
                "登录成功",
                {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "display_name": user.display_name,
                        "is_active": user.is_active,
                        "is_verified": user.is_verified,
                        "created_at": user.created_at,
                        "last_login_at": user.last_login_at,
                    },
                },
            )

        except Exception as e:
            logger.error(f"用户登录失败: {e}")
            return False, "登录失败，请稍后重试", None

    async def verify_token(self, token: str) -> Tuple[bool, Optional[User]]:
        """
        验证JWT令牌

        Args:
            token: JWT令牌

        Returns:
            (是否有效, 用户对象)
        """
        try:
            # 验证令牌
            payload = verify_access_token(token)
            if not payload:
                return False, None

            # 获取用户
            user_id = payload.get("user_id")
            if not user_id:
                return False, None

            user = await self.user_service.get_user_by_id(user_id)
            if not user or not user.is_active:
                return False, None

            # 令牌版本校验：登出/改密会使旧令牌失效
            token_ver = payload.get("ver", 0) or 0
            current_ver = getattr(user, "token_version", 0) or 0
            if token_ver != current_ver:
                logger.info(f"令牌版本不匹配（已失效）: user_id={user_id}")
                return False, None

            return True, user

        except Exception as e:
            logger.error(f"令牌验证失败: {e}")
            return False, None

    async def logout_user(
        self, user_id: int, client_ip: Optional[str] = None, user_agent: Optional[str] = None
    ) -> bool:
        """
        用户登出

        Args:
            user_id: 用户ID
            client_ip: 客户端IP
            user_agent: 用户代理

        Returns:
            是否成功
        """
        try:
            user = await self.user_service.get_user_by_id(user_id)
            if not user:
                return False

            # 递增令牌版本，使该用户所有已签发 JWT 立即失效
            user.token_version = (getattr(user, "token_version", 0) or 0) + 1

            # 记录登出活动
            await self.user_service._log_user_activity(
                user_id, ActivityType.USER_LOGOUT, f"用户登出: {user.username}", client_ip=client_ip, user_agent=user_agent
            )
            await self.db.commit()

            logger.info(f"用户登出: {user.username}（令牌版本已递增）")
            return True

        except Exception as e:
            logger.error(f"用户登出失败: {e}")
            return False

    async def check_username_available(self, username: str) -> Tuple[bool, str]:
        """
        检查用户名是否可用

        Args:
            username: 用户名

        Returns:
            (是否可用, 消息)
        """
        try:
            if len(username) < 3:
                return False, "用户名长度至少3个字符"

            if len(username) > 50:
                return False, "用户名长度不能超过50个字符"

            # 检查字符是否合法（只允许字母、数字、下划线）
            if not username.replace("_", "").isalnum():
                return False, "用户名只能包含字母、数字和下划线"

            # 检查是否已存在
            exists = await self.user_service.check_username_exists(username)
            if exists:
                return False, "用户名已存在"

            return True, "用户名可用"

        except Exception as e:
            logger.error(f"检查用户名失败: {e}")
            return False, "检查用户名失败"

    async def check_email_available(self, email: str) -> Tuple[bool, str]:
        """
        检查邮箱是否可用

        Args:
            email: 邮箱地址

        Returns:
            (是否可用, 消息)
        """
        try:
            # 简单的邮箱格式验证
            if "@" not in email or "." not in email.split("@")[1]:
                return False, "邮箱格式不正确"

            # 检查是否已存在
            exists = await self.user_service.check_email_exists(email)
            if exists:
                return False, "邮箱已存在"

            return True, "邮箱可用"

        except Exception as e:
            logger.error(f"检查邮箱失败: {e}")
            return False, "检查邮箱失败"

    async def get_current_user(self, token: str) -> Optional[User]:
        """
        获取当前用户

        Args:
            token: JWT令牌

        Returns:
            用户对象
        """
        try:
            is_valid, user = await self.verify_token(token)
            return user if is_valid else None
        except Exception as e:
            logger.error(f"获取当前用户失败: {e}")
            return None
