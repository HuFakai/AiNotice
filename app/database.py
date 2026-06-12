# -*- coding: utf-8 -*-
"""
数据库连接和配置模块
"""

import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from loguru import logger

from app.config import settings


class Base(DeclarativeBase):
    """数据库模型基类"""

    pass


# 创建异步数据库引擎
def create_database_engine():
    """创建数据库引擎"""
    database_url = (
        f"mysql+aiomysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        f"?charset=utf8mb4"
    )

    engine = create_async_engine(
        database_url,
        echo=settings.db_echo,  # 是否输出SQL语句
        pool_size=settings.db_pool_size,  # 连接池大小
        max_overflow=settings.db_max_overflow,  # 连接池溢出大小
        pool_timeout=settings.db_pool_timeout,  # 连接超时时间
        pool_recycle=settings.db_pool_recycle,  # 连接回收时间
        pool_pre_ping=True,  # 连接前ping测试
    )

    return engine


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
    """初始化数据库连接"""
    try:
        # 测试数据库连接
        async with engine.begin() as conn:
            # 执行简单查询测试连接
            result = await conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")

        logger.info(f"数据库初始化成功 - {settings.db_host}:{settings.db_port}/{settings.db_name}")
        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


async def close_database():
    """关闭数据库连接"""
    try:
        await engine.dispose()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接时出错: {e}")


async def check_database_health() -> dict:
    """检查数据库健康状态"""
    try:
        async with engine.begin() as conn:
            # 检查连接
            await conn.execute(text("SELECT 1"))

            # 获取数据库信息
            result = await conn.execute(text("SELECT VERSION() as version"))
            version = result.scalar()

            # 获取连接池状态
            pool = engine.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
            }

            return {
                "status": "healthy",
                "database": settings.db_name,
                "host": settings.db_host,
                "port": settings.db_port,
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
