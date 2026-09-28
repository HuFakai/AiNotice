# syntax=docker/dockerfile:1

# ==== 阶段 1：构建前端（Vue 3 + Vite）====
FROM node:20-alpine AS frontend-builder

WORKDIR /build
# 先拷贝依赖清单以利用层缓存
COPY frontend/package.json frontend/package-lock.json ./
# 可用构建参数切换 npm 镜像源（国内构建慢/失败时：--build-arg NPM_REGISTRY=https://registry.npmmirror.com）
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry ${NPM_REGISTRY} && npm ci

COPY frontend/ ./
RUN npm run build

# ==== 阶段 2：Python 运行时 ====
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 先装依赖以利用层缓存
COPY requirements.txt .
# 可用构建参数切换 pip 镜像源（--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple）
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --index-url ${PIP_INDEX_URL} -r requirements.txt

# 拷贝后端代码（Login/ 是小米账号密码登录模块，简化添加账号功能依赖）
COPY app/ ./app/
COPY Login/ ./Login/
COPY start.py .

# 前端构建产物（FastAPI 托管 + history fallback）
COPY --from=frontend-builder /build/dist/ ./frontend/dist/

# 运行时持久化目录（由 compose/docker run 挂载卷）
RUN mkdir -p /app/data /app/logs

EXPOSE 9088

# 健康检查：探测 /api/v1/health（内部固定 9088 端口）
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9088/api/v1/health', timeout=4).status==200 else 1)" || exit 1

# uvicorn 直接启动（容器内不使用 reload）；内部端口固定 9088，外部映射由 -p/compose 决定
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port 9088"]
