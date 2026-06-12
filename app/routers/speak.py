# -*- coding: utf-8 -*-
"""
语音播放API路由
提供语音播放相关的REST API接口
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.models.speak import SpeakRequest, SpeakResponse, SpeakStatus, DeviceInfo, DeviceListResponse
from app.services.speak_service import speak_service
from app.dependencies import (
    DatabaseSession,
    AuthenticatedUser,
    ClientIP,
    UserAgent,
    UserWithApiKey,
)

# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["语音播放"])


@router.post("/speak", response_model=SpeakResponse, summary="播放文字内容（支持多设备）")
async def speak_text(
    request: SpeakRequest,
    db: DatabaseSession,
    user_and_api: UserWithApiKey,
    client_ip: ClientIP,
    user_agent: UserAgent,
):
    """
    让小爱音箱播放指定的文字内容，支持单设备和多设备播报

    ## 基础参数
    - **text**: 要播放的文字内容（必填，1-500字符）
    - **device_id**: 设备ID（可选）
      - 单设备：字符串格式，如 "device1"
      - 多设备：字符串数组格式，如 ["device1", "device2", "device3"]
      - 不指定则使用默认设备
    - **volume**: 播报时音量大小（可选，0-100，不指定则不调整音量）
    - **endvolume**: 播报完成后恢复的音量（可选，0-100，不指定则不恢复音量）
    - **speed**: 语速倍率（可选，0.5-2.0，默认1.0）
    - **voice_type**: 音色类型（可选，male/female/child，默认female）

    ## 多设备播报特性
    - ✅ **并行执行**: 多设备任务同时启动，提高效率
    - ✅ **独立任务**: 每个设备创建独立任务ID，便于状态追踪
    - ✅ **向后兼容**: 完全兼容现有单设备API调用
    - ✅ **错误隔离**: 单个设备失败不影响其他设备播报

    ## 返回格式
    - 单设备：返回单个任务ID（字符串）
    - 多设备：返回任务ID数组（字符串数组）

    ## 使用示例
    ```json
    // 单设备播报
    {
      "text": "Hello World",
      "device_id": "device1"
    }

    // 多设备播报
    {
      "text": "紧急通知：会议将在5分钟后开始",
      "device_id": ["device1", "device2", "device3"],
      "volume": 80
    }
    ```
    """
    logger.info(f"收到语音播放请求: {request.text[:50]}...")

    try:
        current_user, api_key_id = user_and_api
        response = await speak_service.speak_text(
            request,
            user_id=current_user.id,
            db=db,
            api_key_id=api_key_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        if response.success:
            logger.info(f"创建播放任务成功: {response.task_id}")
        else:
            logger.warning(f"创建播放任务失败: {response.message}")

        return response

    except Exception as e:
        logger.error(f"播放请求处理异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/speak/{device_id}", response_model=SpeakResponse, summary="指定设备播放文字")
async def speak_text_to_device(
    device_id: str,
    request: SpeakRequest,
    db: DatabaseSession,
    user_and_api: UserWithApiKey,
    client_ip: ClientIP,
    user_agent: UserAgent,
):
    """
    让指定设备播放文字内容

    - **device_id**: 设备ID（路径参数）
    - **request**: 播放请求参数
    """
    logger.info(f"收到指定设备播放请求: 设备={device_id}, 内容={request.text[:50]}...")

    # 强制设置设备ID
    request.device_id = device_id

    try:
        current_user, api_key_id = user_and_api
        response = await speak_service.speak_text(
            request,
            user_id=current_user.id,
            db=db,
            api_key_id=api_key_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return response

    except Exception as e:
        logger.error(f"指定设备播放请求处理异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/speak/status/{task_id}", response_model=SpeakStatus, summary="查询播放状态")
async def get_speak_status(task_id: str):
    """
    查询语音播放任务状态

    - **task_id**: 任务ID

    返回任务的详细状态信息
    """
    logger.debug(f"查询任务状态: {task_id}")

    try:
        status = await speak_service.get_task_status(task_id)

        if status is None:
            raise HTTPException(status_code=404, detail="任务不存在")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/speak/stop", summary="停止播放")
async def stop_speak(
    task_id: Optional[str] = Query(None, description="任务ID"), device_id: Optional[str] = Query(None, description="设备ID")
):
    """
    停止语音播放

    - **task_id**: 任务ID（可选）
    - **device_id**: 设备ID（可选）

    至少需要提供task_id或device_id中的一个
    """
    if not task_id and not device_id:
        raise HTTPException(status_code=400, detail="必须提供task_id或device_id")

    logger.info(f"收到停止播放请求: task_id={task_id}, device_id={device_id}")

    try:
        result = await speak_service.stop_speak(task_id=task_id, device_id=device_id)

        if result["success"]:
            return {"success": True, "message": result["message"]}
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止播放异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/devices", response_model=DeviceListResponse, summary="获取设备列表")
async def get_devices(db: DatabaseSession, current_user: AuthenticatedUser):
    """
    获取所有可用的小爱音箱设备列表

    返回设备的基本信息和状态
    """
    logger.info("收到获取设备列表请求")

    try:
        devices = await speak_service.get_devices(user_id=current_user.id, db=db)

        return DeviceListResponse(success=True, message=f"获取到 {len(devices)} 个设备", devices=devices, total=len(devices))

    except Exception as e:
        logger.error(f"获取设备列表异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/devices/{device_id}", response_model=DeviceInfo, summary="获取设备详情")
async def get_device_info(device_id: str):
    """
    获取指定设备的详细信息

    - **device_id**: 设备ID
    """
    logger.debug(f"查询设备信息: {device_id}")

    try:
        device = await speak_service.get_device_status(device_id)

        if device is None:
            raise HTTPException(status_code=404, detail="设备不存在")

        return device

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设备信息异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/devices/scan", summary="扫描设备")
async def scan_devices():
    """
    重新扫描小爱音箱设备

    强制刷新设备列表缓存
    """
    logger.info("收到设备扫描请求")

    try:
        # 强制刷新设备列表
        from app.utils.mi_service import mi_service_wrapper

        devices = await mi_service_wrapper.get_devices(force_refresh=True)

        return {"success": True, "message": f"扫描完成，发现 {len(devices)} 个设备", "device_count": len(devices)}

    except Exception as e:
        logger.error(f"设备扫描异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/devices/{device_id}/volume", summary="设置设备音量")
async def set_device_volume(
    device_id: str,
    db: DatabaseSession,
    current_user: AuthenticatedUser,
    volume: int = Query(..., ge=0, le=100, description="音量大小(0-100)")
):
    """
    设置指定设备的音量

    - **device_id**: 设备ID（路径参数）
    - **volume**: 音量大小（0-100）
    """
    logger.info(f"收到设置设备音量请求: 设备={device_id}, 音量={volume}")

    try:
        result = await speak_service.set_device_volume(
            device_id=device_id,
            volume=volume,
            user_id=current_user.id,
            db=db
        )

        if result["success"]:
            return {"success": True, "message": f"设备 {device_id} 音量已设置为 {volume}", "device_id": device_id, "volume": volume}
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "设置音量失败"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置设备音量异常: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


# 健康检查接口
@router.get("/health", summary="健康检查")
async def health_check():
    """
    API健康检查接口
    """
    return {"status": "healthy", "service": "miAPI", "version": "1.0.0"}
