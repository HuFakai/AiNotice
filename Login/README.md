# Login 模块文档

## 概述

Login 模块是一个专门用于小米账号登录、Token 管理和 Cookie 处理的独立 Python 模块。该模块提供了完整的小米账号认证流程，包括登录验证、设备信息获取、Token 文件管理以及 Cookie 生成和解析功能。

## 核心功能

### 1. 小米账号登录
- 支持用户名/密码登录
- 自动处理 SSL 证书验证
- 获取登录后的认证信息

### 2. Token 文件生成和管理
- 自动生成包含认证信息的 Token 文件
- 提取关键信息：`deviceId`、`serviceToken`、`userId`
- 支持 Token 文件的读取和解析

### 3. Cookie 生成和解析
- 从 Token 信息生成小米服务 Cookie
- 解析 Cookie 字符串为结构化数据
- 支持多种 Cookie 格式

## 模块结构

```
Login/
├── __init__.py              # 模块初始化和导出
├── config.py                # 配置文件
├── mi_account.py            # 小米账号管理器
├── utils.py                 # 工具函数
├── requirements.txt         # 依赖包
├── test_login_final.py      # 测试程序
└── README.md               # 文档
```

## 主要类和函数

### MiAccountManager 类

主要的账号管理类，提供完整的登录和认证功能。

```python
from Login import MiAccountManager, LoginConfig

# 创建配置
config = LoginConfig(
    account="your_account",
    password="your_password",
    token_path="./token.json"
)

# 创建管理器实例
manager = MiAccountManager(config)

# 执行登录
await manager.login()
```

### 核心工具函数

#### extract_token_info(token_data)
从 Token 数据中提取关键信息。

```python
from Login import extract_token_info

# 提取 Token 信息
token_info = extract_token_info(token_data)
print(f"Device ID: {token_info['deviceId']}")
print(f"User ID: {token_info['userId']}")
print(f"Service Token: {token_info['serviceToken']}")
```

#### get_cookie_from_token(token_path)
从 Token 文件生成 Cookie。

```python
from Login import get_cookie_from_token

# 从 Token 文件生成 Cookie
cookie = await get_cookie_from_token("./token.json")
print(f"Generated Cookie: {cookie}")
```

#### parse_cookie_string(cookie_string)
解析 Cookie 字符串为字典格式。

```python
from Login import parse_cookie_string

# 解析 Cookie 字符串
cookie_dict = parse_cookie_string(cookie_string)
print(f"Parsed Cookie: {cookie_dict}")
```

## 使用流程

### 1. 基本登录流程

```python
import asyncio
from Login import MiAccountManager, LoginConfig

async def login_example():
    # 配置登录信息
    config = LoginConfig(
        account="your_xiaomi_account",
        password="your_password",
        token_path="./my_token.json"
    )
    
    # 创建管理器
    manager = MiAccountManager(config)
    
    try:
        # 执行登录
        await manager.login()
        print("登录成功！")
        
        # 获取设备信息
        device_id = manager.get_device_id()
        user_id = manager.get_user_id()
        service_token = manager.get_service_token()
        
        print(f"Device ID: {device_id}")
        print(f"User ID: {user_id}")
        print(f"Service Token: {service_token}")
        
    except Exception as e:
        print(f"登录失败: {e}")

# 运行示例
asyncio.run(login_example())
```

### 2. Token 文件处理

```python
import json
from Login import extract_token_info

# 读取 Token 文件
with open("./token.json", "r", encoding="utf-8") as f:
    token_data = json.load(f)

# 提取关键信息
token_info = extract_token_info(token_data)

print("Token 信息:")
for key, value in token_info.items():
    print(f"  {key}: {value}")
```

### 3. Cookie 生成和解析

```python
import asyncio
from Login import get_cookie_from_token, parse_cookie_string

async def cookie_example():
    # 从 Token 生成 Cookie
    cookie_string = await get_cookie_from_token("./token.json")
    print(f"生成的 Cookie: {cookie_string}")
    
    # 解析 Cookie
    cookie_dict = parse_cookie_string(cookie_string)
    print("解析后的 Cookie:")
    for key, value in cookie_dict.items():
        print(f"  {key}: {value}")

# 运行示例
asyncio.run(cookie_example())
```

## Token 文件格式

Token 文件是一个 JSON 格式的文件，包含以下关键信息：

```json
{
  "deviceId": "设备ID",
  "userId": "用户ID", 
  "passToken": "认证令牌",
  "micoapi": {
    "serviceToken": "服务令牌"
  }
}
```

## Cookie 格式

生成的 Cookie 包含三个主要部分：

1. **deviceId**: 设备标识符
2. **serviceToken**: 服务认证令牌
3. **userId**: 用户标识符

示例 Cookie 格式：
```
deviceId=XXXXXXXX; serviceToken=YYYYYYYY; userId=ZZZZZZZZ
```

## 配置选项

### LoginConfig 类

```python
from Login import LoginConfig

config = LoginConfig(
    account="xiaomi_account",      # 小米账号（必需）
    password="password",           # 密码（必需）
    token_path="./token.json"      # Token 文件路径（可选，默认为 ./token.json）
)
```

## 依赖要求

模块依赖以下 Python 包：

- `miservice`: 小米服务核心库
- `aiohttp`: 异步 HTTP 客户端
- `requests`: HTTP 请求库
- `pytest`: 测试框架（开发用）
- `pytest-asyncio`: 异步测试支持（开发用）

安装依赖：
```bash
pip install -r requirements.txt
```

## 测试

运行测试程序验证模块功能：

```bash
python3 test_login_final.py
```

测试程序将验证：
- 小米账号登录
- Token 文件生成
- Cookie 生成和解析
- 关键信息提取

## 错误处理

模块提供了完善的错误处理机制：

- **登录失败**: 检查账号密码是否正确
- **网络错误**: 检查网络连接
- **SSL 证书错误**: 模块会自动处理证书验证问题
- **Token 文件错误**: 检查文件路径和权限

## 注意事项

1. **安全性**: 请妥善保管 Token 文件，避免泄露认证信息
2. **网络环境**: 确保网络连接正常，能够访问小米服务
3. **账号安全**: 建议使用应用专用密码而非主密码
4. **文件权限**: 确保程序有读写 Token 文件的权限

## 许可证

本模块遵循原项目的许可证协议。