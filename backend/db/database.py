"""
db/database.py
Async SQLAlchemy engine, session factory, and base model.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from sqlalchemy import text
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

# ── Engine ───────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,          # detect stale connections
    echo=settings.debug,
)

# ── Session factory ──────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Base model ───────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


# ── Dependency: FastAPI request-scoped session ───────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health check ─────────────────────────────────────────────
async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("db_connection_failed", error=str(exc))
        return False


# ── Create all tables (dev only — use Alembic in prod) ───────
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("db_tables_created")
