# -*- coding: utf-8 -*-
"""
加密工具
用于加密和解密敏感信息，如小米账户密码
"""

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from app.config import settings


class EncryptionManager:
    """加密管理器"""

    def __init__(self):
        self._fernet = self._get_fernet_instance()

    def _get_fernet_instance(self) -> Fernet:
        """获取Fernet加密实例"""
        # 使用JWT密钥作为加密密钥的基础
        password = settings.jwt_secret_key.encode()

        # 生成固定的盐值（实际生产环境应该使用随机盐值并存储）
        salt = b"xiaomi_api_platform_salt_2025"

        # 使用PBKDF2生成密钥
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
        """解密文本"""
        try:
            if not encrypted_text:
                return ""

            encrypted_data = base64.urlsafe_b64decode(encrypted_text.encode("utf-8"))
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return decrypted_data.decode("utf-8")
        except Exception as e:
            raise ValueError(f"解密失败: {e}")


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
