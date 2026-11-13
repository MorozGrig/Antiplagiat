"""Базовый модуль подключения к PostgreSQL.

- FastAPI  -> async engine + async_sessionmaker (asyncpg)
- Celery   -> sync engine  + Session      (psycopg2)

Модели (app.models.models.Base) переиспользуются в обоих режимах.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.models import Base  # noqa: F401  (метаданные для create_all/миграций)

# --------------------------------------------------------------------------- #
# Async (FastAPI)
# --------------------------------------------------------------------------- #
async_engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    echo=settings.db_echo,
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# --------------------------------------------------------------------------- #
# Sync (Celery workers / скрипты)
# --------------------------------------------------------------------------- #
sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=settings.db_pool_pre_ping,
    echo=settings.db_echo,
)

SyncSessionFactory: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #
async def get_db() -> Generator[AsyncSession, None, None]:
    """Dependency для FastAPI-эндпоинтов: отдаёт AsyncSession с авто-закрытием."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------------- #
# Celery / sync helpers
# --------------------------------------------------------------------------- #
@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Контекст-менеджер синхронной сессии для Celery-задач.

    Пример:
        with get_sync_session() as session:
            ...
    """
    session: Session = SyncSessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def dispose_engines() -> None:
    """Вызывается при остановке FastAPI-приложения (lifespan shutdown)."""
    await async_engine.dispose()
    sync_engine.dispose()
