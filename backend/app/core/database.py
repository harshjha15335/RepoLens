"""Database engine and session management for CodeMentor-RAG."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


_engine = None
_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=(settings.app_env == "development"),
            future=True,
        )
        if settings.database_url.startswith("sqlite"):
            @event.listens_for(_engine.sync_engine, "connect")
            def enable_foreign_keys(connection, _connection_record):
                connection.execute("PRAGMA foreign_keys=ON")
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncSession:
    """Dependency for getting a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Initialize the database, creating all tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
