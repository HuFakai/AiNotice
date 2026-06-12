#!/usr/bin/env python3
"""
Login模块

小米账号登录相关功能的独立模块
专注于账号登录、Token管理和Cookie处理
"""

from .config import LoginConfig, COOKIE_TEMPLATE
from .mi_account import MiAccountManager
from .utils import (
    parse_cookie_string,
    get_cookie_from_token,
    extract_token_info,
)

__version__ = "1.0.0"
__author__ = "xiaomusic"
__description__ = "小米账号登录模块 - 专注于登录、Token和Cookie处理"

__all__ = [
    # 配置类
    "LoginConfig",
    "COOKIE_TEMPLATE",
    
    # 核心管理器
    "MiAccountManager",
    
    # 工具函数
    "parse_cookie_string",
    "get_cookie_from_token",
    "extract_token_info",
]