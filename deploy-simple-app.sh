#!/bin/bash

# 简化应用部署脚本
# 跳过MySQL相关配置，直接部署应用

set -e

echo "🚀 开始部署小米音箱API平台（跳过MySQL配置）..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3未安装，请先安装pip3"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "❌ 未找到 .env 配置文件"
    echo "请确保项目根目录存在 .env 文件，包含以下配置："
    echo "API_HOST=0.0.0.0"
    echo "API_PORT=8000"
    echo "DB_HOST=your_db_host"
    echo "DB_PORT=3306"
    echo "DB_USER=your_db_user"
    echo "DB_PASSWORD=your_db_password"
    echo "DB_NAME=your_db_name"
    echo "JWT_SECRET_KEY=your_jwt_secret"
    exit 1
else
    echo "✅ 发现现有 .env 配置文件"
    # 验证必要的配置项
    if ! grep -q "^DB_HOST=" .env || ! grep -q "^DB_USER=" .env || ! grep -q "^DB_PASSWORD=" .env; then
        echo "⚠️ .env 文件缺少必要的数据库配置项"
        echo "请确保包含：DB_HOST, DB_USER, DB_PASSWORD, DB_NAME"
        exit 1
    fi
    echo "✅ 环境配置验证通过"
fi

# 读取API端口和主机配置
API_PORT=$(grep "^API_PORT=" .env | cut -d'=' -f2 | tr -d ' \r\n' || echo "8000")
API_HOST=$(grep "^API_HOST=" .env | cut -d'=' -f2 | tr -d ' \r\n' || echo "0.0.0.0")

# 如果API_HOST为空，设置默认值
if [ -z "$API_HOST" ]; then
    API_HOST="0.0.0.0"
fi

# 如果API_PORT为空，设置默认值
if [ -z "$API_PORT" ]; then
    API_PORT="8000"
fi

echo "📡 API服务配置: $API_HOST:$API_PORT"

# 读取数据库配置
DB_HOST=$(grep "^DB_HOST=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_PORT=$(grep "^DB_PORT=" .env | cut -d'=' -f2 | tr -d ' \r\n' || echo "3306")
DB_USER=$(grep "^DB_USER=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_PASSWORD=$(grep "^DB_PASSWORD=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_NAME=$(grep "^DB_NAME=" .env | cut -d'=' -f2 | tr -d ' \r\n')

# 检查必要的数据库配置
if [ -z "$DB_HOST" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ]; then
    echo "❌ 数据库配置不完整:"
    echo "DB_HOST: '$DB_HOST'"
    echo "DB_USER: '$DB_USER'"
    echo "DB_PASSWORD: [${#DB_PASSWORD} 字符]"
    echo "DB_NAME: '$DB_NAME'"
    echo "请检查 .env 文件中的数据库配置"
    exit 1
fi

echo "🗄️ 数据库配置: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"

# 测试数据库连接
echo "🔍 测试数据库连接..."
if command -v mysql &> /dev/null; then
    # 测试连接，捕获错误信息
    DB_TEST_RESULT=$(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME; SELECT 1;" 2>&1)
    if [ $? -eq 0 ]; then
        echo "✅ 数据库连接测试成功"
    else
        echo "⚠️ 数据库连接测试失败，但继续部署"
        echo "错误信息: $DB_TEST_RESULT"
        echo "💡 提示: 请确保数据库服务正在运行，并且网络连接正常"
        echo "应用启动后可能会因数据库连接问题而失败"
    fi
else
    echo "⚠️ 未安装mysql客户端，跳过数据库连接测试"
fi

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
After=network.target

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
    echo "💡 常用命令:"
    echo "查看日志: sudo journalctl -u miapi -f"
    echo "重启服务: sudo systemctl restart miapi"
    echo "停止服务: sudo systemctl stop miapi"
    echo "查看状态: sudo systemctl status miapi"
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "sudo journalctl -u miapi -n 50"
    echo ""
    echo "💡 可能的问题:"
    echo "1. 检查 .env 文件中的数据库连接配置"
    echo "2. 确保MySQL数据库正在运行"
    echo "3. 确保数据库用户权限正确"
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
echo "📝 如果遇到数据库连接问题，请检查 .env 文件中的数据库配置"}}}