# -*- coding: utf-8 -*-
"""
认证工具函数
"""

import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from loguru import logger

from app.config import settings


def hash_password(password: str) -> str:
    """
    哈希密码

    Args:
        password: 原始密码

    Returns:
        哈希后的密码
    """
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 原始密码
        hashed_password: 哈希后的密码

    Returns:
        验证结果
    """
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"密码验证异常: {e}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间差

    Returns:
        JWT令牌
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证访问令牌

    Args:
        token: JWT令牌

    Returns:
        解码后的数据，如果验证失败返回None
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    从令牌中获取用户ID

    Args:
        token: JWT令牌

    Returns:
        用户ID，如果验证失败返回None
    """
    payload = verify_access_token(token)
    if payload:
        return payload.get("user_id")
    return None


def create_user_token(user_id: int, username: str, email: str) -> str:
    """
    为用户创建令牌

    Args:
        user_id: 用户ID
        username: 用户名
        email: 邮箱

    Returns:
        JWT令牌
    """
    token_data = {"user_id": user_id, "username": username, "email": email, "type": "access_token"}
    return create_access_token(token_data)


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    验证密码强度

    Args:
        password: 密码

    Returns:
        验证结果字典
    """
    result = {"valid": True, "score": 0, "issues": []}

    # 长度检查
    if len(password) < settings.password_min_length:
        result["valid"] = False
        result["issues"].append(f"密码长度不能少于{settings.password_min_length}位")
    else:
        result["score"] += 1

    # 包含数字
    if any(c.isdigit() for c in password):
        result["score"] += 1
    else:
        result["issues"].append("密码应包含至少一个数字")

    # 包含小写字母
    if any(c.islower() for c in password):
        result["score"] += 1
    else:
        result["issues"].append("密码应包含至少一个小写字母")

    # 包含大写字母
    if any(c.isupper() for c in password):
        result["score"] += 1
    else:
        result["issues"].append("密码应包含至少一个大写字母")

    # 包含特殊字符
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if any(c in special_chars for c in password):
        result["score"] += 1
    else:
        result["issues"].append("密码应包含至少一个特殊字符")

    # 设置强度级别
    if result["score"] >= 4:
        result["strength"] = "strong"
    elif result["score"] >= 3:
        result["strength"] = "medium"
    elif result["score"] >= 2:
        result["strength"] = "weak"
    else:
        result["strength"] = "very_weak"
        result["valid"] = False

    return result
