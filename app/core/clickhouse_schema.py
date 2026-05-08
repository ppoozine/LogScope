"""Schema bootstrap. Real DDL added in Task 4."""

from clickhouse_connect.driver.asyncclient import AsyncClient


async def ensure_parse_events_table(_client: AsyncClient) -> None:  # pragma: no cover
    pass
