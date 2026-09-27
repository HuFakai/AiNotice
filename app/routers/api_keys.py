# -*- coding: utf-8 -*-
"""
API密钥管理路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path
from loguru import logger

from app.dependencies import get_current_active_user, get_api_key_service, get_client_ip, get_user_agent
from app.services.api_key_service import ApiKeyService
from app.schemas.api_key import CreateApiKeyRequest, UpdateApiKeyRequest, ApiKeyResponse, ApiKeyCreatedResponse
from app.schemas.auth import SuccessResponse
from app.models.user import User


router = APIRouter(prefix="/api-keys", tags=["API密钥管理"])


def _display_key(api_key_obj) -> str:
    """列表/详情展示用的掩码密钥（哈希存储行用前缀，历史明文行走旧掩码属性）"""
    prefix = getattr(api_key_obj, "key_prefix", None)
    if prefix:
        return f"{prefix}••••"
    return api_key_obj.masked_api_key


@router.get("", response_model=List[ApiKeyResponse], summary="获取API密钥列表", description="获取当前用户的所有API密钥（密钥仅掩码展示）")
async def get_api_keys(
    current_user: User = Depends(get_current_active_user), api_key_service: ApiKeyService = Depends(get_api_key_service)
):
    """获取API密钥列表"""
    try:
        api_keys = await api_key_service.get_user_api_keys(current_user.id)
        return [
            ApiKeyResponse(
                id=ak.id,
                key_name=ak.key_name,
                api_key=_display_key(ak),
                is_active=ak.is_active,
                is_expired=ak.is_expired,
                is_usage_exceeded=ak.is_usage_exceeded,
                is_valid=ak.is_valid,
                permissions=ak.permissions,
                usage_count=ak.usage_count,
                usage_limit=ak.usage_limit,
                last_used_at=ak.last_used_at,
                expires_at=ak.expires_at,
                created_at=ak.created_at,
                updated_at=ak.updated_at,
            )
            for ak in api_keys
        ]

    except Exception as e:
        logger.error(f"获取API密钥列表错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("", response_model=ApiKeyCreatedResponse, summary="创建API密钥", description="为当前用户创建新的API密钥")
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
):
    """创建API密钥"""
    try:
        success, message, key_data = await api_key_service.create_api_key(
            user_id=current_user.id,
            key_name=request.key_name,
            permissions=request.permissions,
            expires_in_days=request.expires_in_days,
            usage_limit=request.usage_limit,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        try:
            response = ApiKeyCreatedResponse(**key_data)
            return response
        except Exception as validation_error:
            logger.error(f"Pydantic验证错误: {validation_error}")
            logger.error(f"返回数据: {key_data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据格式错误: {str(validation_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建API密钥错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.put("/{api_key_id}", response_model=SuccessResponse, summary="更新API密钥", description="更新指定的API密钥配置")
async def update_api_key(
    api_key_id: int = Path(..., description="API密钥ID"),
    request: UpdateApiKeyRequest = ...,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
):
    """更新API密钥"""
    try:
        success, message = await api_key_service.update_api_key(
            api_key_id=api_key_id,
            user_id=current_user.id,
            key_name=request.key_name,
            permissions=request.permissions,
            is_active=request.is_active,
            usage_limit=request.usage_limit,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return SuccessResponse(message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新API密钥错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.delete("/{api_key_id}", response_model=SuccessResponse, summary="删除API密钥", description="删除指定的API密钥")
async def delete_api_key(
    api_key_id: int = Path(..., description="API密钥ID"),
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
    api_key_service: ApiKeyService = Depends(get_api_key_service),
):
    """删除API密钥"""
    try:
        success, message = await api_key_service.delete_api_key(
            api_key_id=api_key_id, user_id=current_user.id, client_ip=client_ip, user_agent=user_agent
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return SuccessResponse(message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除API密钥错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")
