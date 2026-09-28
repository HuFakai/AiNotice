# 部署指南（Docker 为主）

本项目以 **Docker 部署为唯一推荐的部署方式**，旧的手工部署脚本已移除。

## 一、Docker 部署（推荐）

### 前置要求
- Docker 20+ 与 Docker Compose v2
- 端口可用（默认 9000，通过 `.env` 的 `API_PORT` 调整宿主机映射）

### 快速开始

```bash
# 1. 准备配置
cp .env.example .env
# 按需编辑 .env（端口、注册开关、CORS 等）
# JWT_SECRET_KEY / ENCRYPTION_KEY 留空即可：首次启动自动生成强随机值并写回 .env

# 2. 构建并启动
docker compose up -d --build

# 3. 查看状态与健康检查
docker compose ps
curl http://localhost:9000/api/v1/health
```

访问 `http://localhost:9000` 进入管理控制台（宿主机端口跟随 `.env` 中的 `API_PORT`，容器内固定监听 9000）。

### 数据持久化

| 宿主机路径 | 容器路径 | 说明 |
|---|---|---|
| `./data` | `/app/data` | SQLite 数据库文件 |
| `./logs` | `/app/logs` | 运行日志 |
| `./.env` | `/app/.env` | 配置（**读写挂载**：首次启动自动生成的密钥要写回） |

> 升级镜像后数据不丢失（数据库在卷中）；重大版本升级建议先备份 `./data`。

### 使用 PostgreSQL（可选）

1. `.env` 中设置：
   ```env
   DB_TYPE=postgresql
   DB_HOST=postgres
   DB_PORT=5432
   DB_USER=miapi
   DB_PASSWORD=miapi_change_me
   DB_NAME=miapi
   ```
2. 启动：
   ```bash
   docker compose --profile postgres up -d --build
   ```

### 常用运维命令

```bash
docker compose logs -f miapi      # 跟踪日志
docker compose restart miapi      # 重启
docker compose down               # 停止（保留数据卷）
docker compose up -d --build      # 代码更新后重建
```

### 国内构建网络问题

构建时拉取 node/python 基础镜像或 pip/npm 依赖超时，按以下任一方式处理：

1. **依赖镜像源**（compose 中取消注释 `args` 段）：
   ```yaml
   build:
     args:
       NPM_REGISTRY: https://registry.npmmirror.com
       PIP_INDEX_URL: https://pypi.tuna.tsinghua.edu.cn/simple
   ```
2. **基础镜像加速**：为 Docker daemon 配置 registry-mirrors（如阿里云/中科大镜像加速地址）后 `systemctl restart docker`。
3. **离线导入**：在联网机器 `docker build -t ainotice:latest .` 后 `docker save ainotice:latest | gzip > ainotice.tar.gz`，拷贝到目标服务器 `docker load < ainotice.tar.gz`，再 `docker compose up -d`（compose 会直接使用已存在的镜像）。

### 反向代理（HTTPS）

容器只监听 HTTP 9000，建议前置 Nginx/Caddy 终止 TLS：

```nginx
location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

同时在 `.env` 中设置 `TRUST_PROXY_HEADERS=true`（信任反代传来的真实 IP，用于审计与限流）。

## 二、本地开发环境

```bash
# 1. Python 虚拟环境（推荐 Python 3.11）
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 前端依赖与构建（或开发模式）
cd frontend && npm install && npm run build && cd ..
# 开发热更：cd frontend && npm run dev   （已配置 /api 代理到后端端口）

# 3. 启动后端
python start.py          # 或 .venv/bin/python -m uvicorn app.main:app --port 9000
```

默认 `API_PORT=9000`，访问 `http://localhost:9000`。

## 三、健康检查与验收

- `GET /api/v1/health` → `{"status": "healthy", "services": {"database": "healthy", ...}}`
- 打开控制台首页能正常渲染（前端构建产物由后端托管）
- 登录后各页面（仪表盘/密钥/小米账号/设备/分析/渠道）可正常访问
