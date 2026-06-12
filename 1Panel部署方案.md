# 小米音箱API平台 - 1Panel部署方案

## 📋 部署概述

本文档提供在1Panel服务器环境中部署"爱通知小爱音箱消息推送统一API平台"的完整方案。

## 🛠️ 环境要求

- **服务器**: 1Panel管理面板
- **Python**: 3.9+
- **数据库**: MySQL 8.0+
- **内存**: 建议2GB+
- **存储**: 建议10GB+

## 📦 部署步骤

### 1. 创建Docker应用

在1Panel中创建新的Docker应用，使用以下配置：

#### Dockerfile
```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  miapi:
    build: .
    container_name: miapi-platform
    ports:
      - "9000:8000"
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_USER=miapi
      - DB_PASSWORD=your_secure_password
      - DB_NAME=miapi
      - JWT_SECRET_KEY=your_jwt_secret_key_here
      - JWT_ALGORITHM=HS256
      - JWT_EXPIRE_HOURS=24
      - PLATFORM_NAME=爱通知小爱音箱消息推送统一API平台
      - REGISTRATION_ENABLED=true
      - MAX_DEVICES_PER_USER=10
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      - mysql
    restart: unless-stopped
    networks:
      - miapi-network

  mysql:
    image: mysql:8.0
    container_name: miapi-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=root_password
      - MYSQL_DATABASE=miapi
      - MYSQL_USER=miapi
      - MYSQL_PASSWORD=your_secure_password
    volumes:
      - mysql_data:/var/lib/mysql
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"
    restart: unless-stopped
    networks:
      - miapi-network

volumes:
  mysql_data:

networks:
  miapi-network:
    driver: bridge
```

### 2. 环境变量配置

在1Panel中设置以下环境变量：

```bash
# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_USER=miapi
DB_PASSWORD=your_secure_password_here
DB_NAME=miapi

# JWT配置
JWT_SECRET_KEY=your_very_secure_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# 平台配置
PLATFORM_NAME=爱通知小爱音箱消息推送统一API平台
REGISTRATION_ENABLED=true
MAX_DEVICES_PER_USER=10

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/app/logs/miapi.log
```

### 3. 数据库初始化

#### 创建数据库用户和权限
```sql
CREATE DATABASE IF NOT EXISTS miapi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'miapi'@'%' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON miapi.* TO 'miapi'@'%';
FLUSH PRIVILEGES;
```

#### 执行数据库初始化脚本
数据库表结构会通过 `database/init.sql` 文件自动创建。

### 4. 反向代理配置

在1Panel的网站管理中配置Nginx反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL证书配置
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # 客户端最大请求体大小
    client_max_body_size 10M;
    
    # API代理
    location /api/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 静态文件服务
    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:9000/health;
        access_log off;
    }
}
```

### 5. 防火墙配置

在1Panel安全设置中开放以下端口：
- **80**: HTTP (重定向到HTTPS)
- **443**: HTTPS
- **8000**: 应用端口 (仅内部访问)
- **3306**: MySQL (仅内部访问)

### 6. 监控和日志

#### 日志配置
```yaml
# 在docker-compose.yml中添加日志配置
services:
  miapi:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

#### 健康检查
```yaml
# 在docker-compose.yml中添加健康检查
services:
  miapi:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 🚀 部署流程

### 1. 准备部署文件
```bash
# 在1Panel文件管理中创建项目目录
mkdir -p /opt/miapi-platform
cd /opt/miapi-platform

# 上传项目文件
# 通过1Panel文件管理上传整个项目目录
```

### 2. 构建和启动
```bash
# 在1Panel终端中执行
cd /opt/miapi-platform

# 构建并启动服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f miapi
```

### 3. 验证部署
```bash
# 检查服务健康状态
curl http://localhost:8000/health

# 检查API响应
curl http://localhost:8000/api/v1/devices
```

## 🔧 维护操作

### 更新应用
```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up -d --build
```

### 备份数据库
```bash
# 创建数据库备份
docker exec miapi-mysql mysqldump -u miapi -p miapi > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 查看日志
```bash
# 查看应用日志
docker-compose logs -f miapi

# 查看数据库日志
docker-compose logs -f mysql
```

## 🔒 安全建议

1. **定期更新密码**: 定期更换数据库密码和JWT密钥
2. **SSL证书**: 使用有效的SSL证书确保HTTPS访问
3. **防火墙**: 仅开放必要的端口
4. **备份策略**: 建立定期数据备份机制
5. **监控告警**: 配置服务监控和异常告警

## 📊 性能优化

### 数据库优化
```sql
-- 在MySQL中执行以下优化配置
SET GLOBAL innodb_buffer_pool_size = 1073741824; -- 1GB
SET GLOBAL max_connections = 200;
SET GLOBAL query_cache_size = 67108864; -- 64MB
```

### 应用优化
```yaml
# 在docker-compose.yml中设置资源限制
services:
  miapi:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## 🆘 故障排除

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep :8000
   
   # 检查Docker日志
   docker-compose logs miapi
   ```

2. **数据库连接失败**
   ```bash
   # 检查数据库状态
   docker-compose exec mysql mysql -u miapi -p -e "SELECT 1;"
   ```

3. **内存不足**
   ```bash
   # 检查系统资源
   free -h
   df -h
   ```

## 📞 技术支持

如遇到部署问题，请检查：
1. 1Panel系统日志
2. Docker容器日志
3. 应用程序日志
4. 数据库连接状态

## 📍 访问地址

部署完成后，可通过以下地址访问：

- **主页**: `http://your-domain.com` 或 `http://localhost:9000`
- **登录页面**: `http://your-domain.com/pages/login.html`
- **管理后台**: `http://your-domain.com/pages/dashboard.html`
- **API文档**: `http://your-domain.com/docs`
- **健康检查**: `http://your-domain.com/health`

---

**部署完成后，您的小米音箱API平台将在 `https://your-domain.com` 上运行！**