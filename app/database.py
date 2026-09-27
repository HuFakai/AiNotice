# -*- coding: utf-8 -*-
"""
数据库连接和配置模块
"""

import asyncio
import os
from urllib.parse import quote_plus
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from loguru import logger

from app.config import settings


class Base(DeclarativeBase):
    """数据库模型基类"""

    pass


def build_database_url() -> str:
    """根据配置构造 SQLAlchemy 异步连接串（默认 SQLite，可切换 PostgreSQL/MySQL）"""
    # 1) 显式完整连接串优先（便于一键切换）
    if settings.database_url:
        return settings.database_url

    db_type = (settings.db_type or "sqlite").lower()

    if db_type == "sqlite":
        path = settings.db_path or "data/miapi.db"
        if not os.path.isabs(path):
            project_root = os.path.dirname(os.path.dirname(__file__))
            path = os.path.join(project_root, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return f"sqlite+aiosqlite:///{path}"

    user = quote_plus(settings.db_user or "")
    pwd = quote_plus(settings.db_password or "")
    host = settings.db_host or "localhost"

    if db_type in ("postgresql", "postgres", "pg"):
        port = settings.db_port or 5432
        return f"postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{settings.db_name}"

    if db_type == "mysql":
        port = settings.db_port or 3306
        return f"mysql+aiomysql://{user}:{pwd}@{host}:{port}/{settings.db_name}?charset=utf8mb4"

    raise ValueError(f"不支持的数据库类型: {db_type}（可选 sqlite/postgresql/mysql）")


# 创建异步数据库引擎
def create_database_engine():
    """创建数据库引擎（按方言选择连接池参数）"""
    database_url = build_database_url()
    is_sqlite = database_url.startswith("sqlite")

    engine_kwargs = {"echo": settings.db_echo, "pool_pre_ping": True}
    if is_sqlite:
        # SQLite 不使用 QueuePool 的 size/overflow 参数；允许跨线程复用连接
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )

    return create_async_engine(database_url, **engine_kwargs)


# 全局数据库引擎
engine = create_database_engine()

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话
    用于依赖注入
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"数据库会话错误: {e}")
        raise
    finally:
        await session.close()


async def init_database():
    """初始化数据库连接，并按模型自动建表（SQLite/PostgreSQL 开箱即用）"""
    try:
        # 确保所有 ORM 模型已注册到 Base.metadata
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            # 自动创建缺失的表（已存在则跳过，幂等）
            await conn.run_sync(Base.metadata.create_all)

        logger.info(f"数据库初始化成功 - {engine.url.render_as_string(hide_password=True)}")
        
        # 自动植入默认配置种子数据
        async with AsyncSessionLocal() as session:
            await seed_initial_data(session)
            
        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


async def seed_initial_data(session: AsyncSession):
    """为系统配置表种初始值（数据库无关，同时支持 SQLite/PostgreSQL/MySQL）"""
    try:
        from app.models.system_setting import SystemSetting, SettingType
        from sqlalchemy import select
        
        # 检查是否已包含配置项
        result = await session.execute(select(SystemSetting))
        existing = result.scalars().first()
        if existing:
            return
            
        logger.info("系统配置为空，正在初始化默认种子数据...")
        initial_settings = [
            SystemSetting(setting_key='platform_name', setting_value='爱通知消息推送统一API平台', setting_type=SettingType.STRING, description='平台名称', is_public=True),
            SystemSetting(setting_key='platform_version', setting_value='1.0.0', setting_type=SettingType.STRING, description='平台版本', is_public=True),
            SystemSetting(setting_key='registration_enabled', setting_value='true', setting_type=SettingType.BOOLEAN, description='是否允许用户注册', is_public=True),
            SystemSetting(setting_key='api_rate_limit', setting_value='1000', setting_type=SettingType.INT, description='API调用频率限制(次/小时)', is_public=False),
            SystemSetting(setting_key='max_devices_per_user', setting_value='10', setting_type=SettingType.INT, description='每用户最大设备数', is_public=False),
            SystemSetting(setting_key='max_api_keys_per_user', setting_value='10', setting_type=SettingType.INT, description='每用户最大API密钥数', is_public=False),
            SystemSetting(setting_key='jwt_secret_key', setting_value='CHANGE_ME_IN_ENV', setting_type=SettingType.STRING, description='JWT密钥（部署后请改为强随机值）', is_public=False),
            SystemSetting(setting_key='jwt_expire_hours', setting_value='24', setting_type=SettingType.INT, description='JWT过期时间(小时)', is_public=False),
            SystemSetting(setting_key='email_verification_required', setting_value='false', setting_type=SettingType.BOOLEAN, description='是否需要邮箱验证', is_public=True)
        ]
        session.add_all(initial_settings)
        await session.commit()
        logger.info("✅ 默认系统配置种子数据播种完成")
    except Exception as e:
        await session.rollback()
        logger.error(f"❌ 系统配置播种失败: {e}")


async def close_database():
    """关闭数据库连接"""
    try:
        await engine.dispose()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接时出错: {e}")


async def check_database_health() -> dict:
    """检查数据库健康状态（方言自适应）"""
    try:
        dialect = engine.dialect.name
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

            # 版本信息（不同方言查询不同）
            version = dialect
            try:
                if dialect == "sqlite":
                    version = (await conn.execute(text("SELECT sqlite_version()"))).scalar()
                else:
                    version = (await conn.execute(text("SELECT version()"))).scalar()
            except Exception:
                pass

        # 连接池状态（尽力而为；不同池类型方法可能缺失）
        pool_status = {}
        try:
            pool = engine.pool
            for key in ("size", "checkedin", "checkedout", "overflow"):
                fn = getattr(pool, key, None)
                if callable(fn):
                    pool_status[key] = fn()
        except Exception:
            pass

        return {
            "status": "healthy",
            "dialect": dialect,
            "database": settings.db_name,
            "version": version,
            "pool": pool_status,
            "connection": "active",
        }

    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return {"status": "unhealthy", "error": str(e), "connection": "failed"}


async def execute_init_sql():
    """执行数据库初始化SQL脚本"""
    try:
        # 读取初始化SQL文件
        import os

        sql_file = os.path.join(os.path.dirname(__file__), "..", "database", "init.sql")

        if not os.path.exists(sql_file):
            logger.warning("数据库初始化脚本不存在")
            return False

        with open(sql_file, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # 分割SQL语句（简单处理）
        sql_statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

        async with engine.begin() as conn:
            for stmt in sql_statements:
                if stmt and not stmt.startswith("--"):
                    try:
                        await conn.execute(text(stmt))
                    except Exception as e:
                        # 忽略已存在的表等错误
                        if "already exists" not in str(e).lower():
                            logger.warning(f"执行SQL语句失败: {stmt[:50]}... 错误: {e}")

        logger.info("数据库初始化脚本执行完成")
        return True

    except Exception as e:
        logger.error(f"执行数据库初始化脚本失败: {e}")
        return False


# 数据库依赖
def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖注入"""
    return get_database_session()
