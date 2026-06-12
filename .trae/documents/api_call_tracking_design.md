# API接口调用记录与统计功能设计方案

## 1. 功能概述

设计一个完整的API调用记录与统计系统，用于监控和分析平台API的使用情况，为用户提供详细的调用统计和分析报告。

## 2. 数据模型设计

### 2.1 API调用记录表 (api_call_logs)

```sql
CREATE TABLE api_call_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    api_key_id INTEGER REFERENCES api_keys(id),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_ip INET,
    user_agent TEXT,
    request_size INTEGER DEFAULT 0,
    response_size INTEGER DEFAULT 0,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER NOT NULL,
    error_message TEXT,
    request_params JSONB,
    response_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引优化
    INDEX idx_api_call_logs_user_id (user_id),
    INDEX idx_api_call_logs_created_at (created_at),
    INDEX idx_api_call_logs_endpoint (endpoint),
    INDEX idx_api_call_logs_status_code (status_code),
    INDEX idx_api_call_logs_user_created (user_id, created_at)
);
```

### 2.2 API统计汇总表 (api_usage_stats)

```sql
CREATE TABLE api_usage_stats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    date DATE NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    total_calls INTEGER DEFAULT 0,
    success_calls INTEGER DEFAULT 0,
    error_calls INTEGER DEFAULT 0,
    avg_response_time_ms DECIMAL(10,2) DEFAULT 0,
    total_request_size BIGINT DEFAULT 0,
    total_response_size BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, date, endpoint),
    INDEX idx_api_usage_stats_user_date (user_id, date),
    INDEX idx_api_usage_stats_endpoint (endpoint)
);
```

### 2.3 API配额管理表 (api_quotas)

```sql
CREATE TABLE api_quotas (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    endpoint VARCHAR(255) NOT NULL,
    quota_type VARCHAR(20) NOT NULL, -- 'daily', 'monthly', 'total'
    quota_limit INTEGER NOT NULL,
    quota_used INTEGER DEFAULT 0,
    reset_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, endpoint, quota_type),
    INDEX idx_api_quotas_user_endpoint (user_id, endpoint)
);
```

## 3. 统计维度设计

### 3.1 时间维度
- **实时统计**: 最近1小时、最近24小时
- **日统计**: 按天统计，支持查看最近30天
- **周统计**: 按周统计，支持查看最近12周
- **月统计**: 按月统计，支持查看最近12个月

### 3.2 接口维度
- **按接口分类**: GET /devices, POST /speak, PUT /mi-accounts等
- **按功能模块**: 设备管理、语音播放、账户管理等
- **按成功率**: 成功调用、失败调用、错误类型分布

### 3.3 性能维度
- **响应时间**: 平均响应时间、P95、P99响应时间
- **吞吐量**: QPS (每秒请求数)
- **数据传输**: 请求大小、响应大小统计

### 3.4 用户维度
- **API Key使用情况**: 每个API Key的调用统计
- **配额使用情况**: 剩余配额、使用率
- **地理位置**: 基于IP的地理位置统计

## 4. 后端API接口设计

### 4.1 调用记录接口

```python
# 获取调用记录列表
GET /api/v1/analytics/call-logs
Query Parameters:
- page: int = 1
- limit: int = 20
- start_date: str (YYYY-MM-DD)
- end_date: str (YYYY-MM-DD)
- endpoint: str (可选)
- status_code: int (可选)
- api_key_id: int (可选)

# 获取调用统计概览
GET /api/v1/analytics/overview
Query Parameters:
- period: str = '24h' | '7d' | '30d' | '90d'

# 获取接口使用统计
GET /api/v1/analytics/endpoints
Query Parameters:
- period: str = '24h' | '7d' | '30d'
- group_by: str = 'endpoint' | 'status' | 'hour' | 'day'

# 获取性能统计
GET /api/v1/analytics/performance
Query Parameters:
- period: str = '24h' | '7d' | '30d'
- endpoint: str (可选)

# 获取配额使用情况
GET /api/v1/analytics/quotas
```

### 4.2 响应数据格式

```json
{
  "overview": {
    "total_calls": 15420,
    "success_rate": 98.5,
    "avg_response_time": 245,
    "top_endpoints": [
      {
        "endpoint": "/speak",
        "calls": 8500,
        "success_rate": 99.2
      }
    ],
    "error_distribution": {
      "400": 120,
      "401": 45,
      "500": 23
    }
  },
  "time_series": [
    {
      "timestamp": "2024-01-15T10:00:00Z",
      "calls": 156,
      "avg_response_time": 234
    }
  ]
}
```

