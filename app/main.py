# -*- coding: utf-8 -*-
"""
爱通知小爱音箱消息推送统一API平台主应用程序
FastAPI应用程序入口点
"""

import os
import sys
import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Set
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import uvicorn

from app.config import get_settings
from app.dependencies import get_db
from app.routers import speak


# 应用派生的后台任务集合：持有强引用防止被 GC，并在应用关闭时尽力收敛。
# 用法：spawn("任务名", coro) 即可。
_background_tasks: Set[asyncio.Task] = set()


def spawn(name: str, coro: Awaitable) -> asyncio.Task:
    """派生一个后台任务并纳入关闭收敛集合（自动 discard）"""
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(_log_task_failure)
    return task


def _log_task_failure(task: asyncio.Task) -> None:
    """后台任务异常兜底记录（避免异常被静默吞掉）"""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(f"后台任务 {task.get_name()} 异常退出: {exc}")


async def _drain_background_tasks(timeout: float = 5.0) -> None:
    """关闭时对在途后台任务做一次尽力收敛：先等待，超时后取消。"""
    pending = [t for t in _background_tasks if not t.done()]
    if not pending:
        return
    logger.info(f"正在等待 {len(pending)} 个在途后台任务完成（最多 {timeout} 秒）...")
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    for task in still_pending:
        task.cancel()
    if still_pending:
        await asyncio.gather(*still_pending, return_exceptions=True)
        logger.warning(f"已取消 {len(still_pending)} 个未在超时内完成的后台任务")
    else:
        logger.info(f"在途后台任务已全部收敛（{len(done)} 个）")


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
        # 密钥安全检查：弱默认 JWT/加密密钥自动生成强随机值并写回 .env
        # （必须在任何 JWT 签发/数据加解密发生之前执行）
        from app.utils.security_keys import ensure_strong_secrets

        ensure_strong_secrets()

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

    # 对在途后台任务做一次尽力收敛（等待/超时取消），避免关闭时挂起或泄漏
    try:
        await _drain_background_tasks()
    except Exception as e:
        logger.error(f"后台任务收敛失败: {e}")

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
    # 平台使用 Authorization: Bearer 令牌认证（非 Cookie），因此 allow_origins="*" 时不携带凭据，
    # 避免「* + allow_credentials=True」这一无效且不安全的组合。
    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=(cors_origins != ["*"]),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 调用日志中间件：记录已认证 /api/v1 请求的真实端点/状态/耗时
    # （异步后台写库，不阻塞请求；替代已被删除的旧死代码中间件）
    from app.middleware.api_call_log import ApiCallLogMiddleware

    app.add_middleware(ApiCallLogMiddleware)

    # 添加路由
    from app.routers.auth import router as auth_router
    from app.routers.user import router as user_router
    from app.routers.api_keys import router as api_keys_router
    from app.routers.mi_accounts import router as mi_accounts_router
    from app.routers.analytics import router as analytics_router
    from app.routers.notification_channels import router as notification_channels_router
    from app.routers.notifications import router as notifications_router
    from app.routers.media import router as media_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(user_router, prefix="/api/v1")
    app.include_router(api_keys_router, prefix="/api/v1")
    app.include_router(mi_accounts_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(notification_channels_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(media_router, prefix="/api/v1")
    # speak 路由自身 prefix="/speak"，与其它 router 一致由这里统一加 /api/v1
    app.include_router(speak.router, prefix="/api/v1")

    # 全局健康检查（唯一实现）：
    # 原 speak.py 与 analytics.py 各自注册了健康检查（前者 /api/v1/health 且不查库，
    # 后者 /api/v1/analytics/health），实现分裂且互相遮蔽。
    # 现统一收敛到此处：检查数据库连通性并返回服务版本。
    # 同时保留 /api/v1/analytics/health 别名，兼容既有调用方（同一实现，不再各写一份）。
    @app.get("/api/v1/health", tags=["健康检查"], summary="健康检查")
    @app.get("/api/v1/analytics/health", tags=["健康检查"], include_in_schema=False)
    async def health_check(db: AsyncSession = Depends(get_db)):
        """健康检查接口：返回服务版本并探测数据库连通性"""
        services = {"database": "unhealthy", "api": "healthy", "analytics": "healthy"}
        healthy = False
        try:
            await db.execute(text("SELECT 1"))
            services["database"] = "healthy"
            healthy = True
        except Exception as e:
            services["database"] = "unhealthy"
            services["analytics"] = "unhealthy"
            logger.error(f"健康检查数据库探测失败: {e}")

        return {
            "success": True,
            "status": "healthy" if healthy else "unhealthy",
            "service": "miAPI",
            "version": app.version,
            "services": services,
        }

    # 全局异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理"""
        logger.error(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "服务器内部错误", "detail": str(exc) if settings.api_debug else "请联系管理员"},
        )

    # 挂载前端
    # Vue 3 SPA（Vite 构建产物 frontend/dist）：静态资源 + history 路由 fallback。
    # 任何目录缺失都不能导致应用启动失败。
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    vite_dist = os.path.join(frontend_path, "dist")

    # 上传音频的公开静态访问（音箱拉取播放需匿名；目录不存在则跳过）
    media_store = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "media")
    if os.path.isdir(media_store):
        app.mount("/media", StaticFiles(directory=media_store), name="media-store")

    if os.path.isdir(vite_dist):
        assets_dir = os.path.join(vite_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

        @app.get("/{full_path:path}", include_in_schema=False, summary="SPA 入口")
        async def spa_fallback(full_path: str):
            """history 路由 fallback：非 API 的 GET 请求一律回退到 index.html"""
            if full_path.startswith("api/") or full_path == "api":
                return JSONResponse(status_code=404, content={"success": False, "message": "接口不存在"})
            candidate = os.path.normpath(os.path.join(vite_dist, full_path))
            # 防路径穿越：候选文件必须仍在 dist 目录内
            if candidate.startswith(os.path.normpath(vite_dist)) and os.path.isfile(candidate):
                return FileResponse(candidate)
            index_path = os.path.join(vite_dist, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

    else:
        # 没有可用前端构建产物时，保持API根路径
        logger.warning(f"未找到前端构建产物 ({vite_dist})，请执行: cd frontend && npm run build")

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
