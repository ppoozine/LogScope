"""Unit tests for StatsService — uses mocked CH client."""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.library.services.stats_service import RANGE_TO_DAYS, StatsService


def _query_result(rows):
    res = MagicMock()
    res.result_rows = rows
    return res


@pytest.fixture
def lt_id():
    return uuid.uuid4()


async def test_disabled_returns_empty_log_type_stats(lt_id):
    svc = StatsService(client=None)
    out = await svc.log_type_stats(lt_id, "7d")
    assert out.enabled is False
    assert out.range_days == 7
    assert out.timeline == []
    assert out.engine_usage == []
    assert out.totals.total == 0


async def test_log_type_stats_aggregates_timeline(lt_id):
    client = MagicMock()
    client.query = AsyncMock(
        return_value=_query_result(
            [
                (date(2026, 5, 7), 10, 8, 2, "0.32"),
                (date(2026, 5, 8), 4, 4, 0, "0.25"),
            ]
        )
    )
    svc = StatsService(client=client)
    out = await svc.log_type_stats(lt_id, "7d")

    assert out.enabled is True
    assert out.range_days == 7
    days = [p.day for p in out.timeline]
    assert days == ["2026-05-07", "2026-05-08"]
    assert out.timeline[0].success_rate == 0.8
    assert out.timeline[1].success_rate == 1.0
    assert out.totals.total == 14
    assert out.totals.success == 12
    assert out.totals.success_rate == pytest.approx(12 / 14)
    engines = {e.engine_version: e.count for e in out.engine_usage}
    assert engines == {"0.32": 1, "0.25": 1}


async def test_product_coverage_disabled_returns_empty():
    svc = StatsService(client=None)
    out = await svc.product_coverage([uuid.uuid4()], "7d")
    assert out.enabled is False
    assert out.log_types == []


async def test_product_coverage_per_log_type_sparkline():
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    a, b = uuid.uuid4(), uuid.uuid4()
    client = MagicMock()
    client.query = AsyncMock(
        return_value=_query_result(
            [
                (a, yesterday, 4, 4),
                (a, today, 4, 2),
                (b, yesterday, 2, 0),
            ]
        )
    )
    svc = StatsService(client=client)
    out = await svc.product_coverage([a, b], "7d")
    assert out.enabled is True
    assert out.range_days == 7
    by_id = {lt.log_type_id: lt for lt in out.log_types}
    assert by_id[a].volume == 8
    assert by_id[a].success_rate_avg == pytest.approx(0.75)
    assert len(by_id[a].sparkline) == 7
    # yesterday at -2, today at -1
    assert by_id[a].sparkline[-2:] == [1.0, 0.5]
    assert by_id[b].volume == 2
    assert by_id[b].success_rate_avg == 0.0


def test_range_to_days_mapping():
    assert RANGE_TO_DAYS == {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
