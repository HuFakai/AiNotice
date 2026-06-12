#!/bin/bash

# .env 配置文件调试脚本
# 用于检查和诊断环境变量配置问题

echo "🔍 .env 配置文件调试工具"
echo "================================"

# 检查.env文件是否存在
if [ ! -f ".env" ]; then
    echo "❌ .env 文件不存在"
    echo "当前目录: $(pwd)"
    echo "目录内容:"
    ls -la
    exit 1
fi

echo "✅ .env 文件存在"
echo "文件大小: $(wc -c < .env) 字节"
echo "文件行数: $(wc -l < .env) 行"
echo ""

# 显示文件内容（隐藏敏感信息）
echo "📄 .env 文件内容预览:"
echo "--------------------------------"
cat .env | sed 's/PASSWORD=.*/PASSWORD=***HIDDEN***/g' | sed 's/SECRET=.*/SECRET=***HIDDEN***/g'
echo "--------------------------------"
echo ""

# 检查关键配置项
echo "🔧 关键配置项检查:"
echo "--------------------------------"

# API配置
API_HOST=$(grep "^API_HOST=" .env | cut -d'=' -f2 | tr -d ' \r\n')
API_PORT=$(grep "^API_PORT=" .env | cut -d'=' -f2 | tr -d ' \r\n')
echo "API_HOST: '$API_HOST' (长度: ${#API_HOST})"
echo "API_PORT: '$API_PORT' (长度: ${#API_PORT})"

# 数据库配置
DB_HOST=$(grep "^DB_HOST=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_PORT=$(grep "^DB_PORT=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_USER=$(grep "^DB_USER=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_PASSWORD=$(grep "^DB_PASSWORD=" .env | cut -d'=' -f2 | tr -d ' \r\n')
DB_NAME=$(grep "^DB_NAME=" .env | cut -d'=' -f2 | tr -d ' \r\n')

echo "DB_HOST: '$DB_HOST' (长度: ${#DB_HOST})"
echo "DB_PORT: '$DB_PORT' (长度: ${#DB_PORT})"
echo "DB_USER: '$DB_USER' (长度: ${#DB_USER})"
echo "DB_PASSWORD: [${#DB_PASSWORD} 字符]"
echo "DB_NAME: '$DB_NAME' (长度: ${#DB_NAME})"

# JWT配置
JWT_SECRET=$(grep "^JWT_SECRET_KEY=" .env | cut -d'=' -f2 | tr -d ' \r\n')
echo "JWT_SECRET_KEY: [${#JWT_SECRET} 字符]"

echo "--------------------------------"
echo ""

# 配置验证
echo "✅ 配置验证:"
echo "--------------------------------"

# 检查必要配置是否存在
MISSING_CONFIGS=()

if [ -z "$API_HOST" ]; then
    MISSING_CONFIGS+=("API_HOST")
fi

if [ -z "$API_PORT" ]; then
    MISSING_CONFIGS+=("API_PORT")
fi

if [ -z "$DB_HOST" ]; then
    MISSING_CONFIGS+=("DB_HOST")
fi

if [ -z "$DB_USER" ]; then
    MISSING_CONFIGS+=("DB_USER")
fi

if [ -z "$DB_PASSWORD" ]; then
    MISSING_CONFIGS+=("DB_PASSWORD")
fi

if [ -z "$DB_NAME" ]; then
    MISSING_CONFIGS+=("DB_NAME")
fi

if [ -z "$JWT_SECRET" ]; then
    MISSING_CONFIGS+=("JWT_SECRET_KEY")
fi

if [ ${#MISSING_CONFIGS[@]} -eq 0 ]; then
    echo "✅ 所有必要配置项都存在"
else
    echo "❌ 缺少以下配置项:"
    for config in "${MISSING_CONFIGS[@]}"; do
        echo "  - $config"
    done
fi

echo "--------------------------------"
echo ""

# 网络连接测试
echo "🌐 网络连接测试:"
echo "--------------------------------"

if [ -n "$DB_HOST" ] && [ "$DB_HOST" != "localhost" ] && [ "$DB_HOST" != "127.0.0.1" ]; then
    echo "测试到数据库主机的连接: $DB_HOST"
    if ping -c 1 "$DB_HOST" > /dev/null 2>&1; then
        echo "✅ 可以ping通数据库主机"
    else
        echo "❌ 无法ping通数据库主机"
    fi
    
    if command -v telnet > /dev/null 2>&1; then
        echo "测试数据库端口连接: $DB_HOST:$DB_PORT"
        timeout 5 telnet "$DB_HOST" "$DB_PORT" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ 数据库端口可访问"
        else
            echo "❌ 数据库端口不可访问"
        fi
    fi
else
    echo "⚠️ 数据库主机为本地地址，跳过网络测试"
fi

echo "--------------------------------"
echo ""

# 建议
echo "💡 建议和提示:"
echo "--------------------------------"
echo "1. 如果配置项为空，请检查.env文件格式是否正确"
echo "2. 确保配置项格式为: KEY=VALUE（等号两边不要有空格）"
echo "3. 如果是从Windows复制的文件，可能包含\r字符，已自动处理"
echo "4. 数据库连接问题可能是网络、防火墙或数据库服务未启动"
echo "5. 可以使用以下命令手动测试数据库连接:"
if [ -n "$DB_HOST" ] && [ -n "$DB_USER" ] && [ -n "$DB_PASSWORD" ]; then
    echo "   mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASSWORD -e 'SELECT 1;'"
fi
echo "================================"