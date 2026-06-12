#!/bin/bash

# 简化版部署脚本 - 适用于网络受限环境
# 使用官方Docker Hub镜像，不配置镜像源

set -e

echo "🚀 开始简化部署小米音箱API平台..."

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 生成随机密码
MYSQL_ROOT_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
MYSQL_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
JWT_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
API_PORT=9000

echo "🔐 生成安全配置..."
echo "API端口: $API_PORT"
echo "MySQL Root密码: $MYSQL_ROOT_PASSWORD"
echo "MySQL用户密码: $MYSQL_PASSWORD"
echo "JWT密钥: $JWT_SECRET"

# 创建环境变量文件
echo "📝 创建环境配置文件..."
cat > .env << EOF
# API配置
API_PORT=$API_PORT

# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_NAME=miapi
DB_USER=miapi
DB_PASSWORD=$MYSQL_PASSWORD
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD

# JWT配置
JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# 平台配置
PLATFORM_NAME=爱通知小爱音箱消息推送统一API平台
PLATFORM_VERSION=1.0.0
DEBUG=false
EOF

echo "🐳 创建Docker配置..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: miapi-mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: miapi
      MYSQL_USER: miapi
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      timeout: 20s
      retries: 10

  miapi:
    build: .
    container_name: miapi-platform
    ports:
      - "9000:8000"
    env_file:
      - .env
    depends_on:
      mysql:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  mysql_data:
EOF

# 创建简化的Dockerfile
echo "📦 创建Dockerfile..."
cat > Dockerfile << 'EOF'
# 使用官方Python基础镜像
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 构建并启动服务
echo "🔨 构建Docker镜像..."
docker-compose build --no-cache

echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "📊 检查服务状态..."
docker-compose ps

# 测试服务
echo "🧪 测试服务连接..."
if curl -f http://localhost:9000/health > /dev/null 2>&1; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "🎉 部署完成！"
    echo "📱 访问地址: http://localhost:9000"
    echo "📊 管理后台: http://localhost:9000/pages/dashboard.html"
    echo "🔐 登录页面: http://localhost:9000/pages/login.html"
    echo ""
    echo "📋 重要信息:"
    echo "MySQL Root密码: $MYSQL_ROOT_PASSWORD"
    echo "MySQL用户密码: $MYSQL_PASSWORD"
    echo "JWT密钥: $JWT_SECRET"
    echo ""
    echo "💡 常用命令:"
    echo "查看日志: docker-compose logs -f"
    echo "重启服务: docker-compose restart"
    echo "停止服务: docker-compose down"
    echo "更新服务: docker-compose pull && docker-compose up -d"
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "docker-compose logs"
    exit 1
fi