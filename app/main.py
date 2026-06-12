# -*- coding: utf-8 -*-
"""
爱通知小爱音箱消息推送统一API平台主应用程序
FastAPI应用程序入口点
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn

from app.config import get_settings
from app.routers import speak


# 配置日志
def setup_logging():
    """配置日志系统"""
    settings = get_settings()

    # 删除默认的日志处理器
    logger.remove()

    # 添加控制台日志
    log_level = "DEBUG" if settings.api_debug else "INFO"
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # 创建日志目录
    log_file = "logs/miapi.log"
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 添加文件日志
    logger.add(
        log_file,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )


# 应用程序生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序启动和关闭时的处理"""
    # 启动时执行
    logger.info("🚀 爱通知小爱音箱消息推送统一API平台服务启动中...")

    try:
        # 初始化服务
        settings = get_settings()
        logger.info(f"配置加载完成: 调试模式={settings.api_debug}")

        # 初始化数据库连接
        from app.database import init_database

        db_success = await init_database()
        if db_success:
            logger.info("✅ 数据库连接初始化成功")
        else:
            logger.warning("⚠️ 数据库连接初始化失败，某些功能可能不可用")

        # 小米服务将在用户添加账号后按需初始化
        logger.info("小米服务已准备就绪，等待用户添加账号")
        
        # 初始化定时任务调度器
        try:
            from app.services.scheduler_service import init_scheduler
            scheduler_success = await init_scheduler()
            if scheduler_success:
                logger.info("✅ 定时任务调度器初始化成功")
            else:
                logger.warning("⚠️ 定时任务调度器初始化失败")
        except Exception as e:
            logger.error(f"定时任务调度器初始化异常: {e}")

        logger.success("✅ 爱通知小爱音箱消息推送统一API平台服务启动成功！")

    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        # 不抛出异常，允许API服务启动，但会记录错误

    yield

    # 关闭时执行
    logger.info("🛑 爱通知小爱音箱消息推送统一API平台服务正在关闭...")

    # 关闭定时任务调度器
    try:
        from app.services.scheduler_service import shutdown_scheduler
        await shutdown_scheduler()
        logger.info("定时任务调度器已关闭")
    except Exception as e:
        logger.error(f"关闭定时任务调度器失败: {e}")
    
    # 清理任务
    try:
        from app.services.speak_service import speak_service

        speak_service.cleanup_old_tasks()
        logger.info("任务清理完成")
    except Exception as e:
        logger.error(f"任务清理失败: {e}")

    # 关闭数据库连接
    try:
        from app.database import close_database

        await close_database()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {e}")

    logger.info("👋 爱通知小爱音箱消息推送统一API平台服务已关闭")


# 创建FastAPI应用实例
def create_app() -> FastAPI:
    """创建FastAPI应用实例"""

    # 设置日志
    setup_logging()

    settings = get_settings()

    # 创建应用实例
    app = FastAPI(
        title="爱通知",
        description="通过REST API控制小爱音箱播放文字内容的服务",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开发阶段允许所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加API调用记录中间件
    from app.middleware import ApiLoggingMiddleware
    app.add_middleware(ApiLoggingMiddleware)

    # 添加路由
    from app.routers.auth import router as auth_router
    from app.routers.user import router as user_router
    from app.routers.api_keys import router as api_keys_router
    from app.routers.mi_accounts import router as mi_accounts_router
    from app.routers.analytics import router as analytics_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(user_router, prefix="/api/v1")
    app.include_router(api_keys_router, prefix="/api/v1")
    app.include_router(mi_accounts_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(speak.router)

    # 全局异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理"""
        logger.error(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "服务器内部错误", "detail": str(exc) if settings.api_debug else "请联系管理员"},
        )

    # 挂载静态文件
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(frontend_path):
        # 挂载静态资源
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")
        app.mount("/css", StaticFiles(directory=os.path.join(frontend_path, "css")), name="css")
        app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")
        
        # 前端页面路由
        @app.get("/pages/{page_name}")
        async def serve_page(page_name: str):
            """提供前端页面"""
            page_path = os.path.join(frontend_path, "pages", page_name)
            if os.path.exists(page_path) and page_name.endswith(".html"):
                return FileResponse(page_path)
            return JSONResponse(status_code=404, content={"detail": "Page not found"})
        
        # 具体页面路由
        @app.get("/login")
        async def login_page():
            """登录页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "login.html"))
        
        @app.get("/register")
        async def register_page():
            """注册页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "register.html"))
        
        @app.get("/dashboard")
        async def dashboard_page():
            """仪表板页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "dashboard.html"))
        
        @app.get("/devices")
        async def devices_page():
            """设备管理页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "devices.html"))
        
        @app.get("/mi-accounts")
        async def mi_accounts_page():
            """小米账户管理页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "mi-accounts.html"))
        
        @app.get("/api-keys")
        async def api_keys_page():
            """API密钥管理页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "api-keys.html"))
        
        @app.get("/analytics")
        async def analytics_page():
            """数据分析页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "analytics.html"))
        
        @app.get("/profile")
        async def profile_page():
            """用户资料页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "profile.html"))
        
        @app.get("/docs-page")
        async def docs_page():
            """文档页面"""
            return FileResponse(os.path.join(frontend_path, "pages", "docs.html"))
        
        # 根路径重定向到前端首页
        @app.get("/", summary="前端首页")
        async def root():
            """根路径，返回前端首页"""
            index_path = os.path.join(frontend_path, "pages", "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            # 如果前端文件不存在，返回API信息
            return {
                "service": "爱通知小爱音箱消息推送统一API平台",
                "version": "1.0.0",
                "status": "running",
                "docs": "/docs",
                "redoc": "/redoc",
                "health": "/api/v1/health",
            }
    else:
        # 如果没有前端文件，保持原有的API根路径
        @app.get("/", summary="API根路径")
        async def root():
            """API根路径，返回基本信息"""
            return {
                "service": "爱通知小爱音箱消息推送统一API平台",
                "version": "1.0.0",
                "status": "running",
                "docs": "/docs",
                "redoc": "/redoc",
                "health": "/api/v1/health",
            }

    return app


# 创建应用实例
app = create_app()


# 主函数
def main():
    """主函数，用于直接运行应用"""
    settings = get_settings()

    logger.info(f"启动爱通知小爱音箱消息推送统一API平台服务...")
    logger.info(f"服务地址: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"API文档: http://{settings.api_host}:{settings.api_port}/docs")

    log_level = "debug" if settings.api_debug else "info"
    uvicorn.run(
        "app.main:app", host=settings.api_host, port=settings.api_port, reload=settings.api_debug, log_level=log_level
    )


if __name__ == "__main__":
    main()
