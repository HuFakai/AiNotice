#!/bin/bash

# 使用现有MySQL的离线部署脚本
# 适用于服务器已安装MySQL的环境

set -e

echo "🚀 开始部署小米音箱API平台（使用现有MySQL）..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3未安装，请先安装pip3"
    exit 1
fi

# 检查MySQL是否运行
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL未安装，请先安装MySQL"
    exit 1
fi

# 检查MySQL服务状态
echo "🔍 检查MySQL服务状态..."
if ! systemctl is-active --quiet mysqld && ! systemctl is-active --quiet mysql; then
    echo "❌ MySQL服务未运行，正在启动..."
    # 尝试启动MySQL服务
    if systemctl list-unit-files | grep -q mysqld.service; then
        sudo systemctl start mysqld
        sudo systemctl enable mysqld
    elif systemctl list-unit-files | grep -q mysql.service; then
        sudo systemctl start mysql
        sudo systemctl enable mysql
    else
        echo "❌ 无法找到MySQL服务，请检查MySQL安装"
        exit 1
    fi
fi

# 检查现有配置或生成新配置
if [ -f ".env" ]; then
    echo "✅ 发现现有 .env 配置文件，读取配置..."
    API_PORT=$(grep "^API_PORT=" .env | cut -d'=' -f2 || echo "8000")
    API_HOST=$(grep "^API_HOST=" .env | cut -d'=' -f2 || echo "0.0.0.0")
    DB_PASSWORD=$(grep "^DB_PASSWORD=" .env | cut -d'=' -f2)
    JWT_SECRET=$(grep "^JWT_SECRET_KEY=" .env | cut -d'=' -f2)
    
    if [ -z "$DB_PASSWORD" ] || [ -z "$JWT_SECRET" ]; then
        echo "⚠️ .env文件缺少必要配置，将生成新的密码和密钥"
        MYSQL_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        JWT_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
    else
        MYSQL_PASSWORD="$DB_PASSWORD"
        echo "📖 使用现有配置"
    fi
else
    echo "🔐 生成新的安全配置..."
    MYSQL_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    JWT_SECRET=$(openssl rand -base64 64 | tr -d "=+/" | cut -c1-50)
    API_PORT=8000
    API_HOST="0.0.0.0"
fi

echo "📡 API服务配置: $API_HOST:$API_PORT"
echo "🔐 MySQL用户密码: $MYSQL_PASSWORD"
echo "🔑 JWT密钥: ${JWT_SECRET:0:20}..."

# 提示用户输入MySQL root密码
echo "📝 请输入MySQL root密码以创建数据库和用户:"
read -s MYSQL_ROOT_PASSWORD

# 测试MySQL连接
echo "🔗 测试MySQL连接..."
if ! mysql -u root -p$MYSQL_ROOT_PASSWORD -e "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ MySQL连接失败，请检查root密码"
    exit 1
fi

echo "✅ MySQL连接成功"

# 创建数据库和用户
echo "🗄️ 配置数据库..."
mysql -u root -p$MYSQL_ROOT_PASSWORD << EOF
CREATE DATABASE IF NOT EXISTS miapi;
CREATE USER IF NOT EXISTS 'miapi'@'localhost' IDENTIFIED BY '$MYSQL_PASSWORD';
GRANT ALL PRIVILEGES ON miapi.* TO 'miapi'@'localhost';
FLUSH PRIVILEGES;
EOF

# 导入数据库结构
if [ -f "database/init.sql" ]; then
    echo "📊 导入数据库结构..."
    mysql -u miapi -p$MYSQL_PASSWORD miapi < database/init.sql
else
    echo "⚠️ 数据库初始化文件不存在，请手动导入数据库结构"
fi

# 创建或更新环境变量文件
if [ -f ".env" ]; then
    echo "📝 更新现有环境配置文件..."
    # 备份原文件
    cp .env .env.backup
    # 更新数据库密码（如果是新生成的）
    if [ "$MYSQL_PASSWORD" != "$DB_PASSWORD" ]; then
        sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$MYSQL_PASSWORD/" .env
    fi
else
    echo "📝 创建环境配置文件..."
    cat > .env << EOF
# API配置
API_HOST=$API_HOST
API_PORT=$API_PORT
API_DEBUG=True

# JWT认证配置
JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# 数据库配置 (MySQL)
DB_HOST=localhost
DB_PORT=3306
DB_USER=miapi
DB_PASSWORD=$MYSQL_PASSWORD
DB_NAME=miapi

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/miapi.log

# 小米服务配置
MI_SSL_VERIFY=false

# 平台配置
PLATFORM_NAME=爱通知小爱音箱消息推送统一API平台
PLATFORM_VERSION=1.0.0
DEBUG=false
EOF

# 安装Python依赖
echo "📦 安装Python依赖..."
echo "🔧 先安装基础依赖..."
pip3 install aiohttp==3.9.1 aiofiles==23.2.0 httpx==0.25.2 requests==2.31.0 email-validator==2.1.0
echo "📦 安装其他依赖..."
pip3 install -r requirements.txt

# 创建日志目录
mkdir -p logs

# 创建systemd服务文件
echo "⚙️ 创建系统服务..."
sudo tee /etc/systemd/system/miapi.service > /dev/null << EOF
[Unit]
Description=MiAPI Platform
After=network.target mysql.service mysqld.service
Requires=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host $API_HOST --port $API_PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
echo "🚀 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable miapi
sudo systemctl start miapi

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "📊 检查服务状态..."
sudo systemctl status miapi --no-pager

# 测试服务
echo "🧪 测试服务连接..."
if curl -f http://localhost:$API_PORT/health > /dev/null 2>&1; then
    echo "✅ 服务启动成功！"
    echo ""
    echo "🎉 部署完成！"
    echo "📱 访问地址: http://localhost:$API_PORT"
    echo "📊 管理后台: http://localhost:$API_PORT/pages/dashboard.html"
    echo "🔐 登录页面: http://localhost:$API_PORT/pages/login.html"
    echo ""
    echo "📋 重要信息:"
    echo "MySQL用户密码: $MYSQL_PASSWORD"
    echo "JWT密钥: $JWT_SECRET"
    echo ""
    echo "💡 常用命令:"
    echo "查看日志: sudo journalctl -u miapi -f"
    echo "重启服务: sudo systemctl restart miapi"
    echo "停止服务: sudo systemctl stop miapi"
    echo "查看状态: sudo systemctl status miapi"
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "sudo journalctl -u miapi -n 50"
    exit 1
fi

# 配置防火墙
echo "🔥 配置防火墙..."
if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --permanent --add-port=$API_PORT/tcp
    sudo firewall-cmd --reload
    echo "✅ 防火墙配置完成"
elif command -v ufw &> /dev/null; then
    sudo ufw allow $API_PORT/tcp
    echo "✅ 防火墙配置完成"
else
    echo "⚠️ 请手动配置防火墙开放端口 $API_PORT"
fi

echo ""
echo "🎊 部署完成！请访问 http://your-server-ip:$API_PORT 开始使用"