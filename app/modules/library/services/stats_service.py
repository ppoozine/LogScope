"""Read-side: aggregate ClickHouse parse_events into Stats / Coverage DTOs."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from app.modules.library.schemas import (
    CoverageLogType,
    EngineUsage,
    EngineVersion,
    LogTypeStats,
    ProductCoverage,
    StatsRange,
    StatsTotals,
    TimelinePoint,
)

RANGE_TO_DAYS: dict[StatsRange, int] = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}


class StatsService:
    def __init__(self, client: Any | None) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def log_type_stats(self, log_type_id: uuid.UUID, range_: StatsRange) -> LogTypeStats:
        days = RANGE_TO_DAYS[range_]
        if not self.enabled or self._client is None:
            return LogTypeStats(
                enabled=False,
                range_days=days,
                timeline=[],
                engine_usage=[],
                totals=StatsTotals(total=0, success=0, error=0, success_rate=0.0),
            )
        result = await self._client.query(
            """
            SELECT toDate(ts) AS day,
                   sum(total)   AS total,
                   sum(success) AS success,
                   sum(error)   AS error,
                   engine_version
            FROM parse_events
            WHERE log_type_id = {lt:UUID}
              AND ts >= now() - INTERVAL {days:UInt16} DAY
            GROUP BY day, engine_version
            ORDER BY day
            """,
            parameters={"lt": log_type_id, "days": days},
        )
        return self._build_log_type_stats(result.result_rows, days)

    async def product_coverage(self, log_type_ids: list[uuid.UUID], range_: StatsRange) -> ProductCoverage:
        days = RANGE_TO_DAYS[range_]
        if not self.enabled or self._client is None or not log_type_ids:
            return ProductCoverage(enabled=self.enabled, range_days=days, log_types=[])
        result = await self._client.query(
            """
            SELECT log_type_id,
                   toDate(ts)   AS day,
                   sum(total)   AS total,
                   sum(success) AS success
            FROM parse_events
            WHERE log_type_id IN {ids:Array(UUID)}
              AND ts >= now() - INTERVAL {days:UInt16} DAY
            GROUP BY log_type_id, day
            ORDER BY log_type_id, day
            """,
            parameters={"ids": log_type_ids, "days": days},
        )
        return self._build_coverage(result.result_rows, log_type_ids, days)

    @staticmethod
    def _build_log_type_stats(rows: list[tuple], days: int) -> LogTypeStats:
        # day -> (total, success, error)
        per_day: dict[date, tuple[int, int, int]] = {}
        engines: dict[str, int] = {}
        for day, total, success, error, engine in rows:
            t, s, e = per_day.get(day, (0, 0, 0))
            per_day[day] = (t + int(total), s + int(success), e + int(error))
            engines[engine] = engines.get(engine, 0) + 1

        timeline = [
            TimelinePoint(
                day=d.isoformat(),
                total=t,
                success=s,
                error=e,
                success_rate=(s / t) if t else 0.0,
            )
            for d, (t, s, e) in sorted(per_day.items())
        ]
        total_sum = sum(t for t, _, _ in per_day.values())
        success_sum = sum(s for _, s, _ in per_day.values())
        error_sum = sum(e for _, _, e in per_day.values())
        return LogTypeStats(
            enabled=True,
            range_days=days,
            timeline=timeline,
            engine_usage=[EngineUsage(engine_version=cast("EngineVersion", k), count=v) for k, v in engines.items()],
            totals=StatsTotals(
                total=total_sum,
                success=success_sum,
                error=error_sum,
                success_rate=(success_sum / total_sum) if total_sum else 0.0,
            ),
        )

    @staticmethod
    def _build_coverage(rows: list[tuple], log_type_ids: list[uuid.UUID], days: int) -> ProductCoverage:
        # group rows by log_type_id, pre-sort dates ascending
        by_lt: dict[uuid.UUID, dict[date, tuple[int, int]]] = {lt: {} for lt in log_type_ids}
        for lt_id, day, total, success in rows:
            if lt_id in by_lt:
                by_lt[lt_id][day] = (int(total), int(success))

        today = datetime.now(UTC).date()
        window = [today - timedelta(days=days - 1 - i) for i in range(days)]

        out: list[CoverageLogType] = []
        for lt_id in log_type_ids:
            day_map = by_lt[lt_id]
            sparkline = []
            for d in window:
                t, s = day_map.get(d, (0, 0))
                sparkline.append((s / t) if t else 0.0)
            volume = sum(t for t, _ in day_map.values())
            successes = sum(s for _, s in day_map.values())
            avg = (successes / volume) if volume else 0.0
            out.append(
                CoverageLogType(
                    log_type_id=lt_id,
                    sparkline=sparkline,
                    success_rate_avg=avg,
                    volume=volume,
                )
            )
        return ProductCoverage(enabled=True, range_days=days, log_types=out)
