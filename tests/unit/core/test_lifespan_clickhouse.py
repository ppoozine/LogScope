"""Lifespan should call init_clickhouse / close_clickhouse around yield."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

from app.core.lifespan import lifespan


async def test_lifespan_initializes_and_closes_clickhouse():
    app = FastAPI()
    init_mock = AsyncMock()
    close_mock = AsyncMock()
    with (
        patch("app.core.lifespan.init_clickhouse", new=init_mock),
        patch("app.core.lifespan.close_clickhouse", new=close_mock),
        patch("app.core.lifespan.init_database") as init_db,
        patch("app.core.lifespan.init_cache") as init_cache,
    ):
        init_db.return_value.connect = AsyncMock()
        init_db.return_value.disconnect = AsyncMock()
        init_cache.return_value.connect = AsyncMock()
        init_cache.return_value.disconnect = AsyncMock()

        async with lifespan(app):
            init_mock.assert_awaited_once()
            close_mock.assert_not_awaited()
        close_mock.assert_awaited_once()
