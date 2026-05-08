"""Lifecycle tests for the ClickHouse async client wrapper."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core import clickhouse as ch
from app.core.config import Settings


@pytest.fixture(autouse=True)
async def _reset_global():
    yield
    await ch.close_clickhouse()


async def test_init_skips_when_url_unset():
    settings = Settings.model_construct(clickhouse_url=None)
    with patch("app.core.clickhouse.get_settings", return_value=settings):
        await ch.init_clickhouse()
    assert ch.get_clickhouse() is None


async def test_init_creates_client_when_url_set():
    settings = Settings.model_construct(clickhouse_url="http://x:y@h:8123/db")
    fake_client = AsyncMock()
    with (
        patch("app.core.clickhouse.get_settings", return_value=settings),
        patch(
            "app.core.clickhouse.clickhouse_connect.get_async_client",
            new=AsyncMock(return_value=fake_client),
        ) as get_client,
        patch("app.core.clickhouse.ensure_schema", new=AsyncMock()) as ensure,
    ):
        await ch.init_clickhouse()
    assert ch.get_clickhouse() is fake_client
    get_client.assert_awaited_once_with(dsn="http://x:y@h:8123/db")
    ensure.assert_awaited_once_with(fake_client)


async def test_close_resets_global():
    settings = Settings.model_construct(clickhouse_url="http://x:y@h:8123/db")
    fake_client = AsyncMock()
    with (
        patch("app.core.clickhouse.get_settings", return_value=settings),
        patch(
            "app.core.clickhouse.clickhouse_connect.get_async_client",
            new=AsyncMock(return_value=fake_client),
        ),
        patch("app.core.clickhouse.ensure_schema", new=AsyncMock()),
    ):
        await ch.init_clickhouse()
    await ch.close_clickhouse()
    assert ch.get_clickhouse() is None
    fake_client.close.assert_awaited_once()
