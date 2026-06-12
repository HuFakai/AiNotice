-- 为speak接口API调用日志添加新字段的数据库迁移脚本
-- 执行时间: 2025-01-11

-- 添加speak接口相关字段到api_call_logs表
ALTER TABLE api_call_logs 
ADD COLUMN device_id VARCHAR(255),
ADD COLUMN device_name VARCHAR(255),
ADD COLUMN speak_text TEXT,
ADD COLUMN task_end_time TIMESTAMP;

-- 添加索引以提高查询性能
CREATE INDEX idx_api_call_logs_device_id ON api_call_logs(device_id);
CREATE INDEX idx_api_call_logs_speak_endpoint ON api_call_logs(endpoint) WHERE endpoint = '/api/v1/speak';

-- 为speak_status表添加api_log_id字段
ALTER TABLE speak_status 
ADD COLUMN api_log_id INTEGER;

-- 添加外键约束（可选）
-- ALTER TABLE speak_status 
-- ADD CONSTRAINT fk_speak_status_api_log 
-- FOREIGN KEY (api_log_id) REFERENCES api_call_logs(id) ON DELETE SET NULL;

-- 验证表结构
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'api_call_logs' 
AND column_name IN ('device_id', 'device_name', 'speak_text', 'task_end_time');

SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'speak_status' 
AND column_name = 'api_log_id';