# -*- coding: utf-8 -*-
"""
数据库连接和配置模块
"""

import hashlib
import os
from urllib.parse import quote_plus
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event, inspect
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
        # 注意：db_path 可能是裸文件名（无目录部分），此时 dirname 为空串，
        # 直接 makedirs("") 会抛 FileNotFoundError，必须先判空。
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
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

# SQLite 连接级 PRAGMA：
# - foreign_keys=ON：SQLite 默认不强制外键约束，开启后 ondelete=CASCADE 等语义才生效
# - journal_mode=WAL：提升并发读性能（该 PRAGMA 是持久化的，重复执行无副作用）
# - busy_timeout=5000：写锁冲突时最多等待 5 秒再报 "database is locked"
if engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - 连接层钩子
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# 轻量迁移机制
# ---------------------------------------------------------------------------
# 新增迁移项的写法（列表项为 dict）：
#   {"table": "表名", "column": "列名", "ddl": "方言无关的列定义"}
# 例如为 users 表补充 phone 列：
#   {"table": "users", "column": "phone", "ddl": "VARCHAR(50)"}
#
# 工作机制：ensure_schema_upgrades() 会先用 sqlalchemy.inspect 检查表是否存在、
# 列是否已存在，仅当「表存在且列缺失」时执行：
#     ALTER TABLE <table> ADD COLUMN <column> <ddl>
# 该语句在 SQLite / PostgreSQL / MySQL 上对「不存在的简单列」都兼容。
# 注意：
#   - 仅支持简单类型、可空列（不适用于修改/删除列、加约束等复杂变更）；
#   - ddl 中请避免方言特有语法（如 SQLite 不支持在 ADD COLUMN 时加非空无默认值）；
#   - 迁移项应保持幂等语义，重复执行安全（缺列才加）。
MIGRATIONS: list[dict] = [
    # API Key 哈希化存储（安全整改）：明文列保留用于历史兼容，新列由迁移补齐
    {"table": "api_keys", "column": "key_hash", "ddl": "VARCHAR(64)"},
    {"table": "api_keys", "column": "key_prefix", "ddl": "VARCHAR(16)"},
    # JWT 令牌版本（登出/改密即时失效旧令牌）
    {"table": "users", "column": "token_version", "ddl": "INTEGER DEFAULT 0"},
    # 扫码会话 Cookie（lp 长轮询需携带 loginUrl 阶段的 Cookie）
    {"table": "mi_qr_sessions", "column": "cookies_json", "ddl": "TEXT"},
    # API Key 绑定的通知渠道ID列表（JSON 数组文本）
    {"table": "api_keys", "column": "channel_ids", "ddl": "TEXT"},
]


def _column_exists(inspector, table: str, column: str) -> bool:
    """判断指定表的列是否已存在（通过 SQLAlchemy Inspector，方言无关）"""
    try:
        columns = inspector.get_columns(table)
    except Exception:
        return False
    return any(col.get("name") == column for col in columns)


def ensure_schema_upgrades(connection) -> list[str]:
    """
    执行轻量结构升级：为已存在但缺列的表补齐 MIGRATIONS 中声明的列。

    Args:
        connection: SQLAlchemy 同步 Connection（由 run_sync 传入）

    Returns:
        实际执行的迁移描述列表（便于日志/测试断言）
    """
    applied: list[str] = []
    if not MIGRATIONS:
        return applied

    inspector = inspect(connection)
    for mig in MIGRATIONS:
        table = mig.get("table")
        column = mig.get("column")
        ddl = mig.get("ddl")
        if not (table and column and ddl):
            logger.warning(f"跳过无效迁移项（缺少 table/column/ddl）: {mig}")
            continue

        try:
            if not inspector.has_table(table):
                # 表不存在时由 create_all 负责建全量结构，无需补列
                continue
            if _column_exists(inspector, table, column):
                continue

            stmt = f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'
            connection.execute(text(stmt))
            applied.append(f"{table}.{column}")
            logger.info(f"✅ 结构迁移已应用: {stmt}")
        except Exception as e:
            logger.error(f"结构迁移失败 ({table}.{column}): {e}")

    return applied


# 一次性数据迁移（幂等，可重复执行）：
# 历史版本 SQLEnum 未指定 values_callable，落库的是枚举「成员名」大写形式
# （如 STRING/INT），而模型读取时期望小写「值」。此处统一归一化为小写，
# 否则读取旧数据会抛 LookupError。
_DATA_NORMALIZATIONS: list[dict] = [
    {
        "table": "system_settings",
        "column": "setting_type",
        "sql": "UPDATE system_settings SET setting_type = LOWER(setting_type) "
               "WHERE setting_type <> LOWER(setting_type)",
    },
]


def ensure_data_normalizations(connection) -> list[str]:
    """执行一次性数据归一化（幂等；表/列不存在时自动跳过）"""
    applied: list[str] = []
    inspector = inspect(connection)
    for norm in _DATA_NORMALIZATIONS:
        table = norm["table"]
        column = norm["column"]
        try:
            if not inspector.has_table(table) or not _column_exists(inspector, table, column):
                continue
            result = connection.execute(text(norm["sql"]))
            if result.rowcount:
                applied.append(f"{table}.{column} ({result.rowcount} rows)")
                logger.info(f"✅ 数据归一化已应用: {table}.{column} 更新 {result.rowcount} 行")
        except Exception as e:
            logger.error(f"数据归一化失败 ({table}.{column}): {e}")
    return applied


