"""数据库连接管理 — PostgreSQL (async) + SQLite 开发模式"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

# === 数据库引擎 ===
if settings.USE_SQLITE:
    # 支持环境变量覆盖 DATABASE_URL，测试时可用 ":memory:" 避免文件锁问题
    import os as _os
    _db_url = _os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./officetool_dev.db")
    engine = create_async_engine(
        _db_url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    # W9.8: 使用可配置的连接池参数支持 50 QPS
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_POOL_OVERFLOW,
        pool_pre_ping=True,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库：创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
