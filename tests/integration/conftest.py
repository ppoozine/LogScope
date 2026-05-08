"""Integration test fixtures: real Postgres + Redis from docker-compose.

Assumes `make up && make migrate` has been run; tests will run admin login
and reuse the seeded admin user. Each test cleans up its own data.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def pytest_configure(config):  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    settings = get_settings()
    os.environ.setdefault("LOGSCOPE_ADMIN_EMAIL", settings.admin_email)
    os.environ.setdefault("LOGSCOPE_ADMIN_PASSWORD", settings.admin_password)


@pytest.fixture
async def app() -> AsyncGenerator[FastAPI]:
    from app.main import create_app

    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Yield a transactional AsyncSession that rolls back after each test."""
    from app.core.config import get_settings
    from app.core.database import init_database

    db = init_database(get_settings().database_url)
    await db.connect()
    try:
        async with db._sessionmaker() as session:  # type: ignore[union-attr]
            async with session.begin():
                yield session
                await session.rollback()
    finally:
        await db.disconnect()
