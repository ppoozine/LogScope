"""Local fixtures for copilot inline router tests.

These tests use dependency_overrides to mock all external services,
so they don't need a real Postgres / Redis — override the integration-level
app fixture with a no-op lifespan.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app with no-op lifespan (no real DB / Redis needed)."""
    from app.main import create_app

    application = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_a: FastAPI) -> AsyncGenerator[None]:
        yield

    application.router.lifespan_context = _noop_lifespan
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """AsyncClient bound to the test FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
