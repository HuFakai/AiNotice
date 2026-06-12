#!/usr/bin/env python3
"""
小米账号管理模块

提供小米账号登录、认证和服务初始化功能
"""

import json
import logging
import os
from typing import Optional

from aiohttp import ClientSession
from miservice import MiAccount, MiIOService, MiNAService

from utils import parse_cookie_string
from config import COOKIE_TEMPLATE


class MiAccountManager:
    """小米账号管理器"""
    
    def __init__(self, account: str, password: str, token_path: str, cookie: str = ""):
        """
        初始化小米账号管理器
        
        Args:
            account: 小米账号
            password: 密码
            token_path: token文件路径
            cookie: 可选的cookie字符串
        """
        self.account = account
        self.password = password
        self.token_path = token_path
        self.cookie = cookie
        
        self.mina_service: Optional[MiNAService] = None
        self.miio_service: Optional[MiIOService] = None
        self.mi_account: Optional[MiAccount] = None
        
        self.log = logging.getLogger(__name__)
    
    async def login(self, session: ClientSession) -> bool:
        """
        登录小米账号
        
        Args:
            session: aiohttp会话
            
        Returns:
            bool: 登录是否成功
        """
        try:
            # 不传递session，让MiAccount使用自己的SSL配置
            self.mi_account = MiAccount(
                None,  # 传递None让MiAccount自己创建session并应用SSL配置
                self.account,
                self.password,
                str(self.token_path),
            )
            # 强制登录以刷新token
            await self.mi_account.login("micoapi")
            
            # 初始化服务
            self.mina_service = MiNAService(self.mi_account)
            self.miio_service = MiIOService(self.mi_account)
            
            self.log.info("小米账号登录成功")
            return True
            
        except Exception as e:
            self.log.warning(f"小米账号登录失败: {e}")
            return False
    
    def get_cookie_jar(self, device_id: str = ""):
        """
        获取cookie jar
        
        Args:
            device_id: 设备ID，用于从token文件生成cookie
            
        Returns:
            cookie jar对象或None
        """
        # 优先使用配置的cookie
        if self.cookie:
            return parse_cookie_string(self.cookie)
        
        # 从token文件生成cookie
        if not os.path.exists(self.token_path):
            self.log.warning(f"{self.token_path} file not exist")
            return None
        
        try:
            with open(self.token_path, encoding="utf-8") as f:
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
            self.log.error(f"生成cookie失败: {e}")
            return None
    
    def is_logged_in(self) -> bool:
        """
        检查是否已登录
        
        Returns:
            bool: 是否已登录
        """
        return (
            self.mi_account is not None and 
            self.mina_service is not None and 
            self.miio_service is not None
        )
    
    def get_services(self) -> tuple[Optional[MiNAService], Optional[MiIOService]]:
        """
        获取小米服务实例
        
        Returns:
            tuple: (MiNAService, MiIOService)
        """
        return self.mina_service, self.miio_service