-- 添加mi_username字段到devices表的迁移脚本
-- 执行时间: 2025-08-15

-- 添加mi_username字段
ALTER TABLE devices ADD COLUMN mi_username VARCHAR(100) NOT NULL DEFAULT '' COMMENT '关联的小米账号用户名';

-- 更新现有设备的mi_username字段
-- 从关联的mi_accounts表获取mi_username
UPDATE devices d 
INNER JOIN mi_accounts ma ON d.mi_account_id = ma.id 
SET d.mi_username = ma.mi_username;

-- 添加索引以提高查询性能
CREATE INDEX idx_mi_username ON devices(mi_username);
CREATE INDEX idx_user_mi_username ON devices(user_id, mi_username);

-- 验证数据迁移
SELECT 
    d.id,
    d.device_name,
    d.mi_username,
    ma.mi_username as account_username
FROM devices d
INNER JOIN mi_accounts ma ON d.mi_account_id = ma.id
LIMIT 10;