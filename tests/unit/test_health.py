from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """Override lifespan to no-op for unit-style health check test."""
    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_a: FastAPI) -> AsyncGenerator[None]:
        yield

    app.router.lifespan_context = _noop_lifespan
    return app


class TestHealth:
    """Tests for /healthz endpoint."""

    async def test_healthz_returns_200(self, app: FastAPI):
        """Should return 200 with status=ok."""
        # Arrange
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Act
            response = await client.get("/healthz")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
