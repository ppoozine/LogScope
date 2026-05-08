"""Real ClickHouse: schema bootstrap is idempotent and the table is shaped correctly."""

import os

import clickhouse_connect
import pytest

from app.core.clickhouse_schema import ensure_parse_events_table

pytestmark = pytest.mark.integration


@pytest.fixture
async def ch_client():
    url = os.environ.get("CLICKHOUSE_URL")
    if not url:
        pytest.skip("CLICKHOUSE_URL not set; skipping ClickHouse integration test")
    client = await clickhouse_connect.get_async_client(dsn=url)
    yield client
    await client.command("DROP TABLE IF EXISTS parse_events")
    await client.close()


async def test_ensure_creates_table(ch_client):
    await ensure_parse_events_table(ch_client)
    rows = await ch_client.query("EXISTS TABLE parse_events")
    assert rows.first_row[0] == 1


async def test_ensure_is_idempotent(ch_client):
    await ensure_parse_events_table(ch_client)
    await ensure_parse_events_table(ch_client)  # should not error
    rows = await ch_client.query("EXISTS TABLE parse_events")
    assert rows.first_row[0] == 1


async def test_table_has_expected_columns(ch_client):
    await ensure_parse_events_table(ch_client)
    rows = await ch_client.query(
        "SELECT name FROM system.columns WHERE database = currentDatabase() AND table = 'parse_events'"
    )
    columns = {r[0] for r in rows.result_rows}
    assert columns == {
        "ts",
        "log_type_id",
        "parse_rule_id",
        "engine_version",
        "total",
        "success",
        "error",
        "latency_ms",
        "user_id",
        "raw_log_hash",
        "vrl_hash",
    }
