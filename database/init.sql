-- 爱通知小爱音箱消息推送统一API平台 - 数据库初始化脚本
-- 数据库: miapi
-- 字符集: utf8mb4

USE miapi;

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 1. 用户表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 2. 小米账户表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小米账户表';

-- 3. 设备表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表';

-- 4. API密钥表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API密钥表';

-- 5. 语音任务表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='语音任务表';

-- 6. 用户活动日志表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户活动日志表';

-- 7. 系统配置表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 插入初始系统配置
INSERT INTO system_settings (setting_key, setting_value, setting_type, description, is_public) VALUES
('platform_name', '爱通知小爱音箱消息推送统一API平台', 'string', '平台名称', TRUE),
('platform_version', '1.0.0', 'string', '平台版本', TRUE),
('registration_enabled', 'true', 'boolean', '是否允许用户注册', TRUE),
('api_rate_limit', '1000', 'int', 'API调用频率限制(次/小时)', FALSE),
('max_devices_per_user', '10', 'int', '每用户最大设备数', FALSE),
('max_api_keys_per_user', '5', 'int', '每用户最大API密钥数', FALSE),
('jwt_secret_key', 'CHANGE_ME_IN_ENV', 'string', 'JWT密钥（部署后请改为强随机值）', FALSE),
('jwt_expire_hours', '24', 'int', 'JWT过期时间(小时)', FALSE),
('email_verification_required', 'false', 'boolean', '是否需要邮箱验证', TRUE)
ON DUPLICATE KEY UPDATE 
setting_value = VALUES(setting_value),
updated_at = CURRENT_TIMESTAMP;

-- 创建复合索引以优化查询性能
CREATE INDEX idx_user_created_at ON users(id, created_at);
CREATE INDEX idx_device_user_status ON devices(user_id, is_online);
CREATE INDEX idx_apikey_user_active ON api_keys(user_id, is_active);
CREATE INDEX idx_task_user_status ON speak_tasks(user_id, status);
CREATE INDEX idx_activity_user_type ON user_activities(user_id, activity_type);

-- 显示创建结果
SELECT 'Database tables created successfully!' AS status;
SELECT TABLE_NAME, TABLE_COMMENT 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'miapi' 
ORDER BY TABLE_NAME;
