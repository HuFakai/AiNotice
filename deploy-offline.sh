#!/bin/bash

# 离线部署脚本 - 适用于无法访问Docker Hub的环境
# 使用本地Python环境直接运行，不依赖Docker

set -e

echo "🚀 开始离线部署小米音箱API平台..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3未安装，请先安装pip3"
    exit 1
fi

# 检查MySQL
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL未安装，正在安装MySQL..."
    # CentOS/RHEL
    if command -v yum &> /dev/null; then
        sudo yum install -y mysql-server mysql
        sudo systemctl start mysqld
        sudo systemctl enable mysqld
    # Ubuntu/Debian
    elif command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y mysql-server mysql-client
        sudo systemctl start mysql
        sudo systemctl enable mysql
    else
        echo "❌ 无法自动安装MySQL，请手动安装"
        exit 1
    fi
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

# 设置MySQL root密码
echo "🗄️ 配置MySQL数据库..."
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';"

# 创建数据库和用户
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
fi

# 创建环境变量文件
echo "📝 创建环境配置文件..."
cat > .env << EOF
# API配置
API_PORT=$API_PORT

# 数据库配置
DB_HOST=localhost
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

# 安装Python依赖
echo "📦 安装Python依赖..."
pip3 install -r requirements.txt

# 创建日志目录
mkdir -p logs

# 创建systemd服务文件
echo "⚙️ 创建系统服务..."
sudo tee /etc/systemd/system/miapi.service > /dev/null << EOF
[Unit]
Description=MiAPI Platform
After=network.target mysql.service
Requires=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port $API_PORT
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
    echo "🎉 离线部署完成！"
    echo "📱 访问地址: http://localhost:$API_PORT"
    echo "📊 管理后台: http://localhost:$API_PORT/pages/dashboard.html"
    echo "🔐 登录页面: http://localhost:$API_PORT/pages/login.html"
    echo ""
    echo "📋 重要信息:"
    echo "MySQL Root密码: $MYSQL_ROOT_PASSWORD"
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