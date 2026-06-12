# -*- coding: utf-8 -*-
"""
小米账户管理API路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path
from loguru import logger

from app.dependencies import get_current_active_user, get_client_ip, get_user_agent, DatabaseSession
from app.services.mi_account_service import MiAccountService
from app.schemas.mi_account import (
    CreateMiAccountRequest,
    SimplifiedCreateMiAccountRequest,
    UpdateMiAccountRequest,
    MiAccountResponse,
    MiAccountCreatedResponse,
    MiAccountDetailResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    SyncAccountResponse,
    MiAccountStatsResponse,
    AuthenticationTestRequest,
    AuthenticationTestResponse,
    DeviceResponse,
)
from app.schemas.auth import SuccessResponse
from app.models.user import User


router = APIRouter(prefix="/mi-accounts", tags=["小米账户管理"])


@router.get("", response_model=List[MiAccountResponse], summary="获取小米账户列表", description="获取当前用户的所有小米账户")
async def get_mi_accounts(db: DatabaseSession, current_user: User = Depends(get_current_active_user)):
    """获取小米账户列表"""
    try:
        mi_account_service = MiAccountService(db)
        mi_accounts = await mi_account_service.get_user_mi_accounts(current_user.id)
        return [MiAccountResponse.from_orm(account) for account in mi_accounts]

    except Exception as e:
        logger.error(f"获取小米账户列表错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/simplified", response_model=MiAccountCreatedResponse, summary="简化添加小米账户", description="使用小米账号和密码自动添加账户（推荐）")
async def create_mi_account_simplified(
    request: SimplifiedCreateMiAccountRequest,
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """简化添加小米账户 - 只需要小米账号和密码"""
    try:
        mi_account_service = MiAccountService(db)
        success, message, account_data = await mi_account_service.create_mi_account_simplified(
            user_id=current_user.id,
            mi_username=request.mi_username,
            mi_password=request.mi_password,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # 直接返回account_data中的字段，而不是嵌套在data中
        return MiAccountCreatedResponse(
            id=account_data["id"],
            mi_username=account_data["mi_username"],
            sync_status=account_data["sync_status"],
            created_at=account_data["created_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"简化添加小米账户错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("", response_model=MiAccountCreatedResponse, summary="添加小米账户（传统方式）", description="手动输入所有参数添加小米账户")
async def create_mi_account(
    request: CreateMiAccountRequest,
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """创建小米账户"""
    try:
        mi_account_service = MiAccountService(db)
        success, message, account_data = await mi_account_service.create_mi_account(
            user_id=current_user.id,
            mi_username=request.mi_username,
            mi_password=request.mi_password,
            device_id=request.device_id,
            user_id_mi=request.user_id,
            pass_token=request.pass_token,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return MiAccountCreatedResponse(**account_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建小米账户错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get(
    "/{account_id}", response_model=MiAccountDetailResponse, summary="获取小米账户详情", description="获取指定小米账户的详细信息，包括设备列表"
)
async def get_mi_account_detail(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
):
    """获取小米账户详情"""
    try:
        mi_account_service = MiAccountService(db)
        mi_account = await mi_account_service.get_mi_account_by_id(current_user.id, account_id)

        if not mi_account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小米账户不存在")

        return MiAccountDetailResponse.from_orm_with_devices(mi_account)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取小米账户详情错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.put("/{account_id}", response_model=SuccessResponse, summary="更新小米账户", description="更新指定的小米账户信息")
async def update_mi_account(
    request: UpdateMiAccountRequest,
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """更新小米账户"""
    try:
        mi_account_service = MiAccountService(db)

        # 检查账户是否存在
        mi_account = await mi_account_service.get_mi_account_by_id(current_user.id, account_id)
        if not mi_account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小米账户不存在")

        # 更新状态
        if request.is_active is not None:
            success, message = await mi_account_service.update_mi_account_status(
                user_id=current_user.id, account_id=account_id, is_active=request.is_active
            )

            if not success:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # TODO: 如果提供了新密码，更新密码
        if request.mi_password:
            # 这里可以实现密码更新逻辑
            pass

        return SuccessResponse(message="小米账户更新成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新小米账户错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.delete("/{account_id}", response_model=SuccessResponse, summary="删除小米账户", description="删除指定的小米账户及相关设备")
async def delete_mi_account(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
    client_ip: str = Depends(get_client_ip),
    user_agent: str = Depends(get_user_agent),
):
    """删除小米账户"""
    try:
        mi_account_service = MiAccountService(db)
        success, message = await mi_account_service.delete_mi_account(
            user_id=current_user.id, account_id=account_id, client_ip=client_ip, user_agent=user_agent
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return SuccessResponse(message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除小米账户错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/{account_id}/sync", response_model=SyncAccountResponse, summary="同步小米账户", description="手动同步指定小米账户的设备信息")
async def sync_mi_account(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
):
    """同步小米账户"""
    try:
        mi_account_service = MiAccountService(db)
        success, message = await mi_account_service.sync_mi_account(user_id=current_user.id, account_id=account_id)

        return SyncAccountResponse(success=success, message=message)

    except Exception as e:
        logger.error(f"同步小米账户错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post(
    "/{account_id}/test", response_model=TestConnectionResponse, summary="测试小米账户连接", description="测试指定小米账户的连接状态"
)
async def test_mi_account_connection(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
):
    """测试小米账户连接"""
    try:
        mi_account_service = MiAccountService(db)
        success, message, data = await mi_account_service.test_mi_account_connection(
            user_id=current_user.id, account_id=account_id
        )

        return TestConnectionResponse(success=success, message=message, data=data)

    except Exception as e:
        logger.error(f"测试小米账户连接错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.get(
    "/{account_id}/devices", response_model=List[DeviceResponse], summary="获取账户设备", description="获取指定小米账户下的所有设备"
)
async def get_account_devices(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
):
    """获取账户设备"""
    try:
        mi_account_service = MiAccountService(db)
        devices = await mi_account_service.get_account_devices(user_id=current_user.id, account_id=account_id)

        return [DeviceResponse.from_orm(device) for device in devices]

    except Exception as e:
        logger.error(f"获取账户设备错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post(
    "/{account_id}/refresh-devices", response_model=SyncAccountResponse, summary="刷新账户设备", description="刷新指定小米账户的设备列表"
)
async def refresh_account_devices(
    db: DatabaseSession,
    account_id: int = Path(..., description="小米账户ID"),
    current_user: User = Depends(get_current_active_user),
):
    """刷新账户设备"""
    try:
        mi_account_service = MiAccountService(db)
        success, message = await mi_account_service.refresh_account_devices(user_id=current_user.id, account_id=account_id)

        return SyncAccountResponse(success=success, message=message)

    except Exception as e:
        logger.error(f"刷新账户设备错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post(
    "/refresh-all-devices", response_model=SyncAccountResponse, summary="刷新所有设备", description="刷新当前用户所有小米账户的设备列表"
)
async def refresh_all_devices(
    db: DatabaseSession,
    current_user: User = Depends(get_current_active_user),
):
    """刷新所有设备"""
    try:
        mi_account_service = MiAccountService(db)
        success, message = await mi_account_service.refresh_all_devices(user_id=current_user.id)

        return SyncAccountResponse(success=success, message=message)

    except Exception as e:
        logger.error(f"刷新所有设备错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")





@router.get(
    "/stats/summary", response_model=MiAccountStatsResponse, summary="获取小米账户统计", description="获取当前用户的小米账户和设备统计信息"
)
async def get_mi_account_stats(db: DatabaseSession, current_user: User = Depends(get_current_active_user)):
    """获取小米账户统计"""
    try:
        mi_account_service = MiAccountService(db)
        mi_accounts = await mi_account_service.get_user_mi_accounts(current_user.id)

        total_accounts = len(mi_accounts)
        active_accounts = sum(1 for account in mi_accounts if account.is_active)
        synced_accounts = sum(1 for account in mi_accounts if account.is_synced)

        total_devices = 0
        online_devices = 0

        for account in mi_accounts:
            if account.devices:
                total_devices += len(account.devices)
                online_devices += sum(1 for device in account.devices if device.is_online)

        return MiAccountStatsResponse(
            total_accounts=total_accounts,
            active_accounts=active_accounts,
            synced_accounts=synced_accounts,
            total_devices=total_devices,
            online_devices=online_devices,
        )

    except Exception as e:
        logger.error(f"获取小米账户统计错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")


@router.post("/test-auth", response_model=AuthenticationTestResponse, summary="测试小米认证", description="测试小米账户认证，不保存账户信息")
async def test_mi_authentication(
    request: AuthenticationTestRequest, db: DatabaseSession, current_user: User = Depends(get_current_active_user)
):
    """测试小米认证"""
    try:
        mi_account_service = MiAccountService(db)

        # 这里应该调用实际的认证测试逻辑
        # 目前返回模拟数据
        success = True
        message = "认证测试成功"
        auth_data = {
            "device_id": f"test_device_{request.mi_username}",
            "user_id": f"test_user_{request.mi_username}",
            "pass_token": "test_token_***",
        }
        device_count = 2
        devices_preview = [{"name": "客厅小爱音箱", "model": "LX01"}, {"name": "卧室小爱音箱", "model": "LX04"}]

        return AuthenticationTestResponse(
            success=success,
            message=message,
            auth_data=auth_data,
            device_count=device_count,
            devices_preview=devices_preview,
        )

    except Exception as e:
        logger.error(f"测试小米认证错误: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误")
