#!/bin/bash
# 小米音箱API平台 - 1Panel快速部署脚本

set -e

echo "🚀 开始部署小米音箱API平台..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 创建必要的目录
echo "📁 创建项目目录..."
mkdir -p logs data

# 设置权限
chmod 755 logs data

# 生成随机密码
echo "🔐 生成安全配置..."
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
JWT_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
ROOT_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
API_PORT=9000

# 创建环境变量文件
echo "📝 创建环境配置文件..."
cat > .env << EOF
# API配置
API_PORT=${API_PORT}

# 数据库配置
DB_HOST=mysql
DB_PORT=3306
DB_USER=miapi
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=miapi
MYSQL_ROOT_PASSWORD=${ROOT_PASSWORD}

# JWT配置
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

# 平台配置
PLATFORM_NAME=爱通知小爱音箱消息推送统一API平台
REGISTRATION_ENABLED=true
MAX_DEVICES_PER_USER=10

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/app/logs/miapi.log
EOF

# 创建Docker Compose文件
echo "🐳 配置Docker镜像源..."
# 创建Docker daemon配置目录（如果不存在）
sudo mkdir -p /etc/docker

# 配置Docker镜像源
sudo tee /etc/docker/daemon.json > /dev/null << 'DOCKER_EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://dockerproxy.com"
  ],
  "insecure-registries": [],
  "debug": false,
  "experimental": false
}
DOCKER_EOF

# 重启Docker服务
echo "🔄 重启Docker服务..."
sudo systemctl daemon-reload
sudo systemctl restart docker

echo "🐳 创建Docker配置..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  miapi:
    build: .
    container_name: miapi-platform
    ports:
      - "9000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      mysql:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - miapi-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  mysql:
    image: mysql:8.0
    container_name: miapi-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=${DB_NAME}
      - MYSQL_USER=${DB_USER}
      - MYSQL_PASSWORD=${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"
    restart: unless-stopped
    networks:
      - miapi-network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      timeout: 20s
      retries: 10
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  mysql_data:

networks:
  miapi-network:
    driver: bridge
EOF

# 创建Dockerfile
echo "📦 创建Dockerfile..."
cat > Dockerfile << 'EOF'
# 使用官方Python基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 配置apt使用国内镜像源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# 配置pip使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
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
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 创建nginx配置模板
echo "🌐 创建Nginx配置模板..."
mkdir -p nginx
cat > nginx/miapi.conf << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 请修改为您的域名
    
    # 重定向到HTTPS (可选)
    # return 301 https://$server_name$request_uri;
    
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
EOF

# 构建并启动服务
echo "🔨 构建Docker镜像..."
if ! docker-compose build; then
    echo "⚠️  镜像构建失败，尝试使用备用方案..."
    echo "🔄 重置Docker镜像源配置..."
    sudo rm -f /etc/docker/daemon.json
    sudo systemctl restart docker
    sleep 10
    
    echo "🔨 重新尝试构建..."
    if ! docker-compose build; then
        echo "❌ 构建失败，请检查网络连接或手动配置镜像源"
        exit 1
    fi
fi

echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 30

# 检查服务状态
echo "🔍 检查服务状态..."
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
    echo "   数据库密码: ${DB_PASSWORD}"
    echo "   JWT密钥: ${JWT_SECRET}"
    echo "   MySQL Root密码: ${ROOT_PASSWORD}"
    echo ""
    echo "💡 请保存上述密码信息！"
    echo "📄 详细配置请查看 .env 文件"
    echo "🌐 Nginx配置模板位于 nginx/miapi.conf"
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "   docker-compose logs miapi"
    echo "   docker-compose logs mysql"
fi

echo ""
echo "📚 常用命令:"
echo "   查看日志: docker-compose logs -f miapi"
echo "   重启服务: docker-compose restart"
echo "   停止服务: docker-compose down"
echo "   更新服务: docker-compose up -d --build"
echo "   备份数据库: docker exec miapi-mysql mysqladump -u miapi -p${DB_PASSWORD} miapi > backup.sql"