"""Fire-and-forget writer for parse stats.

Designed to be invoked from FastAPI BackgroundTasks. Never raises.
When the underlying ClickHouse client is None (CLICKHOUSE_URL unset),
record() is a no-op.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


_COLUMNS: tuple[str, ...] = (
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
)


@dataclass(frozen=True)
class ParseEvent:
    ts: datetime
    log_type_id: uuid.UUID | None
    parse_rule_id: uuid.UUID | None
    engine_version: str
    total: int
    success: int
    error: int
    latency_ms: int
    user_id: uuid.UUID | None
    raw_log_hash: bytes
    vrl_hash: bytes


def hash16(data: str) -> bytes:
    """blake2b-16: deterministic 16-byte hash for raw log / VRL identity."""
    return hashlib.blake2b(data.encode("utf-8"), digest_size=16).digest()


class StatsRecorder:
    def __init__(self, client: Any | None) -> None:
        self._client = client

    async def record(self, event: ParseEvent) -> None:
        if self._client is None:
            return
        try:
            await self._client.insert(
                "parse_events",
                [self._row(event)],
                column_names=list(_COLUMNS),
            )
        except Exception as exc:  # fire-and-forget by design, swallow all errors
            logger.warning("stats_record_failed", error=str(exc))

    @staticmethod
    def _row(event: ParseEvent) -> tuple:
        return (
            event.ts,
            event.log_type_id,
            event.parse_rule_id,
            event.engine_version,
            event.total,
            event.success,
            event.error,
            event.latency_ms,
            event.user_id,
            event.raw_log_hash,
            event.vrl_hash,
        )
