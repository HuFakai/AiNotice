# 💌 爱通知小爱音箱消息推送统一API平台

> 爱通知是一个企业级的小爱音箱消息推送统一API平台，支持多用户注册、API密钥管理、权限控制等功能，未来将扩展支持邮箱、钉钉、企业微信、飞书等多种通知渠道。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🚀 功能特性

### ✨ 核心功能
- 🔐 **用户认证系统** - 注册、登录、JWT令牌验证
- 🔑 **API密钥管理** - 细粒度权限控制、使用统计
- 👤 **用户管理** - 资料管理、密码修改、活动记录
- 🎤 **小爱音箱控制** - 兼容原有语音播放功能
- 💾 **数据持久化** - MySQL数据库，完整的用户数据管理

### 🔒 安全特性
- JWT令牌认证 + API密钥双重验证
- bcrypt密码哈希加密
- HMAC-SHA256密钥签名验证
- 细粒度权限控制
- 完整的用户活动审计日志

## 📦 快速开始

### 环境要求
- Python 3.9+
- MySQL 8.0+
- 小米账户 (用于设备控制)

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动服务
```bash
python3 start.py
```

服务启动后访问：
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/v1/health

## 📖 API 使用指南

### 1. 用户注册
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your_username",
    "email": "your@email.com",
    "password": "YourPassword123",
    "display_name": "Your Name"
  }'
```

### 2. 用户登录
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username_or_email": "your_username",
    "password": "YourPassword123"
  }'
```

### 3. 创建API密钥
```bash
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "My API Key",
    "permissions": {
      "speak": true,
      "get_devices": true,
      "manage_devices": false
    }
  }'
```

### 4. 使用API密钥调用
```bash
# 获取设备列表
curl -H "Authorization: Bearer xai_sk_your_api_key" \
  http://localhost:8000/api/v1/devices

# 语音播放
curl -X POST http://localhost:8000/api/v1/speak \
  -H "Authorization: Bearer xai_sk_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from API!",
    "device_id": "device_id_here"
  }'
```

## 🏗️ 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   MySQL         │
│   (HTML/JS)     │◄──►│   Backend       │◄──►│   Database      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   MiService     │
                       │   (小米设备)      │
                       └─────────────────┘
```

### 数据库表结构
- `users` - 用户信息
- `mi_accounts` - 小米账户绑定
- `devices` - 设备管理
- `api_keys` - API密钥
- `speak_tasks` - 语音任务
- `user_activities` - 活动日志
- `system_settings` - 系统配置

## 🔧 配置说明

### 环境变量
```bash
# 数据库配置
DB_HOST=your_mysql_host
DB_PORT=3306
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=miapi

# JWT配置
JWT_SECRET_KEY=your-super-secret-key
JWT_EXPIRE_HOURS=24

# 小米账户 (可选)
MI_USER=your_xiaomi_username
MI_PASS=your_xiaomi_password
```

## 📚 API 文档

### 认证相关 (`/api/v1/auth`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/register` | POST | 用户注册 |
| `/login` | POST | 用户登录 |
| `/logout` | POST | 用户登出 |
| `/verify` | POST | 验证令牌 |
| `/me` | GET | 获取当前用户 |

### 用户管理 (`/api/v1/user`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/profile` | GET | 获取用户资料 |
| `/profile` | PUT | 更新用户资料 |
| `/change-password` | POST | 修改密码 |
| `/activities` | GET | 获取活动记录 |

### API密钥 (`/api/v1/api-keys`)
| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 获取密钥列表 |
| `/` | POST | 创建新密钥 |
| `/{id}` | PUT | 更新密钥 |
| `/{id}` | DELETE | 删除密钥 |

### 设备控制
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/devices` | GET | 获取设备列表 |
| `/api/v1/speak` | POST | 语音播放 |
| `/api/v1/speak/status/{task_id}` | GET | 获取任务状态 |

## 🧪 测试

> 暂未提供自动化测试套件。可通过 Swagger UI（`/docs`）或 `curl` 手动验证各接口。
> 后续将为 auth / api-keys / speak 关键路径补充 pytest 冒烟测试。

## 📁 项目结构

```
miAPI/
├── app/                    # 应用主目录
│   ├── models/            # 数据模型
│   ├── routers/           # API路由
│   ├── services/          # 业务逻辑
│   ├── schemas/           # 数据验证模式
│   ├── utils/             # 工具函数
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库连接
│   └── main.py            # 主应用
├── frontend/              # 前端页面
├── database/              # 数据库脚本
├── docs/                  # 项目文档
├── requirements.txt       # Python依赖
├── start.py               # 启动脚本
└── README.md             # 项目说明
```

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Python Web框架
- [SQLAlchemy](https://sqlalchemy.org/) - Python SQL工具包
- [MiService](https://github.com/Yonsm/MiService) - 小米设备控制库

## 📞 联系方式

如有问题或建议，请创建 [Issue](../../issues) 或联系项目维护者。

---

⭐ 如果这个项目对你有帮助，请给个星标支持一下！