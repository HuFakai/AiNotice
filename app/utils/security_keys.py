# -*- coding: utf-8 -*-
"""
密钥安全管理

在启动阶段保证关键密钥不为弱默认值：
- jwt_secret_key：缺失/占位符/过短时自动生成强随机值并写回 .env
- encryption_key：缺失时自动生成（数据加密与 JWT 签名从此分离）
- 旧的弱 JWT 密钥会保留为 ENCRYPTION_LEGACY_PASSWORD，
  使历史上由它派生加密密钥的数据仍可解密
"""

import os
import secrets
from pathlib import Path
from loguru import logger

from app.config import settings

_WEAK_JWT_VALUES = {"", "CHANGE_ME_IN_ENV", "miapi_jwt_secret_key_2025", "secret", "jwt_secret"}
_MIN_KEY_LENGTH = 32
ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


def _is_weak_jwt_key(value: str) -> bool:
    return (not value) or value.strip() in _WEAK_JWT_VALUES or len(value) < _MIN_KEY_LENGTH


def _persist_env_value(key: str, value: str) -> None:
    """把配置写入项目根目录的 .env（存在则替换该行，不存在则追加）。"""
    env_path = Path(".env")
    line = f"{key}={value}"
    try:
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            replaced = False
            for i, existing in enumerate(lines):
                if existing.strip().startswith(f"{key}="):
                    lines[i] = line
                    replaced = True
                    break
            if not replaced:
                lines.append(line)
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            env_path.write_text(line + "\n", encoding="utf-8")
    except OSError as e:
        # 写不进去（只读部署等）也能运行，但每次启动都会重新生成随机密钥，
        # 因此必须显式提示用户改为手动配置
        logger.critical(f"无法将自动生成的 {key} 写入 .env: {e}。"
                        f"请手动在 .env 中固定该值，否则每次重启后已加密数据将无法解密。")


def ensure_strong_secrets() -> None:
    """
    启动期密钥检查与自动修复。

    必须在应用开始处理请求、且尚未使用任何加密/签名能力之前调用。
    """
    old_jwt_key = settings.jwt_secret_key

    # 1) JWT 算法白名单
    if settings.jwt_algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise RuntimeError(
            f"不支持的 JWT_ALGORITHM: {settings.jwt_algorithm}，"
            f"允许的算法: {sorted(ALLOWED_JWT_ALGORITHMS)}"
        )

    # 2) JWT 密钥弱值检查
    jwt_was_weak = _is_weak_jwt_key(old_jwt_key)
    if jwt_was_weak:
        new_key = secrets.token_urlsafe(48)
        settings.jwt_secret_key = new_key
        _persist_env_value("JWT_SECRET_KEY", new_key)
        logger.warning("检测到弱 JWT_SECRET_KEY，已自动生成强随机值并写入 .env（原有登录态将失效）")

    # 3) 数据加密密钥与 JWT 密钥分离
    if not settings.encryption_key:
        if jwt_was_weak:
            # 历史数据由旧 JWT 值派生密钥加密，保留旧值作为解密回退
            settings.encryption_key = secrets.token_urlsafe(48)
            settings.encryption_legacy_password = old_jwt_key
            _persist_env_value("ENCRYPTION_KEY", settings.encryption_key)
            _persist_env_value("ENCRYPTION_LEGACY_PASSWORD", old_jwt_key)
            logger.warning("已生成独立 ENCRYPTION_KEY 并写入 .env；旧弱密钥保留为解密回退（ENCRYPTION_LEGACY_PASSWORD）")
        else:
            # JWT 密钥本身足够强：沿用旧派生方式，保证现有数据可解密
            logger.info("未配置 ENCRYPTION_KEY，暂时沿用 JWT_SECRET_KEY 派生数据加密密钥；"
                        "建议在 .env 中单独设置 ENCRYPTION_KEY 以支持密钥轮换")
    else:
        if len(settings.encryption_key) < _MIN_KEY_LENGTH:
            raise RuntimeError("ENCRYPTION_KEY 强度不足，请设置为至少 32 字节的强随机值")

    # 4) 关键失败场景兜底：密钥是自动生成且 .env 不可写时，加密数据无法跨重启解密
    if not Path(".env").exists():
        logger.warning("项目根目录未找到 .env，自动生成的密钥未持久化；"
                       "容器化部署请务必挂载/固定 JWT_SECRET_KEY 与 ENCRYPTION_KEY")
