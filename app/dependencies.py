# -*- coding: utf-8 -*-
"""
依赖注入模块
"""

from typing import Optional, Annotated, Tuple
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_database_session
from app.models.user import User
from app.models.api_key import ApiKey
from app.services.auth_service import AuthService
from app.services.api_key_service import ApiKeyService
from app.services.mi_account_service import MiAccountService
from app.utils.api_key import extract_api_key_from_header


# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async for session in get_database_session():
        try:
            yield session
        finally:
            # 确保会话被正确关闭
            if session and not session.is_active:
                await session.close()


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """获取认证服务"""
    return AuthService(db)


async def get_api_key_service(db: AsyncSession = Depends(get_db)) -> ApiKeyService:
    """获取API密钥服务"""
    return ApiKeyService(db)


async def get_mi_account_service(db: AsyncSession = Depends(get_db)) -> MiAccountService:
    """获取小米账户服务"""
    return MiAccountService(db)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    获取当前认证用户

    Args:
        credentials: HTTP认证凭据
        auth_service: 认证服务

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败时抛出
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="需要认证", headers={"WWW-Authenticate": "Bearer"}
        )

    # 验证JWT令牌
    is_valid, user = await auth_service.verify_token(credentials.credentials)
    if not is_valid or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败", headers={"WWW-Authenticate": "Bearer"}
        )

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        当前活跃用户对象

    Raises:
        HTTPException: 用户不活跃时抛出
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户账户已被禁用")

    return current_user


async def verify_api_key(
    request: Request, api_key_service: ApiKeyService = Depends(get_api_key_service)
) -> tuple[User, ApiKey]:
    """
    验证API密钥

    Args:
        request: 请求对象
        api_key_service: API密钥服务

    Returns:
        用户和API密钥对象的元组

    Raises:
        HTTPException: API密钥验证失败时抛出
    """
    # 从Authorization头部获取API密钥
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少API密钥", headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key = extract_api_key_from_header(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API密钥格式错误", headers={"WWW-Authenticate": "ApiKey"}
        )

    # 验证API密钥
    is_valid, user, api_key_obj = await api_key_service.verify_api_key(api_key)
    if not is_valid or not user or not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API密钥无效", headers={"WWW-Authenticate": "ApiKey"}
        )

    return user, api_key_obj


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[User]:
    """
    获取可选的当前用户（不强制要求认证）

    Args:
        credentials: HTTP认证凭据
        auth_service: 认证服务

    Returns:
        当前用户对象或None
    """
    if not credentials:
        return None

    try:
        is_valid, user = await auth_service.verify_token(credentials.credentials)
        return user if is_valid else None
    except Exception as e:
        logger.warning(f"可选用户认证失败: {e}")
        return None


async def get_user_from_jwt_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> User:
    """
    支持JWT令牌或API密钥两种认证方式获取用户

    Args:
        request: 请求对象
        credentials: HTTP认证凭据
        auth_service: 认证服务
        api_key_service: API密钥服务

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败时抛出
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="需要认证", 
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # 首先尝试API密钥认证（以 xai_sk_ 开头）
    if token.startswith("xai_sk_"):
        try:
            is_valid, user, api_key_obj = await api_key_service.verify_api_key(token)
            if is_valid and user and api_key_obj:
                logger.debug(f"API密钥认证成功: 用户={user.username}")
                return user
        except Exception as e:
            logger.warning(f"API密钥认证异常: {e}")

    # 否则（或API密钥认证失败）尝试JWT认证
    try:
        is_valid, user = await auth_service.verify_token(token)
        if is_valid and user:
            logger.debug(f"JWT认证成功: 用户={user.username}")
            return user
    except Exception as e:
        logger.warning(f"JWT认证异常: {e}")

    # 两种认证方式都失败
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="认证失败", 
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_user_and_api_key_info(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> Tuple[User, Optional[int]]:
    """
    支持JWT令牌或API密钥两种认证方式获取用户和API密钥ID

    Args:
        request: 请求对象
        credentials: HTTP认证凭据
        auth_service: 认证服务
        api_key_service: API密钥服务

    Returns:
        (用户对象, API密钥ID或None)

    Raises:
        HTTPException: 认证失败时抛出
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="需要认证", 
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    
    # 首先尝试API密钥认证
    if token.startswith("xai_sk_"):
        try:
            is_valid, user, api_key_obj = await api_key_service.verify_api_key(token)
            if is_valid and user and api_key_obj:
                return user, api_key_obj.id
        except Exception as e:
            logger.warning(f"API密钥认证异常: {e}")

    # 如果API密钥认证失败，尝试JWT认证
    try:
        is_valid, user = await auth_service.verify_token(token)
        if is_valid and user:
            return user, None
    except Exception as e:
        logger.warning(f"JWT认证异常: {e}")

    # 两种认证方式都失败
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, 
        detail="认证失败", 
        headers={"WWW-Authenticate": "Bearer"}
    )


def get_client_ip(request: Request) -> str:
    """
    获取客户端IP地址

    仅依据反向代理头与连接信息解析，**不做任何外部网络调用**
    （此前版本会在本地请求时同步访问 httpbin.org / 建立 socket，
    在异步框架中造成阻塞，已移除）。

    Args:
        request: 请求对象

    Returns:
        客户端IP地址
    """
    from ipaddress import ip_address

    # 优先从反向代理头获取真实IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        try:
            ip_address(ip)
            return ip
        except ValueError:
            pass

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        try:
            ip_address(real_ip)
            return real_ip
        except ValueError:
            pass

    # 直接连接的客户端IP
    client_ip = request.client.host if request.client else None
    return client_ip if client_ip else "unknown"


def get_user_agent(request: Request) -> str:
    """
    获取用户代理

    Args:
        request: 请求对象

    Returns:
        用户代理字符串
    """
    return request.headers.get("User-Agent", "Unknown")


# 类型别名
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
AuthenticatedUser = Annotated[User, Depends(get_user_from_jwt_or_api_key)]
UserWithApiKey = Annotated[Tuple[User, Optional[int]], Depends(get_user_and_api_key_info)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
ClientIP = Annotated[str, Depends(get_client_ip)]
UserAgent = Annotated[str, Depends(get_user_agent)]
