# -*- coding: utf-8 -*-
"""
认证相关API路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger

from app.dependencies import get_auth_service, get_current_user, get_client_ip, get_user_agent, DatabaseSession
from app.services.auth_service import AuthService
from app.config import settings
from app.utils.rate_limit import login_limiter, register_limiter, availability_limiter
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    CheckUsernameRequest,
    CheckEmailRequest,
    AvailabilityResponse,
    SuccessResponse,
    ErrorResponse,
    UserResponse,
)
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=SuccessResponse, summary="用户注册", description="注册新用户账户")
async def register(
    request: RegisterRequest,
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    auth_service: AuthService = Depends(get_auth_service),
):
    """用户注册"""
    try:
        if not settings.registration_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前已关闭用户注册")

        blocked, remaining = register_limiter.check(f"reg:{client_ip}")
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"注册尝试过于频繁，请 {max(remaining // 60, 1)} 分钟后再试",
            )

        success, message, user_data = await auth_service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            display_name=request.display_name,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            register_limiter.record_failure(f"reg:{client_ip}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return SuccessResponse(message=message, data=user_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户注册API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/login", response_model=TokenResponse, summary="用户登录", description="用户登录获取访问令牌")
async def login(
    request: LoginRequest,
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    auth_service: AuthService = Depends(get_auth_service),
):
    """用户登录"""
    try:
        # 按 IP 与 IP+账号 双维度防暴力破解
        ip_key = f"login:ip:{client_ip}"
        account_key = f"login:acct:{client_ip}:{request.username_or_email}"
        for key in (ip_key, account_key):
            blocked, remaining = login_limiter.check(key)
            if blocked:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"登录尝试过于频繁，请 {max(remaining // 60, 1)} 分钟后再试",
                )

        success, message, login_data = await auth_service.login_user(
            username_or_email=request.username_or_email,
            password=request.password,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            login_limiter.record_failure(ip_key)
            login_limiter.record_failure(account_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

        login_limiter.reset(ip_key)
        login_limiter.reset(account_key)
        return TokenResponse(**login_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/logout", response_model=SuccessResponse, summary="用户登出", description="用户登出（注销当前会话）")
async def logout(
    current_user: User = Depends(get_current_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    auth_service: AuthService = Depends(get_auth_service),
):
    """用户登出"""
    try:
        success = await auth_service.logout_user(user_id=current_user.id, client_ip=client_ip, user_agent=user_agent)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="登出失败")

        return SuccessResponse(message="登出成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登出API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息", description="获取当前登录用户的详细信息")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse.from_orm(current_user)


@router.post("/verify", response_model=UserResponse, summary="验证令牌", description="验证JWT令牌是否有效并返回用户信息")
async def verify_token(current_user: User = Depends(get_current_user)):
    """验证令牌"""
    return UserResponse.from_orm(current_user)


@router.post("/check-username", response_model=AvailabilityResponse, summary="检查用户名可用性", description="检查用户名是否可用")
async def check_username(
    request: CheckUsernameRequest,
    client_ip: str = Depends(get_client_ip),
    auth_service: AuthService = Depends(get_auth_service),
):
    """检查用户名可用性"""
    try:
        blocked, _ = availability_limiter.check(f"chk:{client_ip}")
        if blocked:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求过于频繁，请稍后再试")
        availability_limiter.record_failure(f"chk:{client_ip}")  # 该接口只有消耗性质，用失败计数做限流

        available, message = await auth_service.check_username_available(request.username)
        return AvailabilityResponse(available=available, message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查用户名API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/check-email", response_model=AvailabilityResponse, summary="检查邮箱可用性", description="检查邮箱是否可用")
async def check_email(
    request: CheckEmailRequest,
    client_ip: str = Depends(get_client_ip),
    auth_service: AuthService = Depends(get_auth_service),
):
    """检查邮箱可用性"""
    try:
        blocked, _ = availability_limiter.check(f"chk:{client_ip}")
        if blocked:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="请求过于频繁，请稍后再试")
        availability_limiter.record_failure(f"chk:{client_ip}")

        available, message = await auth_service.check_email_available(request.email)
        return AvailabilityResponse(available=available, message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"检查邮箱API错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")