## 5. 前端界面设计

### 5.1 统计概览页面 (analytics.html)

**页面布局**:
- 顶部KPI卡片: 总调用次数、成功率、平均响应时间、今日使用量
- 时间序列图表: 调用量趋势、响应时间趋势
- 接口使用排行: 最常用接口、错误率最高接口
- 实时监控: 最近调用记录、当前QPS

**关键组件**:
```html
<!-- KPI指标卡片 -->
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-value" id="totalCalls">--</div>
    <div class="stat-label">总调用次数</div>
    <div class="stat-change positive">+12.5%</div>
  </div>
  <!-- 更多KPI卡片 -->
</div>

<!-- 图表区域 -->
<div class="charts-grid">
  <div class="chart-container">
    <canvas id="callsChart"></canvas>
  </div>
  <div class="chart-container">
    <canvas id="responseTimeChart"></canvas>
  </div>
</div>
```

### 5.2 详细记录页面

**功能特性**:
- 调用记录表格: 时间、接口、状态码、响应时间、IP地址
- 高级筛选: 时间范围、接口类型、状态码、API Key
- 导出功能: CSV、Excel格式导出
- 实时刷新: WebSocket实时更新

### 5.3 性能分析页面

**分析维度**:
- 响应时间分布直方图
- 接口性能对比
- 错误率趋势分析
- 地理位置分布地图

## 6. 技术实现方案

### 6.1 数据收集

**中间件实现**:
```python
# FastAPI中间件
@app.middleware("http")
async def api_logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    # 记录请求信息
    request_data = {
        "endpoint": str(request.url.path),
        "method": request.method,
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "request_size": len(await request.body()) if request.method in ["POST", "PUT"] else 0
    }
    
    response = await call_next(request)
    
    # 计算响应时间
    response_time = int((time.time() - start_time) * 1000)
    
    # 异步记录到数据库
    await log_api_call({
        **request_data,
        "status_code": response.status_code,
        "response_time_ms": response_time,
        "response_size": len(response.body) if hasattr(response, 'body') else 0
    })
    
    return response
```

### 6.2 数据聚合

**定时任务**:
```python
# 每小时聚合统计数据
@scheduler.scheduled_job('cron', minute=0)
async def aggregate_hourly_stats():
    # 聚合最近1小时的数据到统计表
    await aggregate_api_usage_stats(period='1h')

# 每日聚合统计数据
@scheduler.scheduled_job('cron', hour=1, minute=0)
async def aggregate_daily_stats():
    # 聚合昨天的数据
    await aggregate_api_usage_stats(period='1d')
```

### 6.3 缓存策略

**Redis缓存**:
- 实时统计数据缓存 (TTL: 1分钟)
- 热点查询结果缓存 (TTL: 5分钟)
- 用户配额信息缓存 (TTL: 1小时)

### 6.4 性能优化

**数据库优化**:
- 分区表: 按月分区存储历史数据
- 索引优化: 复合索引覆盖常用查询
- 数据清理: 定期清理超过1年的详细记录

**查询优化**:
- 预聚合: 提前计算常用统计指标
- 分页查询: 大数据量分页加载
- 异步处理: 复杂统计异步计算

## 7. 安全与隐私

### 7.1 数据脱敏
- IP地址脱敏: 只保留前3段
- 敏感参数过滤: 密码、token等敏感信息不记录
- 用户隔离: 用户只能查看自己的统计数据

### 7.2 访问控制
- 权限验证: 基于API Key的访问控制
- 数据权限: 用户级别的数据隔离
- 审计日志: 管理员操作审计

## 8. 部署与监控

### 8.1 部署方案
- 微服务架构: 统计服务独立部署
- 容器化: Docker容器部署
- 负载均衡: 多实例负载均衡

### 8.2 监控告警
- 系统监控: CPU、内存、磁盘使用率
- 业务监控: API调用量、错误率、响应时间
- 告警机制: 异常情况及时告警

## 9. 开发计划

### Phase 1: 基础功能 (2周)
- 数据模型设计与实现
- 基础API接口开发
- 简单统计页面

### Phase 2: 高级功能 (2周)
- 详细图表展示
- 高级筛选功能
- 导出功能

### Phase 3: 优化完善 (1周)
- 性能优化
- 用户体验优化
- 测试与部署

## 10. 预期效果

- **用户价值**: 帮助用户了解API使用情况，优化调用策略
- **运营价值**: 提供数据支持，优化产品功能和定价策略
- **技术价值**: 监控系统健康状况，及时发现和解决问题

---

*此设计方案为初版，具体实现时可根据实际需求进行调整和优化。*