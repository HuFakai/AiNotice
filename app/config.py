# -*- coding: utf-8 -*-
"""
配置管理模块
管理应用程序的各种配置参数
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用程序配置类"""

    # 小米账户配置 (单用户模式配置，多用户模式下可选)
    mi_user: Optional[str] = Field(default=None, description="小米账户用户名")
    mi_pass: Optional[str] = Field(default=None, description="小米账户密码")

    # 小米设备认证信息 (可选)
    mi_device_id: Optional[str] = Field(default=None, description="小米设备ID")
    mi_user_id: Optional[str] = Field(default=None, description="小米用户ID")
    mi_pass_token: Optional[str] = Field(default=None, description="小米PassToken")

    # API服务配置
    api_host: str = Field(default="0.0.0.0", description="API服务器地址")
    api_port: int = Field(default=8000, description="API服务器端口")
    api_debug: bool = Field(default=False, description="是否开启调试模式")

    # 数据库配置（敏感值必须通过 .env 注入，源码不保留真实凭据）
    db_host: str = Field(default="localhost", description="数据库主机地址")
    db_port: int = Field(default=3306, description="数据库端口")
    db_user: str = Field(default="miapi", description="数据库用户名")
    db_password: str = Field(default="", description="数据库密码（请在 .env 中配置）")
    db_name: str = Field(default="miapi", description="数据库名称")

    # 数据库连接池配置
    db_echo: bool = Field(default=False, description="是否输出SQL语句")
    db_pool_size: int = Field(default=5, description="连接池大小")
    db_max_overflow: int = Field(default=10, description="连接池溢出大小")
    db_pool_timeout: int = Field(default=30, description="连接超时时间")
    db_pool_recycle: int = Field(default=3600, description="连接回收时间")

    # JWT配置（生产环境务必在 .env 中设置强随机 jwt_secret_key）
    jwt_secret_key: str = Field(default="CHANGE_ME_IN_ENV", description="JWT密钥（请在 .env 中配置强随机值）")
    jwt_algorithm: str = Field(default="HS256", description="JWT算法")
    jwt_expire_hours: int = Field(default=24, description="JWT过期时间(小时)")

    # 安全配置
    password_min_length: int = Field(default=8, description="密码最小长度")
    api_key_length: int = Field(default=64, description="API密钥长度")

    # CORS 配置（逗号分隔的允许来源；"*" 表示全部。使用 Bearer 令牌认证，默认无需携带 Cookie 凭据）
    cors_origins: str = Field(default="*", description="允许的跨域来源，逗号分隔")

    # 平台配置
    platform_name: str = Field(default="爱通知小爱音箱消息推送统一API平台", description="平台名称")
    registration_enabled: bool = Field(default=True, description="是否允许用户注册")
    max_devices_per_user: int = Field(default=10, description="每用户最大设备数")
    max_api_keys_per_user: int = Field(default=10, description="每用户最大API密钥数")
    
    # 数据库清理配置
    cleanup_enabled: bool = Field(default=True, description="是否启用数据库定时清理")
    cleanup_hour: int = Field(default=2, description="清理任务执行小时(0-23)")
    cleanup_minute: int = Field(default=0, description="清理任务执行分钟(0-59)")
    timezone: str = Field(default="Asia/Shanghai", description="时区设置")
    
    # 数据保留天数配置
    api_logs_retention_days: int = Field(default=90, description="API调用记录保留天数")
    speak_tasks_retention_days: int = Field(default=7, description="播放任务记录保留天数")
    user_activities_retention_days: int = Field(default=30, description="用户活动记录保留天数")
    log_files_retention_days: int = Field(default=7, description="日志文件保留天数")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings
