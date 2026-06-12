-- API调用记录与统计功能数据库迁移脚本 (MySQL版本)
-- 创建时间: 2025-01-14
-- 描述: 创建API调用日志、使用统计和配额管理相关表

-- 1. 创建API调用日志表
CREATE TABLE IF NOT EXISTS api_call_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    user_id INT NULL COMMENT '用户ID，关联users表',
    api_key_id INT NULL COMMENT 'API密钥ID，关联api_keys表',
    endpoint VARCHAR(255) NOT NULL COMMENT 'API端点路径',
    method VARCHAR(10) NOT NULL COMMENT 'HTTP方法',
    status_code INT NOT NULL COMMENT 'HTTP状态码',
    response_time DECIMAL(10,3) NOT NULL COMMENT '响应时间(毫秒)',
    request_size INT DEFAULT 0 COMMENT '请求大小(字节)',
    response_size INT DEFAULT 0 COMMENT '响应大小(字节)',
    ip_address VARCHAR(45) NULL COMMENT '客户端IP地址',
    user_agent TEXT NULL COMMENT '用户代理字符串',
    request_data JSON NULL COMMENT '请求数据(JSON格式)',
    response_data JSON NULL COMMENT '响应数据(JSON格式)',
    error_message TEXT NULL COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    -- 索引
    INDEX idx_user_id (user_id),
    INDEX idx_api_key_id (api_key_id),
    INDEX idx_endpoint (endpoint),
    INDEX idx_status_code (status_code),
    INDEX idx_created_at (created_at),
    INDEX idx_user_endpoint (user_id, endpoint),
    INDEX idx_user_created (user_id, created_at),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API调用日志表';

-- 2. 创建API使用统计表
CREATE TABLE IF NOT EXISTS api_usage_stats (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    user_id INT NULL COMMENT '用户ID，关联users表',
    endpoint VARCHAR(255) NOT NULL COMMENT 'API端点路径',
    date DATE NOT NULL COMMENT '统计日期',
    total_calls INT DEFAULT 0 COMMENT '总调用次数',
    success_calls INT DEFAULT 0 COMMENT '成功调用次数',
    error_calls INT DEFAULT 0 COMMENT '错误调用次数',
    avg_response_time DECIMAL(10,3) DEFAULT 0 COMMENT '平均响应时间(毫秒)',
    total_request_size BIGINT DEFAULT 0 COMMENT '总请求大小(字节)',
    total_response_size BIGINT DEFAULT 0 COMMENT '总响应大小(字节)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    UNIQUE KEY uk_user_endpoint_date (user_id, endpoint, date),
    INDEX idx_user_id (user_id),
    INDEX idx_endpoint (endpoint),
    INDEX idx_date (date),
    INDEX idx_user_date (user_id, date),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API使用统计表';

-- 3. 创建API配额管理表
CREATE TABLE IF NOT EXISTS api_quotas (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    user_id INT NULL COMMENT '用户ID，关联users表',
    quota_type ENUM('daily', 'monthly', 'total') NOT NULL DEFAULT 'daily' COMMENT '配额类型',
    endpoint VARCHAR(255) NULL COMMENT 'API端点路径，NULL表示全局配额',
    quota_limit INT NOT NULL DEFAULT 1000 COMMENT '配额限制',
    quota_used INT DEFAULT 0 COMMENT '已使用配额',
    reset_time TIMESTAMP NULL COMMENT '配额重置时间',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 索引
    UNIQUE KEY uk_user_type_endpoint (user_id, quota_type, endpoint),
    INDEX idx_user_id (user_id),
    INDEX idx_quota_type (quota_type),
    INDEX idx_endpoint (endpoint),
    INDEX idx_reset_time (reset_time),
    INDEX idx_is_active (is_active),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='API配额管理表';

-- 4. 插入默认配额设置
INSERT IGNORE INTO api_quotas (user_id, quota_type, endpoint, quota_limit, quota_used, is_active) VALUES
(NULL, 'daily', NULL, 10000, 0, TRUE),
(NULL, 'monthly', NULL, 300000, 0, TRUE),
(NULL, 'daily', '/api/v1/speak', 1000, 0, TRUE),
(NULL, 'daily', '/api/v1/devices', 500, 0, TRUE);

-- 5. 创建视图：每日API调用概览
CREATE OR REPLACE VIEW daily_api_overview AS
SELECT 
    DATE(created_at) as call_date,
    COUNT(*) as total_calls,
    COUNT(CASE WHEN status_code < 400 THEN 1 END) as success_calls,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_calls,
    ROUND(AVG(response_time), 2) as avg_response_time,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT endpoint) as unique_endpoints
FROM api_call_logs 
WHERE created_at >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY call_date DESC;

-- 6. 创建视图：用户API使用概览
CREATE OR REPLACE VIEW user_api_overview AS
SELECT 
    u.id as user_id,
    u.username,
    COUNT(l.id) as total_calls,
    COUNT(CASE WHEN l.status_code < 400 THEN 1 END) as success_calls,
    COUNT(CASE WHEN l.status_code >= 400 THEN 1 END) as error_calls,
    ROUND(AVG(l.response_time), 2) as avg_response_time,
    COUNT(DISTINCT l.endpoint) as unique_endpoints,
    MAX(l.created_at) as last_call_time
FROM users u
LEFT JOIN api_call_logs l ON u.id = l.user_id 
    AND l.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY u.id, u.username
ORDER BY total_calls DESC;

-- 7. 创建存储过程：清理旧日志
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS CleanOldApiLogs(IN days_to_keep INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    DELETE FROM api_call_logs 
    WHERE created_at < DATE_SUB(NOW(), INTERVAL days_to_keep DAY);
    
    DELETE FROM api_usage_stats 
    WHERE date < DATE_SUB(CURRENT_DATE, INTERVAL days_to_keep DAY);
    
    COMMIT;
END //
DELIMITER ;

-- 8. 创建存储过程：重置每日配额
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS ResetDailyQuotas()
BEGIN
    UPDATE api_quotas 
    SET quota_used = 0, 
        reset_time = NOW(),
        updated_at = NOW()
    WHERE quota_type = 'daily' 
    AND (reset_time IS NULL OR DATE(reset_time) < CURRENT_DATE);
END //
DELIMITER ;

-- 9. 创建存储过程：聚合每日统计
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS AggregateApiStats(IN target_date DATE)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- 删除当日已有统计
    DELETE FROM api_usage_stats WHERE date = target_date;
    
    -- 插入新的统计数据
    INSERT INTO api_usage_stats (
        user_id, endpoint, date, total_calls, success_calls, error_calls,
        avg_response_time, total_request_size, total_response_size
    )
    SELECT 
        user_id,
        endpoint,
        target_date,
        COUNT(*) as total_calls,
        COUNT(CASE WHEN status_code < 400 THEN 1 END) as success_calls,
        COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_calls,
        ROUND(AVG(response_time), 3) as avg_response_time,
        COALESCE(SUM(request_size), 0) as total_request_size,
        COALESCE(SUM(response_size), 0) as total_response_size
    FROM api_call_logs
    WHERE DATE(created_at) = target_date
    GROUP BY user_id, endpoint;
    
    COMMIT;
END //
DELIMITER ;

-- 10. 创建事件调度器（如果支持）
-- 注意：需要确保MySQL的事件调度器已启用 (SET GLOBAL event_scheduler = ON;)

-- 每日凌晨1点重置每日配额
CREATE EVENT IF NOT EXISTS reset_daily_quotas
ON SCHEDULE EVERY 1 DAY
STARTS TIMESTAMP(CURRENT_DATE + INTERVAL 1 DAY, '01:00:00')
DO
  CALL ResetDailyQuotas();

-- 每日凌晨2点聚合前一天的统计数据
CREATE EVENT IF NOT EXISTS aggregate_daily_stats
ON SCHEDULE EVERY 1 DAY
STARTS TIMESTAMP(CURRENT_DATE + INTERVAL 1 DAY, '02:00:00')
DO
  CALL AggregateApiStats(DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY));

-- 每周日凌晨3点清理90天前的日志
CREATE EVENT IF NOT EXISTS clean_old_logs
ON SCHEDULE EVERY 1 WEEK
STARTS TIMESTAMP(CURRENT_DATE + INTERVAL (7 - WEEKDAY(CURRENT_DATE)) DAY, '03:00:00')
DO
  CALL CleanOldApiLogs(90);

-- 迁移完成提示
SELECT '✅ API调用记录与统计功能数据库迁移完成！' as message;