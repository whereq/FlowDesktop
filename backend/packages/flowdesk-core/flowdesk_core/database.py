"""Database connection and session management."""

import os

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from flowdesk_core.config import get_settings
from flowdesk_core.slow_query import configure as _configure_slow_query

settings = get_settings()

# Tier 29 #4: pool size + overflow tunable via env (defaults 10 / 20).
_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
)

# Tier 29 #4: bind slow-query listeners.
_configure_slow_query(async_engine)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# The same factory under the name three modules import. `async_session`
# was the name in the flowdesk package this code was extracted from; the
# rename left the importers pointing at a name that no longer existed, so
# `flowdesk_core.premium_trial` could not be imported at all and two
# lazy imports in the API failed when they ran.
async_session = AsyncSessionLocal


def get_engine():
    """The async engine, for the few callers that need a raw connection.

    `engine` is the same object under the name three API routers import;
    that name was in the flowdesk package this code was extracted from
    and was never carried over, so the pool-stats views and the release
    health check silently reported nothing.
    """
    return async_engine


engine = async_engine


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Verify database connectivity.

    Schema is managed by Alembic migrations — do NOT call
    Base.metadata.create_all here, as it races with Alembic and causes
    DuplicateTable errors.
    """
    async with async_engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))
