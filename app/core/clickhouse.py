"""ClickHouse async client wrapper. Optional — silent no-op when CLICKHOUSE_URL unset."""

from __future__ import annotations

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from app.core.config import get_settings

_client: AsyncClient | None = None


async def init_clickhouse() -> None:
    """Called from FastAPI lifespan. No-op when CLICKHOUSE_URL is unset."""
    global _client
    settings = get_settings()
    if not settings.clickhouse_url:
        return
    _client = await clickhouse_connect.get_async_client(dsn=settings.clickhouse_url)
    await ensure_schema(_client)


async def close_clickhouse() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_clickhouse() -> AsyncClient | None:
    """FastAPI dependency. None when ClickHouse is not configured."""
    return _client


async def ensure_schema(client: AsyncClient) -> None:
    """Imported lazily here to avoid a circular import; real impl in clickhouse_schema."""
    from app.core.clickhouse_schema import ensure_parse_events_table

    await ensure_parse_events_table(client)