def migrate_legacy_api_keys(connection) -> int:
    """
    一次性数据迁移（幂等）：把历史明文存储的 API Key 迁移为哈希存储。

    对 key_hash 为空且明文列有值的行：补算 SHA-256 哈希与前缀，并清除明文。
    SQLite 的旧表结构中 api_key/api_secret 是 NOT NULL，无法在线解除约束，
    因此在该方言上明文列改存哈希副本；其余方言直接置 NULL。
    迁移后密钥校验完全走 key_hash，数据库不再持有任何明文密钥。
    """
    migrated = 0
    try:
        inspector = inspect(connection)
        if not inspector.has_table("api_keys"):
            return 0
        columns = {col.get("name"): col for col in inspector.get_columns("api_keys")}
        if "key_hash" not in columns or "api_key" not in columns:
            return 0

        dialect = connection.dialect.name
        rows = connection.execute(
            text("SELECT id, api_key FROM api_keys WHERE key_hash IS NULL AND api_key IS NOT NULL")
        ).fetchall()
        for row_id, plaintext in rows:
            if not plaintext:
                continue
            plaintext = str(plaintext)
            key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
            key_prefix = plaintext[:12]
            if dialect == "sqlite":
                connection.execute(
                    text("UPDATE api_keys SET key_hash = :h, key_prefix = :p, api_key = :h, api_secret = '' WHERE id = :i"),
                    {"h": key_hash, "p": key_prefix, "i": row_id},
                )
            else:
                connection.execute(
                    text("UPDATE api_keys SET key_hash = :h, key_prefix = :p, api_key = NULL, api_secret = NULL WHERE id = :i"),
                    {"h": key_hash, "p": key_prefix, "i": row_id},
                )
            migrated += 1

        # 非SQLite方言：解除历史 NOT NULL 约束，使新密钥的明文列可以保持 NULL
        if dialect != "sqlite":
            for col in ("api_key", "api_secret"):
                if col in columns and columns[col].get("nullable") is False:
                    if dialect == "postgresql":
                        connection.execute(text(f"ALTER TABLE api_keys ALTER COLUMN {col} DROP NOT NULL"))
                    elif dialect == "mysql":
                        connection.execute(text(f"ALTER TABLE api_keys MODIFY COLUMN {col} VARCHAR(255) NULL"))

        if migrated:
            logger.info(f"✅ API Key 哈希化迁移完成: {migrated} 条明文密钥已转换为哈希存储")
    except Exception as e:
        logger.error(f"API Key 哈希化迁移失败: {e}")
    return migrated


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
            # 对已存在但缺列的表应用轻量迁移（见 MIGRATIONS 说明）
            await conn.run_sync(ensure_schema_upgrades)
            # 一次性数据归一化（如枚举历史大写值 -> 小写）
            await conn.run_sync(ensure_data_normalizations)
            # 历史明文 API Key -> 哈希存储（幂等）
            await conn.run_sync(migrate_legacy_api_keys)

        logger.info(f"数据库初始化成功 - {engine.url.render_as_string(hide_password=True)}")
        
        # 自动植入默认配置种子数据
        async with AsyncSessionLocal() as session:
            await seed_initial_data(session)
            
        return True

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


async def seed_initial_data(session: AsyncSession):
    """为系统配置表种初始值（按 setting_key 逐条补种，已存在则跳过）"""
    try:
        from app.models.system_setting import SystemSetting, SettingType
        from sqlalchemy import select

        # 应用从不读取 jwt_secret_key（JWT 密钥来自 app.config.settings），
        # 种这条数据只会误导排障，故不再种。
        initial_settings = [
            SystemSetting(setting_key='platform_name', setting_value='爱通知消息推送统一API平台', setting_type=SettingType.STRING, description='平台名称', is_public=True),
            SystemSetting(setting_key='platform_version', setting_value='1.0.0', setting_type=SettingType.STRING, description='平台版本', is_public=True),
            SystemSetting(setting_key='registration_enabled', setting_value='true', setting_type=SettingType.BOOLEAN, description='是否允许用户注册', is_public=True),
            SystemSetting(setting_key='api_rate_limit', setting_value='1000', setting_type=SettingType.INT, description='API调用频率限制(次/小时)', is_public=False),
            SystemSetting(setting_key='max_devices_per_user', setting_value='10', setting_type=SettingType.INT, description='每用户最大设备数', is_public=False),
            SystemSetting(setting_key='max_api_keys_per_user', setting_value='10', setting_type=SettingType.INT, description='每用户最大API密钥数', is_public=False),
            SystemSetting(setting_key='jwt_expire_hours', setting_value='24', setting_type=SettingType.INT, description='JWT过期时间(小时)', is_public=False),
            SystemSetting(setting_key='email_verification_required', setting_value='false', setting_type=SettingType.BOOLEAN, description='是否需要邮箱验证', is_public=True),
        ]

        # 逐条检查：已存在则跳过，不存在才插入（支持多次启动增量补种新配置项）
        result = await session.execute(select(SystemSetting.setting_key))
        existing_keys = {row[0] for row in result.all()}

        missing = [s for s in initial_settings if s.setting_key not in existing_keys]
        if not missing:
            logger.debug("系统配置种子数据已完整，无需补种")
            return

        logger.info(f"正在补种 {len(missing)} 条缺失的默认配置项: {[s.setting_key for s in missing]}")
        session.add_all(missing)
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


async def close_database():
    """关闭数据库连接"""
    try:
        await engine.dispose()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接时出错: {e}")
