# -*- coding: utf-8 -*-
"""
小米账户管理API路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Path, Request
from fastapi.responses import Response
from loguru import logger

from app.dependencies import get_current_active_user, get_client_ip, get_user_agent, DatabaseSession
from app.services.mi_account_service import MiAccountService
from app.services.mi_qr_service import mi_qr_login_service
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
    QrCreateRequest,
    QrCreateResponse,
    QrStatusResponse,
)
from app.schemas.auth import SuccessResponse
from app.models.mi_account import SyncStatus
from app.models.user import User


router = APIRouter(prefix="/mi-accounts", tags=["小米账户管理"])


def get_client_ip_from_request(request: Request) -> str:
    """从请求中解析客户端 IP（复用 dependencies 的代理头策略）"""
    from app.dependencies import get_client_ip as _gcip

    try:
        return _gcip(request)
    except Exception:
        return "unknown"


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

        # 更新小米密码：重新加密落库，并标记待同步（下次同步用新凭据重新认证）
        if request.mi_password:
            from app.utils.encryption import encrypt_password

            mi_account.mi_password_encrypted = encrypt_password(request.mi_password)
            mi_account.sync_status = SyncStatus.PENDING
            mi_account.error_message = None
            db.add(mi_account)
            await db.commit()
            logger.info(f"小米账户密码已更新: {mi_account.mi_username} (ID: {account_id})")
            return SuccessResponse(message="小米账户密码已更新，请执行同步以验证新凭据")

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


@router.post("/qr/create", response_model=QrCreateResponse, summary="发起扫码登录", description="创建小米账号扫码登录会话，返回二维码地址")
async def create_qr_login(
    request: QrCreateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """创建扫码登录会话"""
    try:
        info = await mi_qr_login_service.create_session(current_user.id, request.name)
        return QrCreateResponse(**info)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"创建扫码登录会话失败: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="获取二维码失败，请稍后重试")


@router.get("/qr/{session_id}/image", summary="获取扫码二维码图片", description="返回扫码登录二维码 PNG 图片")
async def get_qr_login_image(
    session_id: str = Path(..., description="扫码会话ID"),
    current_user: User = Depends(get_current_active_user),
):
    """代理下载二维码 PNG（避免混合内容与跨域问题）"""
    try:
        data = await mi_qr_login_service.get_qr_image(session_id, current_user.id)
    except Exception as e:
        logger.error(f"下载二维码图片失败: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="二维码下载失败")

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="扫码会话不存在或已过期")
    return Response(content=data, media_type="image/png")


@router.get("/qr/{session_id}/status", response_model=QrStatusResponse, summary="查询扫码状态", description="轮询扫码登录状态，确认后自动创建/更新小米账户")
async def get_qr_login_status(
    request: Request,
    db: DatabaseSession,
    session_id: str = Path(..., description="扫码会话ID"),
    current_user: User = Depends(get_current_active_user),
):
    """轮询扫码状态；确认后自动落库（凭据加密存储，不回传前端）"""
    result = await mi_qr_login_service.poll_status(session_id, current_user.id)

    if result.get("status") == "confirmed":
        payload = await mi_qr_login_service.consume_result(session_id, current_user.id)
        if payload:
            mi_account_service = MiAccountService(db)
            try:
                success, message, account_data = await mi_account_service.create_mi_account_from_token(
                    user_id=current_user.id,
                    mi_user_id=payload.get("mi_user_id") or "",
                    mi_pass_token=payload.get("mi_pass_token") or "",
                    display_name=payload.get("display_name"),
                    client_ip=get_client_ip_from_request(request),
                )
            except Exception:
                logger.exception("扫码登录绑定处理异常")
                success, message = False, "绑定处理异常，请重新扫码"
            if success:
                result["account_id"] = account_data["id"]
                result["mi_username"] = account_data["mi_username"]
            else:
                result["status"] = "error"
                result["message"] = message
                await mi_qr_login_service.mark_error(session_id, current_user.id, message)

    return QrStatusResponse(**result)


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
