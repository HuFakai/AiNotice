# -*- coding: utf-8 -*-
"""
加密工具
用于加密和解密敏感信息，如小米账户密码
"""

import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from loguru import logger
from app.config import settings


class EncryptionManager:
    """加密管理器

    密钥来源（按优先级）：
    1. settings.encryption_key —— 独立的数据加密密钥（推荐，支持与 JWT 密钥解耦/轮换）
    2. settings.jwt_secret_key —— 历史兼容路径（未配置 ENCRYPTION_KEY 时沿用旧行为，保证旧数据可解密）

    另支持 settings.encryption_legacy_password 作为解密回退
    （自动修复弱 JWT 密钥时，旧值会被保留在这里，历史密文仍可读）。
    新写入一律使用主密钥。
    """

    def __init__(self):
        self._fernet = self._build_fernet(self._primary_password())
        self._legacy_fernet = None
        legacy_password = getattr(settings, "encryption_legacy_password", None)
        if legacy_password:
            self._legacy_fernet = self._build_fernet(legacy_password.encode())

    @staticmethod
    def _primary_password() -> bytes:
        encryption_key = getattr(settings, "encryption_key", None)
        if encryption_key:
            return encryption_key.encode()
        return settings.jwt_secret_key.encode()

    @staticmethod
    def _build_fernet(password: bytes) -> Fernet:
        # 固定盐值：密文自包含校验，盐无需保密；改盐会使全部历史密文不可读
        salt = b"xiaomi_api_platform_salt_2025"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """加密文本"""
        try:
            if not plaintext:
                return ""

            encrypted_data = self._fernet.encrypt(plaintext.encode("utf-8"))
            return base64.urlsafe_b64encode(encrypted_data).decode("utf-8")
        except Exception as e:
            raise ValueError(f"加密失败: {e}")

    def decrypt(self, encrypted_text: str) -> str:
        """解密文本（先主密钥，失败则尝试历史回退密钥）"""
        try:
            if not encrypted_text:
                return ""

            encrypted_data = base64.urlsafe_b64decode(encrypted_text.encode("utf-8"))
        except Exception as e:
            raise ValueError(f"解密失败: {e}")

        try:
            return self._fernet.decrypt(encrypted_data).decode("utf-8")
        except InvalidToken:
            if self._legacy_fernet is not None:
                try:
                    plaintext = self._legacy_fernet.decrypt(encrypted_data).decode("utf-8")
                    logger.info("使用历史密钥成功解密数据（建议重新保存以迁移到新密钥）")
                    return plaintext
                except InvalidToken:
                    pass
            raise ValueError("解密失败: 密钥不匹配（可能更换过 ENCRYPTION_KEY/JWT_SECRET_KEY）")


# 全局加密管理器实例
_encryption_manager = EncryptionManager()


def encrypt_password(password: str) -> str:
    """
    加密密码

    Args:
        password: 明文密码

    Returns:
        加密后的密码
    """
    return _encryption_manager.encrypt(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    解密密码

    Args:
        encrypted_password: 加密的密码

    Returns:
        明文密码
    """
    return _encryption_manager.decrypt(encrypted_password)


def test_encryption():
    """测试加密功能"""
    test_password = "test_password_123"

    # 测试加密
    encrypted = encrypt_password(test_password)
    print(f"原文: {test_password}")
    print(f"密文: {encrypted}")

    # 测试解密
    decrypted = decrypt_password(encrypted)
    print(f"解密: {decrypted}")

    # 验证一致性
    assert test_password == decrypted, "加密解密不一致"
    print("✅ 加密测试通过")


if __name__ == "__main__":
    test_encryption()
