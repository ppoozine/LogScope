"""Unit tests for StatsRecorder — verifies no-op + insert + swallow-on-error."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.modules.analyzer.services.stats_recorder import (
    ParseEvent,
    StatsRecorder,
    hash16,
)


def _event(**overrides) -> ParseEvent:
    base = {
        "ts": datetime(2026, 5, 8, tzinfo=UTC),
        "log_type_id": uuid.uuid4(),
        "parse_rule_id": uuid.uuid4(),
        "engine_version": "0.32",
        "total": 3,
        "success": 2,
        "error": 1,
        "latency_ms": 42,
        "user_id": uuid.uuid4(),
        "raw_log_hash": hash16("raw"),
        "vrl_hash": hash16(".x = 1"),
    }
    base.update(overrides)
    return ParseEvent(**base)


async def test_record_noop_when_client_none():
    recorder = StatsRecorder(client=None)
    await recorder.record(_event())  # must not raise


async def test_record_inserts_row_when_client_present():
    client = MagicMock()
    client.insert = AsyncMock()
    recorder = StatsRecorder(client=client)

    event = _event()
    await recorder.record(event)

    client.insert.assert_awaited_once()
    args, _kwargs = client.insert.await_args
    assert args[0] == "parse_events"
    rows = args[1]
    assert len(rows) == 1
    row = rows[0]
    assert row[3] == "0.32"  # engine_version
    assert row[4] == 3 and row[5] == 2 and row[6] == 1
    assert row[9] == event.raw_log_hash and row[10] == event.vrl_hash


async def test_record_swallows_clickhouse_errors():
    client = MagicMock()
    client.insert = AsyncMock(side_effect=RuntimeError("boom"))
    recorder = StatsRecorder(client=client)
    await recorder.record(_event())  # must not raise


def test_hash16_is_deterministic_and_16_bytes():
    h = hash16("hello")
    assert isinstance(h, bytes)
    assert len(h) == 16
    assert hash16("hello") == h
