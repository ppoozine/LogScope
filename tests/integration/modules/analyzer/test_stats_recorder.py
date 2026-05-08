"""Real ClickHouse round-trip for StatsRecorder + ensure_schema."""

import os
import uuid
from datetime import UTC, datetime

import clickhouse_connect
import pytest

from app.core.clickhouse_schema import ensure_parse_events_table
from app.modules.analyzer.services.stats_recorder import (
    ParseEvent,
    StatsRecorder,
    hash16,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def ch_client():
    url = os.environ.get("CLICKHOUSE_URL")
    if not url:
        pytest.skip("CLICKHOUSE_URL not set; skipping ClickHouse integration test")
    client = await clickhouse_connect.get_async_client(dsn=url)
    await ensure_parse_events_table(client)
    yield client
    await client.command("TRUNCATE TABLE parse_events")
    await client.close()


async def test_round_trip_writes_and_reads(ch_client):
    lt_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    user_id = uuid.uuid4()
    event = ParseEvent(
        ts=datetime.now(UTC).replace(microsecond=0),
        log_type_id=lt_id,
        parse_rule_id=rule_id,
        engine_version="0.32",
        total=10,
        success=8,
        error=2,
        latency_ms=42,
        user_id=user_id,
        raw_log_hash=hash16("hello"),
        vrl_hash=hash16(".x = 1"),
    )

    recorder = StatsRecorder(client=ch_client)
    await recorder.record(event)

    rows = await ch_client.query(
        "SELECT log_type_id, engine_version, total, success, error, latency_ms "
        "FROM parse_events WHERE log_type_id = {lt:UUID}",
        parameters={"lt": lt_id},
    )
    row = rows.first_row
    assert row is not None
    assert str(row[0]) == str(lt_id)
    assert row[1] == "0.32"
    assert row[2] == 10 and row[3] == 8 and row[4] == 2
    assert row[5] == 42
