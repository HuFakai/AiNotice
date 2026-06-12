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
    logger.info(f"混合认证开始: token前缀={token[:20]}...")
    
    # 首先尝试API密钥认证
    # 检查token是否是API密钥格式（以xai_sk_开头）
    if token.startswith("xai_sk_"):
        logger.info("检测到API密钥格式，尝试API密钥认证")
        try:
            is_valid, user, api_key_obj = await api_key_service.verify_api_key(token)
            if is_valid and user and api_key_obj:
                logger.info(f"API密钥认证成功: 用户={user.username}, 密钥={api_key_obj.key_name}")
                return user
            else:
                logger.warning(f"API密钥认证失败: is_valid={is_valid}, user={user}, api_key_obj={api_key_obj}")
        except Exception as e:
            logger.warning(f"API密钥认证异常: {e}")
    else:
        logger.info("检测到JWT格式，尝试JWT认证")

    # 如果API密钥认证失败，尝试JWT认证
    try:
        is_valid, user = await auth_service.verify_token(token)
        if is_valid and user:
            logger.info(f"JWT认证成功: 用户={user.username}")
            return user
        else:
            logger.warning(f"JWT认证失败: is_valid={is_valid}, user={user}")
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

    Args:
        request: 请求对象

    Returns:
        客户端IP地址
    """
    import socket
    import requests
    from ipaddress import ip_address, AddressValueError
    
    # 尝试从代理头部获取真实IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        try:
            # 验证IP地址格式
            ip_address(ip)
            return ip
        except AddressValueError:
            pass

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        try:
            ip_address(real_ip)
            return real_ip
        except AddressValueError:
            pass

    # 获取直接连接的IP
    client_ip = request.client.host if request.client else None
    
    # 如果是本地IP（127.0.0.1或localhost），尝试获取真实的网络IP
    if client_ip in ["127.0.0.1", "localhost", "::1"] or not client_ip:
        try:
            # 方法1: 通过连接外部服务获取本机公网IP
            try:
                response = requests.get("https://httpbin.org/ip", timeout=3)
                if response.status_code == 200:
                    public_ip = response.json().get("origin")
                    if public_ip:
                        # 如果有多个IP，取第一个
                        public_ip = public_ip.split(",")[0].strip()
                        ip_address(public_ip)  # 验证IP格式
                        return public_ip
            except:
                pass
            
            # 方法2: 获取本机局域网IP
            try:
                # 创建一个UDP socket连接到外部地址（不会实际发送数据）
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    if local_ip and local_ip != "127.0.0.1":
                        ip_address(local_ip)  # 验证IP格式
                        return local_ip
            except:
                pass
                
        except Exception:
            pass
    
    # 如果以上方法都失败，返回原始IP或unknown
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
