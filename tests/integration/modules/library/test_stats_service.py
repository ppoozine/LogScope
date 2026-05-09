"""Real ClickHouse: regression guard for StatsService queries.

Caught a bug where Array(UUID) parameter binding failed because clickhouse-connect
doesn't quote individual UUIDs inside the array literal. The unit tests use a
MagicMock client so they never exercise the real driver — these tests do.
"""

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
from app.modules.library.services.stats_service import StatsService

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


async def _seed(client, log_type_id: uuid.UUID, total: int, success: int) -> None:
    recorder = StatsRecorder(client=client)
    await recorder.record(
        ParseEvent(
            ts=datetime.now(UTC).replace(microsecond=0),
            log_type_id=log_type_id,
            parse_rule_id=uuid.uuid4(),
            engine_version="0.32",
            total=total,
            success=success,
            error=total - success,
            latency_ms=10,
            user_id=uuid.uuid4(),
            raw_log_hash=hash16("x"),
            vrl_hash=hash16("y"),
        )
    )


async def test_log_type_stats_against_real_ch(ch_client):
    lt = uuid.uuid4()
    await _seed(ch_client, lt, total=10, success=8)

    svc = StatsService(client=ch_client)
    out = await svc.log_type_stats(lt, "7d")
    assert out.enabled is True
    assert out.totals.total == 10
    assert out.totals.success == 8
    assert out.totals.success_rate == 0.8


async def test_product_coverage_against_real_ch(ch_client):
    """Regression guard: Array(UUID) param needs careful handling — confirm
    a real driver round-trip succeeds for product_coverage with one log_type."""
    lt = uuid.uuid4()
    await _seed(ch_client, lt, total=4, success=4)

    svc = StatsService(client=ch_client)
    out = await svc.product_coverage([lt], "7d")
    assert out.enabled is True
    assert len(out.log_types) == 1
    assert out.log_types[0].log_type_id == lt
    assert out.log_types[0].volume == 4
    assert out.log_types[0].success_rate_avg == 1.0


async def test_product_coverage_with_multiple_ids(ch_client):
    """Multiple UUIDs is the case that originally failed parameter binding."""
    a, b = uuid.uuid4(), uuid.uuid4()
    await _seed(ch_client, a, total=5, success=5)
    await _seed(ch_client, b, total=2, success=1)

    svc = StatsService(client=ch_client)
    out = await svc.product_coverage([a, b], "7d")
    assert out.enabled is True
    by_id = {x.log_type_id: x for x in out.log_types}
    assert by_id[a].volume == 5
    assert by_id[a].success_rate_avg == 1.0
    assert by_id[b].volume == 2
    assert by_id[b].success_rate_avg == 0.5
