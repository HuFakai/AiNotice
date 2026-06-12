#!/usr/bin/env python3
"""
工具函数模块

包含小米账号登录相关的Cookie和Token处理工具函数
"""

import json
import logging
import os
from http.cookies import SimpleCookie
from typing import Optional

from requests.utils import cookiejar_from_dict

from config import COOKIE_TEMPLATE

log = logging.getLogger(__name__)


def parse_cookie_string(cookie_string: str):
    """
    解析cookie字符串为cookiejar对象
    
    Args:
        cookie_string: cookie字符串，格式如 "deviceId=xxx; serviceToken=xxx; userId=xxx"
        
    Returns:
        cookiejar对象，包含解析后的cookie信息
    """
    cookie = SimpleCookie()
    cookie.load(cookie_string)
    cookies_dict = {k: m.value for k, m in cookie.items()}
    return cookiejar_from_dict(cookies_dict, cookiejar=None, overwrite=True)


def get_cookie_from_token(token_path: str, device_id: str = "") -> Optional[object]:
    """
    从token文件生成cookie
    
    Args:
        token_path: token文件路径
        device_id: 设备ID（可选）
        
    Returns:
        cookiejar对象或None（如果生成失败）
    """
    if not os.path.exists(token_path):
        log.warning(f"{token_path} file not exist")
        return None
    
    try:
        with open(token_path, encoding="utf-8") as f:
            user_data = json.loads(f.read())
        
        user_id = user_data.get("userId")
        service_token = user_data.get("micoapi")[1]
        
        cookie_string = COOKIE_TEMPLATE.format(
            device_id=device_id,
            service_token=service_token,
            user_id=user_id
        )
        return parse_cookie_string(cookie_string)
        
    except Exception as e:
        log.error(f"从token文件生成cookie失败: {e}")
        return None


def extract_token_info(token_path: str) -> dict:
    """
    从token文件中提取关键信息
    
    Args:
        token_path: token文件路径
        
    Returns:
        dict: 包含deviceId、serviceToken、userId的字典
    """
    if not os.path.exists(token_path):
        log.warning(f"{token_path} file not exist")
        return {}
    
    try:
        with open(token_path, encoding="utf-8") as f:
            user_data = json.loads(f.read())
        
        return {
            "deviceId": user_data.get("deviceId", ""),
            "userId": user_data.get("userId", ""),
            "serviceToken": user_data.get("micoapi", ["", ""])[1] if user_data.get("micoapi") else "",
            "passToken": user_data.get("passToken", "")
        }
        
    except Exception as e:
        log.error(f"提取token信息失败: {e}")
        return {}