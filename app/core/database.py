from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all models."""


class DatabaseManager:
    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if self._engine is not None:
            return
        self._engine = create_async_engine(self._url, pool_pre_ping=True)
        self._sessionmaker = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    async def session(self) -> AsyncGenerator[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("DatabaseManager not connected")
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


_db: DatabaseManager | None = None


def init_database(url: str) -> DatabaseManager:
    global _db
    _db = DatabaseManager(url)
    return _db


def get_database() -> DatabaseManager:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI Depends: yield AsyncSession bound to current request."""
    async for session in get_database().session():
        yield session
