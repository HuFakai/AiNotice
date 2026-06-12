#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建完整的数据库表结构
"""

import asyncio
import os
import aiomysql
from loguru import logger


def _db_config() -> dict:
    """数据库连接配置（从环境变量读取，避免在源码中硬编码凭据）"""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'miapi'),
        'password': os.getenv('DB_PASSWORD', ''),
        'db': os.getenv('DB_NAME', 'miapi'),
        'charset': 'utf8mb4',
    }


async def create_all_tables():
    """创建所有数据库表"""
    try:
        config = _db_config()

        print("🏗️ 开始创建完整的数据库表结构...")
        
        connection = await aiomysql.connect(**config)
        
        async with connection.cursor() as cursor:
            
            # 1. 创建用户表
            print("1. 创建用户表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
                    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
                    email VARCHAR(100) UNIQUE NOT NULL COMMENT '邮箱地址',
                    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
                    display_name VARCHAR(100) COMMENT '显示名称',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                    is_verified BOOLEAN DEFAULT FALSE COMMENT '邮箱是否验证',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
                    
                    INDEX idx_username (username),
                    INDEX idx_email (email),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表'
            """)
            
            # 2. 创建小米账户表
            print("2. 创建小米账户表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS mi_accounts (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '小米账户ID',
                    user_id INT NOT NULL COMMENT '关联用户ID',
                    mi_username VARCHAR(100) NOT NULL COMMENT '小米用户名',
                    mi_password_encrypted TEXT NOT NULL COMMENT '加密的小米密码',
                    mi_device_id VARCHAR(100) COMMENT '小米设备ID',
                    mi_user_id VARCHAR(100) COMMENT '小米用户ID',
                    mi_pass_token TEXT COMMENT '小米PassToken',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                    last_sync_at TIMESTAMP NULL COMMENT '最后同步时间',
                    sync_status ENUM('pending', 'success', 'failed') DEFAULT 'pending' COMMENT '同步状态',
                    error_message TEXT COMMENT '错误信息',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_mi_username (mi_username),
                    INDEX idx_sync_status (sync_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小米账户表'
            """)
            
            # 3. 创建设备表
            print("3. 创建设备表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '设备ID',
                    user_id INT NOT NULL COMMENT '关联用户ID',
                    mi_account_id INT NOT NULL COMMENT '关联小米账户ID',
                    device_id VARCHAR(100) NOT NULL COMMENT '设备唯一标识',
                    device_name VARCHAR(100) NOT NULL COMMENT '设备名称',
                    device_model VARCHAR(50) COMMENT '设备型号',
                    device_type VARCHAR(50) DEFAULT 'xiaomi_speaker' COMMENT '设备类型',
                    location VARCHAR(100) COMMENT '设备位置',
                    is_online BOOLEAN DEFAULT FALSE COMMENT '是否在线',
                    is_favorite BOOLEAN DEFAULT FALSE COMMENT '是否收藏',
                    volume INT DEFAULT 50 COMMENT '音量级别',
                    last_seen_at TIMESTAMP NULL COMMENT '最后在线时间',
                    device_info JSON COMMENT '设备详细信息',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (mi_account_id) REFERENCES mi_accounts(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_user_device (user_id, device_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_device_id (device_id),
                    INDEX idx_is_online (is_online)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表'
            """)
            
            # 4. 创建API密钥表
            print("4. 创建API密钥表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'API密钥ID',
                    user_id INT NOT NULL COMMENT '关联用户ID',
                    key_name VARCHAR(100) NOT NULL COMMENT '密钥名称',
                    api_key VARCHAR(255) UNIQUE NOT NULL COMMENT 'API密钥',
                    api_secret VARCHAR(255) NOT NULL COMMENT 'API密钥签名',
                    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
                    permissions JSON COMMENT '权限配置',
                    usage_count INT DEFAULT 0 COMMENT '使用次数',
                    usage_limit INT DEFAULT NULL COMMENT '使用限制',
                    last_used_at TIMESTAMP NULL COMMENT '最后使用时间',
                    expires_at TIMESTAMP NULL COMMENT '过期时间',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_api_key (api_key),
                    INDEX idx_is_active (is_active),
                    INDEX idx_expires_at (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API密钥表'
            """)
            
            # 5. 创建语音任务表
            print("5. 创建语音任务表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS speak_tasks (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '任务ID',
                    user_id INT NOT NULL COMMENT '关联用户ID',
                    device_id INT NOT NULL COMMENT '关联设备ID',
                    task_id VARCHAR(100) UNIQUE NOT NULL COMMENT '任务唯一标识',
                    text_content TEXT NOT NULL COMMENT '播放文本内容',
                    status ENUM('pending', 'playing', 'completed', 'failed') DEFAULT 'pending' COMMENT '任务状态',
                    estimated_duration FLOAT COMMENT '预计播放时长(秒)',
                    actual_duration FLOAT COMMENT '实际播放时长(秒)',
                    error_message TEXT COMMENT '错误信息',
                    api_key_id INT COMMENT '调用API密钥ID',
                    client_ip VARCHAR(45) COMMENT '客户端IP',
                    user_agent VARCHAR(500) COMMENT '用户代理',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    started_at TIMESTAMP NULL COMMENT '开始时间',
                    completed_at TIMESTAMP NULL COMMENT '完成时间',
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE,
                    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_device_id (device_id),
                    INDEX idx_task_id (task_id),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='语音任务表'
            """)
            
            # 6. 创建用户活动日志表
            print("6. 创建用户活动日志表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_activities (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '活动ID',
                    user_id INT NOT NULL COMMENT '关联用户ID',
                    activity_type VARCHAR(50) NOT NULL COMMENT '活动类型',
                    activity_description TEXT NOT NULL COMMENT '活动描述',
                    resource_type VARCHAR(50) COMMENT '资源类型',
                    resource_id INT COMMENT '资源ID',
                    client_ip VARCHAR(45) COMMENT '客户端IP',
                    user_agent VARCHAR(500) COMMENT '用户代理',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_activity_type (activity_type),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户活动日志表'
            """)
            
            # 7. 创建系统配置表
            print("7. 创建系统配置表...")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '配置ID',
                    setting_key VARCHAR(100) UNIQUE NOT NULL COMMENT '配置键',
                    setting_value TEXT COMMENT '配置值',
                    setting_type ENUM('string', 'int', 'float', 'boolean', 'json') DEFAULT 'string' COMMENT '配置类型',
                    description TEXT COMMENT '配置描述',
                    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开可见',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    
                    INDEX idx_setting_key (setting_key),
                    INDEX idx_is_public (is_public)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表'
            """)
            
            # 8. 插入初始系统配置
            print("8. 插入初始系统配置...")
            initial_settings = [
                ('platform_name', '爱通知小爱音箱消息推送统一API平台', 'string', '平台名称', True),
                ('platform_version', '1.0.0', 'string', '平台版本', True),
                ('registration_enabled', 'true', 'boolean', '是否允许用户注册', True),
                ('api_rate_limit', '1000', 'int', 'API调用频率限制(次/小时)', False),
                ('max_devices_per_user', '10', 'int', '每用户最大设备数', False),
                ('max_api_keys_per_user', '5', 'int', '每用户最大API密钥数', False),
                ('jwt_secret_key', 'CHANGE_ME_IN_ENV', 'string', 'JWT密钥（部署后请改为强随机值）', False),
                ('jwt_expire_hours', '24', 'int', 'JWT过期时间(小时)', False),
                ('email_verification_required', 'false', 'boolean', '是否需要邮箱验证', True)
            ]
            
            for setting in initial_settings:
                insert_sql = """
                INSERT INTO system_settings 
                (setting_key, setting_value, setting_type, description, is_public) 
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                setting_value = VALUES(setting_value),
                updated_at = CURRENT_TIMESTAMP
                """
                await cursor.execute(insert_sql, setting)
            
            # 9. 创建复合索引优化查询性能
            print("9. 创建性能优化索引...")
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_user_created_at ON users(id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_device_user_status ON devices(user_id, is_online)",
                "CREATE INDEX IF NOT EXISTS idx_apikey_user_active ON api_keys(user_id, is_active)",
                "CREATE INDEX IF NOT EXISTS idx_task_user_status ON speak_tasks(user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_activity_user_type ON user_activities(user_id, activity_type)"
            ]
            
            for index_sql in indexes:
                try:
                    await cursor.execute(index_sql)
                except Exception as e:
                    print(f"创建索引时警告: {e}")
            
            await connection.commit()
            print("✅ 所有数据库表创建完成!")
        
        await connection.ensure_closed()
        return True
        
    except Exception as e:
        print(f"❌ 创建数据库表失败: {e}")
        return False


async def verify_tables():
    """验证表创建结果"""
    try:
        config = _db_config()

        connection = await aiomysql.connect(**config)

        async with connection.cursor() as cursor:
            # 查看所有表
            await cursor.execute("SHOW TABLES")
            tables = await cursor.fetchall()
            
            print(f"\n📋 数据库表列表 (共{len(tables)}个):")
            for table in tables:
                table_name = table[0]
                
                # 获取表注释
                await cursor.execute(f"""
                    SELECT TABLE_COMMENT 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = 'miapi' AND TABLE_NAME = '{table_name}'
                """)
                comment_result = await cursor.fetchone()
                comment = comment_result[0] if comment_result else ""
                
                # 获取表行数
                await cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_result = await cursor.fetchone()
                count = count_result[0] if count_result else 0
                
                print(f"   📝 {table_name:<20} - {comment:<20} ({count} rows)")
        
        await connection.ensure_closed()
        return True
        
    except Exception as e:
        print(f"❌ 验证表失败: {e}")
        return False


async def main():
    """主函数"""
    print("🚀 爱通知小爱音箱消息推送统一API平台 - 完整数据库表创建")
    print("=" * 60)
    
    # 1. 创建所有表
    if not await create_all_tables():
        return
    
    # 2. 验证结果
    print("\n🔍 验证创建结果...")
    await verify_tables()
    
    print("\n🎉 数据库初始化完成!")
    print("💡 现在可以开始开发用户认证和API系统了!")


if __name__ == "__main__":
    asyncio.run(main())
