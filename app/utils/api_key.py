# -*- coding: utf-8 -*-
"""
API密钥生成和验证工具
"""

import secrets
import hashlib
import hmac
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.config import settings


def generate_api_key() -> str:
    """
    生成API密钥

    Returns:
        API密钥字符串
    """
    # 生成随机密钥，使用Base62编码（数字+大小写字母）
    # 格式: xai_sk_<随机字符串>
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    key_length = settings.api_key_length - 7  # 减去前缀长度

    random_part = "".join(secrets.choice(alphabet) for _ in range(key_length))
    return f"xai_sk_{random_part}"


def generate_api_secret(api_key: str) -> str:
    """
    生成API密钥的签名

    Args:
        api_key: API密钥

    Returns:
        API密钥签名
    """
    # 使用HMAC-SHA256生成签名
    secret_key = settings.jwt_secret_key.encode("utf-8")
    message = api_key.encode("utf-8")
    signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return signature


def verify_api_key_signature(api_key: str, api_secret: str) -> bool:
    """
    验证API密钥签名

    Args:
        api_key: API密钥
        api_secret: API密钥签名

    Returns:
        验证结果
    """
    try:
        expected_secret = generate_api_secret(api_key)
        return hmac.compare_digest(api_secret, expected_secret)
    except Exception as e:
        logger.error(f"验证API密钥签名失败: {e}")
        return False


def extract_api_key_from_header(authorization: str) -> Optional[str]:
    """
    从Authorization头部提取API密钥

    Args:
        authorization: Authorization头部值

    Returns:
        API密钥，如果格式不正确返回None
    """
    if not authorization:
        return None

    # 支持的格式:
    # 1. Bearer xai_sk_xxxxx
    # 2. ApiKey xai_sk_xxxxx
    # 3. xai_sk_xxxxx

    parts = authorization.strip().split()

    if len(parts) == 2 and parts[0].lower() in ["bearer", "apikey"]:
        api_key = parts[1]
    elif len(parts) == 1:
        api_key = parts[0]
    else:
        return None

    # 验证API密钥格式
    if api_key.startswith("xai_sk_") and len(api_key) >= 16:
        return api_key

    return None


def mask_api_key(api_key: str) -> str:
    """
    掩码显示API密钥

    Args:
        api_key: API密钥

    Returns:
        掩码后的API密钥
    """
    if len(api_key) <= 12:
        return api_key

    return f"{api_key[:8]}****{api_key[-4:]}"


def validate_api_key_permissions(permissions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    验证API密钥权限配置

    Args:
        permissions: 权限配置字典

    Returns:
        验证结果
    """
    result = {"valid": True, "permissions": {}, "issues": []}

    # 支持的权限类型
    valid_permissions = {
        "speak": "语音播放权限",
        "get_devices": "获取设备列表权限",
        "manage_devices": "管理设备权限",
        "stop_speak": "停止播放权限",
        "set_volume": "设置音量权限",
        "get_status": "获取状态权限",
    }

    # 如果权限为None，使用默认权限
    if permissions is None:
        permissions = get_default_permissions()

    # 验证权限格式
    if not isinstance(permissions, dict):
        result["valid"] = False
        result["issues"].append("权限配置必须是字典格式")
        return result

    # 检查每个权限
    for perm, value in permissions.items():
        if perm not in valid_permissions:
            result["issues"].append(f"未知权限类型: {perm}")
            continue

        if not isinstance(value, bool):
            result["issues"].append(f"权限值必须是布尔类型: {perm}")
            result["valid"] = False
        else:
            result["permissions"][perm] = value

    # 至少需要一个权限
    if not any(result["permissions"].values()):
        result["valid"] = False
        result["issues"].append("至少需要启用一个权限")

    return result


def get_default_permissions() -> Dict[str, bool]:
    """
    获取默认权限配置

    Returns:
        默认权限字典
    """
    return {
        "speak": True,
        "get_devices": True,
        "manage_devices": False,
        "stop_speak": True,
        "set_volume": False,
        "get_status": True,
    }


def check_permission(permissions: Dict[str, Any], required_permission: str) -> bool:
    """
    检查是否具有指定权限

    Args:
        permissions: 权限配置
        required_permission: 需要的权限

    Returns:
        是否具有权限
    """
    if not permissions or not isinstance(permissions, dict):
        return False

    return permissions.get(required_permission, False)


class ApiKeyGenerator:
    """API密钥生成器类"""

    @staticmethod
    def create_new_key(key_name: str, permissions: Optional[Dict[str, bool]] = None) -> Dict[str, str]:
        """
        创建新的API密钥

        Args:
            key_name: 密钥名称
            permissions: 权限配置

        Returns:
            包含密钥信息的字典
        """
        api_key = generate_api_key()
        api_secret = generate_api_secret(api_key)

        if permissions is None:
            permissions = get_default_permissions()

        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "key_name": key_name,
            "permissions": permissions,
            "created_at": datetime.utcnow().isoformat(),
        }
