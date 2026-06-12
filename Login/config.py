#!/usr/bin/env python3
"""
配置模块

包含小米账号登录相关的常量和配置
"""

from dataclasses import dataclass
from typing import Dict

# Cookie模板
COOKIE_TEMPLATE = (
    "deviceId={device_id}; serviceToken={service_token}; userId={user_id}"
)


@dataclass
class LoginConfig:
    """登录配置类"""
    account: str = ""  # 小米账号
    password: str = ""  # 密码
    token_path: str = "./token.json"  # Token文件路径
    cookie: str = ""  # 可选的cookie字符串
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.account:
            raise ValueError("小米账号不能为空")
        if not self.password:
            raise ValueError("密码不能为空")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "account": self.account,
            "password": self.password,
            "token_path": self.token_path,
            "cookie": self.cookie,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "LoginConfig":
        """从字典创建配置对象"""
        return cls(
            account=data.get("account", ""),
            password=data.get("password", ""),
            token_path=data.get("token_path", "./token.json"),
            cookie=data.get("cookie", ""),
        )