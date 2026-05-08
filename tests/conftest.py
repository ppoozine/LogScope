"""Shared pytest fixtures and mock helpers.

Only fixtures that are useful across multiple test files belong here.
Single-test helpers should stay in the test file.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# =============================================================================
# Mock DB helpers (mirroring growin's pattern)
# =============================================================================


def make_mock_session_for_single(return_value):
    """Mock AsyncSession whose `execute().scalar_one_or_none()` returns `return_value`."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


def make_mock_session_for_list(return_value: list):
    """Mock AsyncSession whose `execute().scalars().all()` returns `return_value`."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = return_value
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


def make_mock_session_for_side_effects(side_effects: list):
    """Mock AsyncSession whose `execute()` returns successive results.

    Each item in `side_effects` is either a list (treated as scalars().all())
    or a scalar value (treated as scalar_one_or_none()).
    """
    mock_session = MagicMock()
    mock_results = []
    for value in side_effects:
        mock_result = MagicMock()
        if isinstance(value, list):
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = value
            mock_result.scalars.return_value = mock_scalars
        else:
            mock_result.scalar_one_or_none.return_value = value
        mock_results.append(mock_result)
    mock_session.execute = AsyncMock(side_effect=mock_results)
    return mock_session


# =============================================================================
# Mock Redis helper
# =============================================================================


def make_mock_redis(*, get_return: str | None = None) -> MagicMock:
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=get_return)
    redis.delete = AsyncMock(return_value=1)
    return redis


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app instance with no-op lifespan (no real DB / Redis needed for unit tests)."""
    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_a: FastAPI) -> AsyncGenerator[None]:
        yield

    app.router.lifespan_context = _noop_lifespan
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """AsyncClient bound to the test FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
