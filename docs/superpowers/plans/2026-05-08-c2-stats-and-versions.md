# C2 — Stats + Parse Rule Version History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 C1 known gaps 收尾：ClickHouse 寫入 parse 統計（BackgroundTasks，optional infra）、Library 顯示 coverage（sparkline + Stats tab）、Parse rule 三態（draft/published/archived）+ Versions tab + Promote 流程。

**Architecture:** ClickHouse 用 `clickhouse-connect` (HTTP) + FastAPI lifespan + `BackgroundTasks` fire-and-forget 寫入；CH 不可用時 silent no-op，不影響主流程。Parse rule 改三態，PG partial unique 保證每 log_type 同時最多一個 published；既有 `LogTypeService.publish()` 改用新的 `ParseRuleService.promote()` delegate，避免 race。前端用 recharts（Stats）+ react-diff-viewer-continued（Diff）+ 純 SVG sparkline（Library overview）。

**Tech Stack:**
- Backend: Python 3.13、FastAPI、SQLAlchemy 2.x async、Alembic、`clickhouse-connect`、pytest
- Frontend: Next.js（custom build — see `web/AGENTS.md`，**寫前端前先讀 `web/node_modules/next/dist/docs/`**）、TanStack Query、recharts、react-diff-viewer-continued、Vitest、Playwright
- Infra: docker-compose（ClickHouse profile=stats）、Alembic migration `0005`

**Spec:** `docs/superpowers/specs/2026-05-08-c2-stats-and-versions-design.md`

**重要：完成定義**
- 28 個 task 全 commit 在 `feat/c2-stats-and-versions` 分支
- `make lint && make test && make test-int && make test-fe && make test-fe-e2e` 全綠
- 手動 smoke：`docker compose --profile stats up -d` → `make migrate` → `make dev-all` → 在 Analyzer parse 幾次 → 看 Stats tab + sparkline + Versions tab 都正常

---

## Task 0: 建立 feature branch

**Files:**
- 無（git 操作）

- [ ] **Step 1: 從 main 建分支**

```bash
git checkout main
git pull
git checkout -b feat/c2-stats-and-versions
```

- [ ] **Step 2: 確認乾淨**

Run: `git status`
Expected: `nothing to commit, working tree clean`

---

## Task 1: 加 `clickhouse-connect` 依賴 + Settings + .env

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: 加依賴**

`pyproject.toml` 在 `[project].dependencies` 加一行：

```toml
"clickhouse-connect>=0.8",
```

- [ ] **Step 2: 加 Settings 欄位**

`app/core/config.py`，在 `llm_match_model` 之後加：

```python
clickhouse_url: str | None = Field(default=None, alias="CLICKHOUSE_URL")
```

- [ ] **Step 3: 加 .env.example 條目**

`.env.example` 末尾加：

```
# ClickHouse (optional — required for Stats / Coverage features)
# CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope
```

- [ ] **Step 4: sync deps + lint**

Run:
```bash
uv sync
uv run ruff check app/core/config.py
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock app/core/config.py .env.example
git commit -m "chore(c2): add clickhouse-connect dep and CLICKHOUSE_URL setting"
```

---

## Task 2: 加 docker-compose `clickhouse` service（profile=stats）

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 加 service**

在 `docker-compose.yml` 的 `services:` 之下、`volumes:` 之上插入：

```yaml
  clickhouse:
    image: clickhouse/clickhouse-server:25.1
    profiles: ["stats"]
    ports:
      - "8123:8123"
      - "9000:9000"
    environment:
      CLICKHOUSE_DB: logscope
      CLICKHOUSE_USER: logscope
      CLICKHOUSE_PASSWORD: logscope
    volumes:
      - chdata:/var/lib/clickhouse
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8123/ping"]
      interval: 5s
      timeout: 3s
      retries: 10
```

並在 `volumes:` 區段加 `chdata:`：

```yaml
volumes:
  pgdata:
  chdata:
```

- [ ] **Step 2: 啟動驗證**

Run:
```bash
docker compose --profile stats up -d clickhouse
docker compose ps
```
Expected: `clickhouse` 出現且 `healthy`

驗證可用：
```bash
curl -s http://logscope:logscope@localhost:8123/ping
```
Expected: `Ok.`

- [ ] **Step 3: 收掉**

```bash
docker compose --profile stats down
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(c2): add ClickHouse service to docker-compose under stats profile"
```

---

## Task 3: `app/core/clickhouse.py` — async client + lifespan

**Files:**
- Create: `app/core/clickhouse.py`
- Test: `tests/unit/core/test_clickhouse.py`

- [ ] **Step 1: 寫 failing test**

```python
# tests/unit/core/test_clickhouse.py
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
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/core/test_clickhouse.py -v`
Expected: ImportError or attribute errors

- [ ] **Step 3: 實作 clickhouse module**

```python
# app/core/clickhouse.py
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
```

- [ ] **Step 4: 暫時 stub `ensure_parse_events_table`**

```python
# app/core/clickhouse_schema.py
"""Schema bootstrap. Real DDL added in Task 4."""

from clickhouse_connect.driver.asyncclient import AsyncClient


async def ensure_parse_events_table(_client: AsyncClient) -> None:  # pragma: no cover
    pass
```

- [ ] **Step 5: Run test, expect PASS**

Run: `uv run pytest tests/unit/core/test_clickhouse.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add app/core/clickhouse.py app/core/clickhouse_schema.py tests/unit/core/test_clickhouse.py
git commit -m "feat(c2): add optional ClickHouse async client wrapper

silent no-op when CLICKHOUSE_URL unset; init/close hooks for lifespan"
```

---

## Task 4: ClickHouse schema bootstrap — `parse_events` 表

**Files:**
- Modify: `app/core/clickhouse_schema.py`
- Test: `tests/integration/core/test_clickhouse_schema.py`

- [ ] **Step 1: 寫 integration test**

```python
# tests/integration/core/test_clickhouse_schema.py
"""Real ClickHouse: schema bootstrap is idempotent and the table is shaped correctly."""

import os
import pytest
import clickhouse_connect

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
        "SELECT name FROM system.columns "
        "WHERE database = currentDatabase() AND table = 'parse_events'"
    )
    columns = {r[0] for r in rows.result_rows}
    assert columns == {
        "ts", "log_type_id", "parse_rule_id", "engine_version",
        "total", "success", "error", "latency_ms",
        "user_id", "raw_log_hash", "vrl_hash",
    }
```

- [ ] **Step 2: Run test (CH 必須跑著)**

Run:
```bash
docker compose --profile stats up -d clickhouse
CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope \
  uv run pytest tests/integration/core/test_clickhouse_schema.py -v
```
Expected: 3 failed (table not created)

- [ ] **Step 3: 實作 schema**

```python
# app/core/clickhouse_schema.py
"""ClickHouse schema bootstrap. Run once at app startup."""

from clickhouse_connect.driver.asyncclient import AsyncClient

PARSE_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS parse_events (
  ts             DateTime64(3, 'UTC'),
  log_type_id    Nullable(UUID),
  parse_rule_id  Nullable(UUID),
  engine_version LowCardinality(String),
  total          UInt32,
  success        UInt32,
  error          UInt32,
  latency_ms     UInt32,
  user_id        Nullable(UUID),
  raw_log_hash   FixedString(16),
  vrl_hash       FixedString(16)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (log_type_id, ts)
TTL toDateTime(ts) + INTERVAL 90 DAY
""".strip()


async def ensure_parse_events_table(client: AsyncClient) -> None:
    await client.command(PARSE_EVENTS_DDL)
```

- [ ] **Step 4: Run test again, expect PASS**

Run: same command as Step 2
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/core/clickhouse_schema.py tests/integration/core/test_clickhouse_schema.py
git commit -m "feat(c2): bootstrap parse_events ClickHouse table on startup

MergeTree partitioned by month, ordered by (log_type_id, ts), 90-day TTL"
```

---

## Task 5: 把 ClickHouse init/close 接進 lifespan

**Files:**
- Modify: `app/core/lifespan.py`
- Test: `tests/unit/core/test_lifespan_clickhouse.py`

- [ ] **Step 1: 寫 failing test**

```python
# tests/unit/core/test_lifespan_clickhouse.py
"""Lifespan should call init_clickhouse / close_clickhouse around yield."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from app.core.lifespan import lifespan


async def test_lifespan_initializes_and_closes_clickhouse():
    app = FastAPI()
    init_mock = AsyncMock()
    close_mock = AsyncMock()
    with (
        patch("app.core.lifespan.init_clickhouse", new=init_mock),
        patch("app.core.lifespan.close_clickhouse", new=close_mock),
        patch("app.core.lifespan.init_database") as init_db,
        patch("app.core.lifespan.init_cache") as init_cache,
    ):
        init_db.return_value.connect = AsyncMock()
        init_db.return_value.disconnect = AsyncMock()
        init_cache.return_value.connect = AsyncMock()
        init_cache.return_value.disconnect = AsyncMock()

        async with lifespan(app):
            init_mock.assert_awaited_once()
            close_mock.assert_not_awaited()
        close_mock.assert_awaited_once()
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/core/test_lifespan_clickhouse.py -v`
Expected: FAIL — init_clickhouse not in lifespan

- [ ] **Step 3: Wire into lifespan**

Replace `app/core/lifespan.py` body (preserve existing structure, just add CH calls):

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import init_cache
from app.core.clickhouse import close_clickhouse, init_clickhouse
from app.core.config import get_settings
from app.core.database import init_database
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    db = init_database(settings.database_url)
    cache = init_cache(settings.redis_url)
    await db.connect()
    await cache.connect()
    await init_clickhouse()
    try:
        yield
    finally:
        await close_clickhouse()
        await cache.disconnect()
        await db.disconnect()
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/core/test_lifespan_clickhouse.py -v`
Expected: PASS

- [ ] **Step 5: 確認 full unit suite 沒退化**

Run: `uv run pytest tests/unit -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/core/lifespan.py tests/unit/core/test_lifespan_clickhouse.py
git commit -m "feat(c2): wire ClickHouse init/close into FastAPI lifespan"
```

---

## Task 6: `StatsRecorder` service — fire-and-forget writer

**Files:**
- Create: `app/modules/analyzer/services/stats_recorder.py`
- Test: `tests/unit/modules/analyzer/test_stats_recorder.py`

- [ ] **Step 1: 寫 failing tests**

```python
# tests/unit/modules/analyzer/test_stats_recorder.py
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
    base = dict(
        ts=datetime(2026, 5, 8, tzinfo=UTC),
        log_type_id=uuid.uuid4(),
        parse_rule_id=uuid.uuid4(),
        engine_version="0.32",
        total=3,
        success=2,
        error=1,
        latency_ms=42,
        user_id=uuid.uuid4(),
        raw_log_hash=hash16("raw"),
        vrl_hash=hash16(".x = 1"),
    )
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
    args, kwargs = client.insert.await_args
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
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/analyzer/test_stats_recorder.py -v`
Expected: ImportError

- [ ] **Step 3: 實作 StatsRecorder**

```python
# app/modules/analyzer/services/stats_recorder.py
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
        except Exception as exc:  # noqa: BLE001 — fire-and-forget by design
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
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/analyzer/test_stats_recorder.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/modules/analyzer/services/stats_recorder.py tests/unit/modules/analyzer/test_stats_recorder.py
git commit -m "feat(c2): add StatsRecorder fire-and-forget writer

no-op when client is None, swallows CH errors with warning log"
```

---

## Task 7: 擴充 `ParseRequest` schema — 帶 log_type_id / parse_rule_id

**Files:**
- Modify: `app/modules/analyzer/schemas.py`
- Test: `tests/unit/modules/analyzer/test_parser_schema.py`

- [ ] **Step 1: 寫 failing test**

```python
# tests/unit/modules/analyzer/test_parser_schema.py
"""ParseRequest accepts optional log_type_id / parse_rule_id."""

import uuid

from app.modules.analyzer.schemas import ParseRequest


def test_parse_request_accepts_no_context():
    req = ParseRequest(vrl_code=".x = 1", logs=["a"], engine_version="0.32")
    assert req.log_type_id is None
    assert req.parse_rule_id is None


def test_parse_request_accepts_log_type_and_rule_ids():
    lt = uuid.uuid4()
    rule = uuid.uuid4()
    req = ParseRequest(
        vrl_code=".x = 1",
        logs=["a"],
        engine_version="0.32",
        log_type_id=lt,
        parse_rule_id=rule,
    )
    assert req.log_type_id == lt
    assert req.parse_rule_id == rule
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/analyzer/test_parser_schema.py -v`
Expected: FAIL (extra fields not allowed)

- [ ] **Step 3: 加欄位**

`app/modules/analyzer/schemas.py`，`ParseRequest` 改：

```python
class ParseRequest(BaseModel):
    vrl_code: str = Field(min_length=1)
    logs: list[str] = Field(max_length=500)
    engine_version: EngineVersion = "0.32"
    log_type_id: uuid.UUID | None = None
    parse_rule_id: uuid.UUID | None = None
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/analyzer/test_parser_schema.py -v`
Expected: 2 passed

- [ ] **Step 5: 確認 既有 router test 沒退化**

Run: `uv run pytest tests/unit/modules/analyzer/test_parse_router.py -v`
Expected: all pass

- [ ] **Step 6: 重新生 frontend openapi types**

Run:
```bash
make dev-be   # 開後端讓 /openapi.json 可拉
sleep 2
make gen-api
make stop-be
```
Expected: `web/lib/api/types.ts` 更新

- [ ] **Step 7: Commit**

```bash
git add app/modules/analyzer/schemas.py tests/unit/modules/analyzer/test_parser_schema.py web/lib/api/types.ts
git commit -m "feat(c2): allow log_type_id and parse_rule_id on ParseRequest

Analyzer can attach Library context for parse stats correlation"
```

---

## Task 8: 把 BackgroundTasks 寫 stats 接進 `parse_router`

**Files:**
- Modify: `app/modules/analyzer/routers/parse_router.py`
- Test: `tests/unit/modules/analyzer/test_parse_router.py`

- [ ] **Step 1: 加 failing test**

把以下測試加到 `test_parse_router.py` 的 `TestParseRoute` class：

```python
async def test_parse_schedules_stats_record(self, app: FastAPI, client: AsyncClient):
    """parse should schedule a StatsRecorder.record BackgroundTask."""
    from unittest.mock import AsyncMock, patch

    from app.modules.analyzer.routers import parse_router as pr

    app.dependency_overrides[current_user] = _user

    fake_recorder = AsyncMock()

    def _override_recorder():
        return fake_recorder

    app.dependency_overrides[pr.get_stats_recorder] = _override_recorder

    r = await client.post(
        "/api/v1/analyzer/parse",
        json={
            "vrl_code": '.action = "allow"\n.',
            "logs": ["one"],
            "engine_version": "0.32",
        },
    )
    assert r.status_code == 200
    # Background task runs after response; httpx ASGITransport awaits it.
    fake_recorder.record.assert_awaited_once()
    event = fake_recorder.record.await_args.args[0]
    assert event.engine_version == "0.32"
    assert event.total == 1 and event.success == 1
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/analyzer/test_parse_router.py::TestParseRoute::test_parse_schedules_stats_record -v`
Expected: FAIL — `get_stats_recorder` not defined

- [ ] **Step 3: 改 router 接 BackgroundTasks**

```python
# app/modules/analyzer/routers/parse_router.py
"""POST /api/v1/analyzer/parse — run a VRL program against raw logs."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.clickhouse import get_clickhouse
from app.core.config import Settings, get_settings
from app.modules.analyzer.schemas import (
    CheckRequest,
    CheckResponse,
    FixtureListResponse,
    MatchAvailabilityResponse,
    ParseRequest,
    ParseResponse,
)
from app.modules.analyzer.services import fixtures_service, parser_service
from app.modules.analyzer.services.stats_recorder import (
    ParseEvent,
    StatsRecorder,
    hash16,
)
from app.modules.auth.models.user import User

router = APIRouter()


def get_stats_recorder() -> StatsRecorder:
    """FastAPI dep: bind a StatsRecorder to the current ClickHouse client (or None)."""
    return StatsRecorder(client=get_clickhouse())


@router.post("/parse", response_model=DataResponse[ParseResponse])
async def parse(
    body: ParseRequest,
    background: BackgroundTasks,
    recorder: Annotated[StatsRecorder, Depends(get_stats_recorder)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseResponse]:
    started = perf_counter()
    response = parser_service.run(
        vrl=body.vrl_code,
        logs=body.logs,
        engine=body.engine_version,
    )
    latency_ms = int((perf_counter() - started) * 1000)

    summary = response.summary
    event = ParseEvent(
        ts=datetime.now(UTC),
        log_type_id=body.log_type_id,
        parse_rule_id=body.parse_rule_id,
        engine_version=body.engine_version,
        total=summary.total if summary else 0,
        success=summary.success if summary else 0,
        error=summary.error if summary else 0,
        latency_ms=latency_ms,
        user_id=user.id,
        raw_log_hash=hash16(body.logs[0] if body.logs else ""),
        vrl_hash=hash16(body.vrl_code),
    )
    background.add_task(recorder.record, event)
    return DataResponse(data=response)
```

（其他 endpoints 不動）

- [ ] **Step 4: Run new test, expect PASS**

Run: `uv run pytest tests/unit/modules/analyzer/test_parse_router.py -v`
Expected: all pass (including new `test_parse_schedules_stats_record`)

- [ ] **Step 5: Commit**

```bash
git add app/modules/analyzer/routers/parse_router.py tests/unit/modules/analyzer/test_parse_router.py
git commit -m "feat(c2): record parse events to ClickHouse via BackgroundTasks

fire-and-forget after response sent; no impact on parse hot path"
```

---

## Task 9: Stats schemas（library）— 回應 DTOs

**Files:**
- Modify: `app/modules/library/schemas.py`

- [ ] **Step 1: 加 schemas（無 test，純資料結構，後續 service test 會涵蓋）**

在 `app/modules/library/schemas.py` 末尾加：

```python
# =============================================================================
# Stats / Coverage
# =============================================================================

StatsRange = Literal["7d", "14d", "30d", "90d"]


class StatsRangeQuery(BaseModel):
    range: StatsRange = "7d"


class TimelinePoint(BaseModel):
    day: str  # YYYY-MM-DD
    total: int
    success: int
    error: int
    success_rate: float  # 0..1


class EngineUsage(BaseModel):
    engine_version: EngineVersion
    count: int


class StatsTotals(BaseModel):
    total: int
    success: int
    error: int
    success_rate: float


class LogTypeStats(BaseModel):
    enabled: bool
    range_days: int
    timeline: list[TimelinePoint]
    engine_usage: list[EngineUsage]
    totals: StatsTotals


class CoverageLogType(BaseModel):
    log_type_id: uuid.UUID
    sparkline: list[float]
    success_rate_avg: float
    volume: int


class ProductCoverage(BaseModel):
    enabled: bool
    range_days: int
    log_types: list[CoverageLogType]
```

- [ ] **Step 2: 確認 lint**

Run: `uv run ruff check app/modules/library/schemas.py && uv run pyright`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add app/modules/library/schemas.py
git commit -m "feat(c2): add Stats and Coverage Pydantic schemas"
```

---

## Task 10: `StatsService` — 讀 CH 算 timeline / coverage

**Files:**
- Create: `app/modules/library/services/stats_service.py`
- Test: `tests/unit/modules/library/test_stats_service.py`

- [ ] **Step 1: 寫 failing tests**

```python
# tests/unit/modules/library/test_stats_service.py
"""Unit tests for StatsService — uses mocked CH client."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.library.services.stats_service import StatsService, RANGE_TO_DAYS


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
    a, b = uuid.uuid4(), uuid.uuid4()
    client = MagicMock()
    # Three rows: a/day1 (rate=1.0), a/day2 (rate=0.5), b/day1 (rate=0.0)
    client.query = AsyncMock(
        return_value=_query_result(
            [
                (a, date(2026, 5, 7), 4, 4),
                (a, date(2026, 5, 8), 4, 2),
                (b, date(2026, 5, 7), 2, 0),
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
    # Last 2 entries non-zero (most recent days), earlier are 0 fillers.
    assert by_id[a].sparkline[-2:] == [1.0, 0.5]
    assert by_id[b].volume == 2
    assert by_id[b].success_rate_avg == 0.0


def test_range_to_days_mapping():
    assert RANGE_TO_DAYS == {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/library/test_stats_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作 StatsService**

```python
# app/modules/library/services/stats_service.py
"""Read-side: aggregate ClickHouse parse_events into Stats / Coverage DTOs."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.modules.library.schemas import (
    CoverageLogType,
    EngineUsage,
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

    async def log_type_stats(
        self, log_type_id: uuid.UUID, range_: StatsRange
    ) -> LogTypeStats:
        days = RANGE_TO_DAYS[range_]
        if not self.enabled:
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

    async def product_coverage(
        self, log_type_ids: list[uuid.UUID], range_: StatsRange
    ) -> ProductCoverage:
        days = RANGE_TO_DAYS[range_]
        if not self.enabled or not log_type_ids:
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
            engine_usage=[EngineUsage(engine_version=k, count=v) for k, v in engines.items()],
            totals=StatsTotals(
                total=total_sum,
                success=success_sum,
                error=error_sum,
                success_rate=(success_sum / total_sum) if total_sum else 0.0,
            ),
        )

    @staticmethod
    def _build_coverage(
        rows: list[tuple], log_type_ids: list[uuid.UUID], days: int
    ) -> ProductCoverage:
        # group rows by log_type_id, pre-sort dates ascending
        by_lt: dict[uuid.UUID, dict[date, tuple[int, int]]] = {
            lt: {} for lt in log_type_ids
        }
        for lt_id, day, total, success in rows:
            if lt_id in by_lt:
                by_lt[lt_id][day] = (int(total), int(success))

        today = datetime.now(timezone.utc).date()
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
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/library/test_stats_service.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/modules/library/services/stats_service.py tests/unit/modules/library/test_stats_service.py
git commit -m "feat(c2): add StatsService for ClickHouse-backed stats and coverage queries"
```

---

## Task 11: Stats router — `/log_types/{id}/stats` + `/products/.../coverage`

**Files:**
- Create: `app/modules/library/routers/stats_router.py`
- Modify: `app/api/v1/__init__.py`
- Test: `tests/unit/modules/library/test_stats_router.py`

- [ ] **Step 1: 寫 failing test**

```python
# tests/unit/modules/library/test_stats_router.py
"""Router tests for /library/log_types/{id}/stats and /library/products/.../coverage."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.routers import stats_router as sr
from app.modules.library.schemas import (
    CoverageLogType,
    LogTypeStats,
    ProductCoverage,
    StatsTotals,
)


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestLogTypeStatsRoute:
    async def test_returns_disabled_when_clickhouse_off(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.log_type_stats = AsyncMock(
            return_value=LogTypeStats(
                enabled=False,
                range_days=7,
                timeline=[],
                engine_usage=[],
                totals=StatsTotals(total=0, success=0, error=0, success_rate=0.0),
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["enabled"] is False
        assert body["range_days"] == 7

    async def test_invalid_range_returns_422(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user
        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats?range=bad")
        assert r.status_code == 422

    async def test_passes_range_to_service(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.log_type_stats = AsyncMock(
            return_value=LogTypeStats(
                enabled=True,
                range_days=14,
                timeline=[],
                engine_usage=[],
                totals=StatsTotals(total=0, success=0, error=0, success_rate=0.0),
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats?range=14d")
        assert r.status_code == 200
        fake_service.log_type_stats.assert_awaited_once()
        assert fake_service.log_type_stats.await_args.args[1] == "14d"


class TestProductCoverageRoute:
    async def test_routes_through_pg_then_ch(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_lt_repo = AsyncMock()
        ids = [uuid.uuid4(), uuid.uuid4()]
        fake_lt_repo.list_ids_for_vendor_product = AsyncMock(return_value=ids)
        app.dependency_overrides[sr.get_log_type_repository] = lambda: fake_lt_repo

        fake_service = AsyncMock()
        fake_service.product_coverage = AsyncMock(
            return_value=ProductCoverage(
                enabled=True,
                range_days=7,
                log_types=[
                    CoverageLogType(
                        log_type_id=ids[0], sparkline=[0.0] * 7, success_rate_avg=0.0, volume=0
                    ),
                    CoverageLogType(
                        log_type_id=ids[1], sparkline=[0.0] * 7, success_rate_avg=0.0, volume=0
                    ),
                ],
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        r = await client.get("/api/v1/library/products/v1/p1/coverage")
        assert r.status_code == 200
        body = r.json()["data"]
        assert len(body["log_types"]) == 2
        fake_lt_repo.list_ids_for_vendor_product.assert_awaited_once_with("v1", "p1")
        fake_service.product_coverage.assert_awaited_once()
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/library/test_stats_router.py -v`
Expected: ImportError

- [ ] **Step 3: 加 LogTypeRepository 方法（PG 拿 vendor/product 下的 ids）**

`app/modules/library/repositories/log_type_repository.py` 末尾加：

```python
async def list_ids_for_vendor_product(
    self, vendor_slug: str, product_slug: str
) -> list[uuid.UUID]:
    """Return all log_type ids under vendor/product (any status)."""
    from app.modules.library.models.product import Product
    from app.modules.library.models.vendor import Vendor

    stmt = (
        select(LogType.id)
        .join(Product, Product.id == LogType.product_id)
        .join(Vendor, Vendor.id == Product.vendor_id)
        .where(Vendor.slug == vendor_slug, Product.slug == product_slug)
    )
    result = await self._session.execute(stmt)
    return [row[0] for row in result.all()]
```

（如果 file 沒有 `from sqlalchemy import select`，加 import）

- [ ] **Step 4: 實作 stats_router**

```python
# app/modules/library/routers/stats_router.py
"""GET stats / coverage — backed by ClickHouse via StatsService."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.clickhouse import get_clickhouse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import LogTypeStats, ProductCoverage, StatsRange
from app.modules.library.services.stats_service import StatsService

router = APIRouter()


def get_stats_service() -> StatsService:
    return StatsService(client=get_clickhouse())


async def get_log_type_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogTypeRepository:
    return LogTypeRepository(session)


@router.get(
    "/log_types/{log_type_id}/stats",
    response_model=DataResponse[LogTypeStats],
)
async def log_type_stats(
    log_type_id: uuid.UUID,
    service: Annotated[StatsService, Depends(get_stats_service)],
    _user: Annotated[User, Depends(current_user)],
    range_: Annotated[StatsRange, Query(alias="range")] = "7d",
) -> DataResponse[LogTypeStats]:
    stats = await service.log_type_stats(log_type_id, range_)
    return DataResponse(data=stats)


@router.get(
    "/products/{vendor_slug}/{product_slug}/coverage",
    response_model=DataResponse[ProductCoverage],
)
async def product_coverage(
    vendor_slug: str,
    product_slug: str,
    repo: Annotated[LogTypeRepository, Depends(get_log_type_repository)],
    service: Annotated[StatsService, Depends(get_stats_service)],
    _user: Annotated[User, Depends(current_user)],
    range_: Annotated[StatsRange, Query(alias="range")] = "7d",
) -> DataResponse[ProductCoverage]:
    ids = await repo.list_ids_for_vendor_product(vendor_slug, product_slug)
    coverage = await service.product_coverage(ids, range_)
    return DataResponse(data=coverage)
```

- [ ] **Step 5: 註冊 router**

`app/api/v1/__init__.py`：

```python
from app.modules.library.routers.stats_router import router as library_stats_router

# ...既有 includes...
router.include_router(library_stats_router, prefix="/library", tags=["library:stats"])
```

- [ ] **Step 6: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/library/test_stats_router.py -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add app/modules/library/routers/stats_router.py \
        app/modules/library/repositories/log_type_repository.py \
        app/api/v1/__init__.py \
        tests/unit/modules/library/test_stats_router.py
git commit -m "feat(c2): add /log_types/{id}/stats and /products/{v}/{p}/coverage endpoints"
```

---

## Task 12: ClickHouse integration test — write 一筆 → 讀回對得上

**Files:**
- Create: `tests/integration/modules/analyzer/test_stats_recorder.py`

- [ ] **Step 1: 寫 integration test**

```python
# tests/integration/modules/analyzer/test_stats_recorder.py
"""Real ClickHouse round-trip for StatsRecorder + ensure_schema."""

import os
import uuid
from datetime import UTC, datetime

import pytest
import clickhouse_connect

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
```

- [ ] **Step 2: Run test, expect PASS**

Run:
```bash
docker compose --profile stats up -d clickhouse
CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope \
  uv run pytest tests/integration/modules/analyzer/test_stats_recorder.py -v
```
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add tests/integration/modules/analyzer/test_stats_recorder.py tests/integration/modules/analyzer/__init__.py
git commit -m "test(c2): integration test for StatsRecorder round-trip with real ClickHouse"
```

> 注意：如果 `tests/integration/modules/analyzer/__init__.py` 不存在，建立空檔。

---

## Task 13: Alembic migration 0005 — parse_rule archived 三態 + partial unique

**Files:**
- Create: `app/alembic/versions/0005_parse_rule_archived_status.py`

- [ ] **Step 1: 產 migration 檔（手寫，不用 autogen）**

Run:
```bash
ls app/alembic/versions/
```
Expected: 0001-0004 出現

建立 `app/alembic/versions/0005_parse_rule_archived_status.py`：

```python
"""parse_rule archived status + partial unique on published

Revision ID: 0005_parse_rule_archived_status
Revises: 0004_drop_product_category
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_parse_rule_archived_status"
down_revision: str | None = "0004_drop_product_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. drop 既有 status check（如有）
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )

    # 2. 既有資料整理：每個 log_type 留最新 published 一筆，其餘 published → archived
    op.execute(
        """
        WITH ranked AS (
          SELECT id,
                 ROW_NUMBER() OVER (
                   PARTITION BY log_type_id ORDER BY version DESC
                 ) AS rn
          FROM parse_rules
          WHERE status = 'published'
        )
        UPDATE parse_rules SET status = 'archived'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    # 3. 加新的 status check
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published', 'archived')",
    )

    # 4. partial unique：每 log_type 最多一個 published
    op.create_index(
        "uq_parse_rules_one_published_per_log_type",
        "parse_rules",
        ["log_type_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("uq_parse_rules_one_published_per_log_type", table_name="parse_rules")
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    # 把 archived 全部還原成 published（不一定保證 partial unique，但 downgrade 不再有 partial unique）
    op.execute("UPDATE parse_rules SET status = 'published' WHERE status = 'archived'")
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published')",
    )
```

- [ ] **Step 2: 驗證 migration 跑得起來**

Run:
```bash
make up
make migrate
```
Expected: `0005_parse_rule_archived_status` 成功 apply（看 alembic 輸出）

- [ ] **Step 3: 驗證 partial unique 真的擋雙重 published（手動驗證）**

Run:
```bash
docker exec -i logscope-postgres-1 psql -U logscope -d logscope <<'SQL'
\d+ parse_rules
SQL
```
Expected: 看到 `uq_parse_rules_one_published_per_log_type` partial index、status check 含 archived

- [ ] **Step 4: Commit**

```bash
git add app/alembic/versions/0005_parse_rule_archived_status.py
git commit -m "feat(c2): migration 0005 — parse_rule archived state + partial unique on published"
```

---

## Task 14: ParseRuleStatus literal 加 archived

**Files:**
- Modify: `app/modules/library/schemas.py`

- [ ] **Step 1: 改 literal**

`app/modules/library/schemas.py` 找到：

```python
ParseRuleStatus = Literal["draft", "published"]
```

改成：

```python
ParseRuleStatus = Literal["draft", "published", "archived"]
```

- [ ] **Step 2: 確認 lint + typecheck**

Run: `uv run ruff check . && uv run pyright`
Expected: no errors

- [ ] **Step 3: 重新生 frontend openapi types**

Run:
```bash
make dev-be
sleep 2
make gen-api
make stop-be
```
Expected: `web/lib/api/types.ts` 中 ParseRuleRead.status 變成 `"draft" | "published" | "archived"`

- [ ] **Step 4: Commit**

```bash
git add app/modules/library/schemas.py web/lib/api/types.ts
git commit -m "feat(c2): add archived to ParseRuleStatus literal"
```

---

## Task 15: ParseRuleRepository — `get_for_update` + `get_current_published`

**Files:**
- Modify: `app/modules/library/repositories/parse_rule_repository.py`
- Test: `tests/integration/modules/library/test_parse_rule_repository.py` (new file)

- [ ] **Step 1: 寫 integration test（用真 PG）**

```python
# tests/integration/modules/library/test_parse_rule_repository.py
"""Integration test for new repository helpers."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository

pytestmark = pytest.mark.integration


async def _seed_log_type(session: AsyncSession) -> LogType:
    unique = uuid.uuid4().hex[:8]
    vendor = Vendor()
    vendor.id = uuid.uuid4()
    vendor.name = f"V {unique}"
    vendor.slug = f"v-{unique}"
    session.add(vendor)
    product = Product()
    product.id = uuid.uuid4()
    product.vendor_id = vendor.id
    product.name = "P"
    product.slug = "p"
    session.add(product)
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product.id
    lt.name = "LT"
    lt.slug = "lt"
    lt.format = "csv"
    session.add(lt)
    await session.flush()
    return lt


async def test_get_current_published_returns_none_when_no_published(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    rule = ParseRule()
    rule.log_type_id = lt.id
    rule.version = 1
    rule.vrl_code = "."
    rule.engine_version = "0.32"
    rule.status = "draft"
    db_session.add(rule)
    await db_session.flush()

    assert await repo.get_current_published(lt.id) is None


async def test_get_current_published_returns_published(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    pub = ParseRule()
    pub.log_type_id = lt.id
    pub.version = 1
    pub.vrl_code = "."
    pub.engine_version = "0.32"
    pub.status = "published"
    db_session.add(pub)
    await db_session.flush()

    found = await repo.get_current_published(lt.id)
    assert found is not None and found.id == pub.id


async def test_get_for_update_locks_row(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    rule = ParseRule()
    rule.log_type_id = lt.id
    rule.version = 1
    rule.vrl_code = "."
    rule.engine_version = "0.32"
    rule.status = "draft"
    db_session.add(rule)
    await db_session.flush()

    locked = await repo.get_for_update(rule.id)
    assert locked is not None and locked.id == rule.id
```

> **Note:** 此測試需要 `db_session` fixture。如果 `tests/integration/conftest.py` 沒有，請先在 Task 15 之前加：

```python
# tests/integration/conftest.py — 加在末尾
@pytest.fixture
async def db_session():
    """Yield a transactional AsyncSession that rolls back after each test."""
    from app.core.config import get_settings
    from app.core.database import init_database

    db = init_database(get_settings().database_url)
    await db.connect()
    try:
        async with db.session() as session:
            async with session.begin():
                yield session
                await session.rollback()
    finally:
        await db.disconnect()
```

> 若已有同名 fixture，沿用既有實作即可。

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/integration/modules/library/test_parse_rule_repository.py -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: 加 repository 方法**

`app/modules/library/repositories/parse_rule_repository.py` 末尾加：

```python
async def get_for_update(self, rule_id: uuid.UUID) -> ParseRule | None:
    """SELECT ... FOR UPDATE — locks the row in current transaction."""
    stmt = select(ParseRule).where(ParseRule.id == rule_id).with_for_update()
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()


async def get_current_published(self, log_type_id: uuid.UUID) -> ParseRule | None:
    stmt = select(ParseRule).where(
        ParseRule.log_type_id == log_type_id,
        ParseRule.status == "published",
    )
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/integration/modules/library/test_parse_rule_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/modules/library/repositories/parse_rule_repository.py \
        tests/integration/modules/library/test_parse_rule_repository.py \
        tests/integration/conftest.py
git commit -m "feat(c2): add get_for_update and get_current_published to ParseRuleRepository"
```

---

## Task 16: `ParseRuleService.promote()` — 三態切換

**Files:**
- Modify: `app/modules/library/services/parse_rule_service.py`
- Test: `tests/unit/modules/library/test_parse_rule_service_promote.py`

- [ ] **Step 1: 寫 failing tests**

```python
# tests/unit/modules/library/test_parse_rule_service_promote.py
"""Unit tests for ParseRuleService.promote() — covers 4 state transitions."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.services.parse_rule_service import ParseRuleService


def _rule(*, status: str, log_type_id=None, rid=None) -> ParseRule:
    r = ParseRule()
    r.id = rid or uuid.uuid4()
    r.log_type_id = log_type_id or uuid.uuid4()
    r.version = 1
    r.vrl_code = "."
    r.engine_version = "0.32"
    r.status = status
    return r


def _log_type(rule_id) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
    lt.name = "LT"
    lt.slug = "lt"
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = rule_id
    return lt


async def test_promote_not_found_raises():
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=None)
    log_types_repo = AsyncMock()
    svc = ParseRuleService(rules_repo, log_types_repo)
    with pytest.raises(NotFoundError):
        await svc.promote(uuid.uuid4())


async def test_promote_archived_raises_conflict():
    target = _rule(status="archived")
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    svc = ParseRuleService(rules_repo, AsyncMock())
    with pytest.raises(ConflictError):
        await svc.promote(target.id)


async def test_promote_already_published_returns_idempotent():
    target = _rule(status="published")
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    svc = ParseRuleService(rules_repo, AsyncMock())
    out = await svc.promote(target.id)
    assert out is target
    rules_repo.update.assert_not_awaited()


async def test_promote_draft_with_no_existing_published_sets_log_type():
    lt_id = uuid.uuid4()
    target = _rule(status="draft", log_type_id=lt_id)
    lt = _log_type(rule_id=target.id)
    lt.id = lt_id

    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    rules_repo.get_current_published = AsyncMock(return_value=None)

    log_types_repo = AsyncMock()
    log_types_repo.get_by_id = AsyncMock(return_value=lt)

    svc = ParseRuleService(rules_repo, log_types_repo)
    out = await svc.promote(target.id)

    assert out.status == "published"
    rules_repo.update.assert_awaited_once_with(target)
    assert lt.current_parse_rule_id == target.id
    assert lt.status == "published"
    assert lt.published_at is not None
    log_types_repo.update.assert_awaited_once_with(lt)


async def test_promote_draft_archives_previous_published():
    lt_id = uuid.uuid4()
    target = _rule(status="draft", log_type_id=lt_id)
    old = _rule(status="published", log_type_id=lt_id)
    lt = _log_type(rule_id=target.id)
    lt.id = lt_id
    lt.status = "published"

    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    rules_repo.get_current_published = AsyncMock(return_value=old)

    log_types_repo = AsyncMock()
    log_types_repo.get_by_id = AsyncMock(return_value=lt)

    svc = ParseRuleService(rules_repo, log_types_repo)
    out = await svc.promote(target.id)

    assert out.status == "published"
    assert old.status == "archived"
    # both updates called: archive old and publish target
    assert rules_repo.update.await_count == 2
    assert lt.current_parse_rule_id == target.id
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_service_promote.py -v`
Expected: FAIL — `promote` 方法不存在

- [ ] **Step 3: 加 promote() 方法**

`app/modules/library/services/parse_rule_service.py`，類別末尾加：

```python
from datetime import UTC, datetime

# ... existing imports ...

    async def promote(self, rule_id: uuid.UUID) -> ParseRule:
        """Make `rule_id` the published rule for its log_type.

        Idempotent for already-published rules. Archives any prior published rule
        on the same log_type. Refuses to promote archived rules.
        """
        rule = await self._rules.get_for_update(rule_id)
        if rule is None:
            raise NotFoundError(f"parse rule not found: {rule_id}")
        if rule.status == "archived":
            raise ConflictError("cannot promote archived rule")
        if rule.status == "published":
            return rule

        previous = await self._rules.get_current_published(rule.log_type_id)
        if previous is not None and previous.id != rule.id:
            previous.status = "archived"
            await self._rules.update(previous)

        rule.status = "published"
        await self._rules.update(rule)

        log_type = await self._log_types.get_by_id(rule.log_type_id)
        if log_type is not None:
            log_type.current_parse_rule_id = rule.id
            log_type.status = "published"
            log_type.published_at = datetime.now(UTC)
            await self._log_types.update(log_type)

        return rule
```

> 注意：`from datetime import UTC, datetime` 加到 file imports。

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_service_promote.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/modules/library/services/parse_rule_service.py tests/unit/modules/library/test_parse_rule_service_promote.py
git commit -m "feat(c2): add ParseRuleService.promote() with three-state semantics

draft -> published, archives prior published rule for same log_type,
idempotent for already-published, rejects archived rules"
```

---

## Task 17: 改 `LogTypeService.publish()` delegate 給 promote()

**Files:**
- Modify: `app/modules/library/services/log_type_service.py`
- Test: 既有的 `tests/integration/modules/library/test_library_flow.py`（不改）+ 新測試

- [ ] **Step 1: 加 unit test 確認新行為**

新建 `tests/unit/modules/library/test_log_type_service_publish.py`：

```python
"""LogTypeService.publish() should now delegate to ParseRuleService.promote()."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.common.exceptions import ValidationError
from app.modules.library.models.log_type import LogType
from app.modules.library.services.log_type_service import LogTypeService


def _log_type(*, current_rule_id) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
    lt.name = "LT"
    lt.slug = "lt"
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = current_rule_id
    return lt


async def test_publish_no_current_rule_raises():
    log_types = AsyncMock()
    log_types.get_by_id = AsyncMock(return_value=_log_type(current_rule_id=None))
    svc = LogTypeService(log_types, AsyncMock(), AsyncMock())
    with pytest.raises(ValidationError):
        await svc.publish(uuid.uuid4())


async def test_publish_calls_parse_rule_service_promote(monkeypatch):
    rule_id = uuid.uuid4()
    lt = _log_type(current_rule_id=rule_id)

    log_types = AsyncMock()
    log_types.get_by_id = AsyncMock(return_value=lt)

    rules = AsyncMock()
    promote_mock = AsyncMock()
    monkeypatch.setattr(
        "app.modules.library.services.log_type_service.ParseRuleService",
        lambda *a, **kw: type("S", (), {"promote": promote_mock})(),
    )

    products = AsyncMock()
    svc = LogTypeService(log_types, products, rules)
    await svc.publish(lt.id)
    promote_mock.assert_awaited_once_with(rule_id)
```

- [ ] **Step 2: Run new test, expect FAIL**

Run: `uv run pytest tests/unit/modules/library/test_log_type_service_publish.py -v`
Expected: FAIL — publish 還沒 delegate

- [ ] **Step 3: 改 publish() 實作**

`app/modules/library/services/log_type_service.py` 改 `publish` 方法：

```python
async def publish(self, log_type_id: uuid.UUID) -> LogType:
    """Promote current draft parse rule to published.

    Delegates to ParseRuleService.promote() so all promotion paths share
    the same archive-and-publish semantics required by the partial unique.
    """
    log_type = await self.get_by_id(log_type_id)
    if log_type.current_parse_rule_id is None:
        raise ValidationError("no parse rule to publish")

    # late import to avoid circular dep
    from app.modules.library.services.parse_rule_service import ParseRuleService

    parse_rule_service = ParseRuleService(self._parse_rules, self._log_types)
    await parse_rule_service.promote(log_type.current_parse_rule_id)

    # promote() already updated log_type via repo, but the in-memory copy here
    # could be stale; re-fetch to return fresh state.
    refreshed = await self._log_types.get_by_id(log_type_id)
    assert refreshed is not None
    return refreshed
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/library/test_log_type_service_publish.py -v`
Expected: 2 passed

- [ ] **Step 5: 確認既有 integration flow 沒退化**

Run:
```bash
make up
make migrate
uv run pytest tests/integration/modules/library/test_library_flow.py -v
```
Expected: all pass（包括既有的 `test_full_flow` publish 步驟）

- [ ] **Step 6: Commit**

```bash
git add app/modules/library/services/log_type_service.py tests/unit/modules/library/test_log_type_service_publish.py
git commit -m "refactor(c2): LogTypeService.publish delegates to ParseRuleService.promote

ensures partial unique invariant by sharing the archive-and-publish path"
```

---

## Task 18: `POST /parse_rules/{id}/promote` endpoint

**Files:**
- Modify: `app/modules/library/routers/parse_rule_router.py`
- Test: `tests/unit/modules/library/test_parse_rule_router_promote.py`

- [ ] **Step 1: 寫 failing test**

```python
# tests/unit/modules/library/test_parse_rule_router_promote.py
"""Router test for POST /api/v1/library/parse_rules/{id}/promote."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.common.exceptions import ConflictError, NotFoundError
from app.modules.auth.models.user import User
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.routers import parse_rule_router as prr


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _rule(status: str = "published") -> ParseRule:
    r = ParseRule()
    r.id = uuid.uuid4()
    r.log_type_id = uuid.uuid4()
    r.version = 2
    r.vrl_code = "."
    r.engine_version = "0.32"
    r.status = status
    r.created_at = datetime.now(UTC)
    r.updated_at = datetime.now(UTC)
    return r


class TestPromoteRoute:
    async def test_promote_success_returns_published_rule(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(return_value=_rule(status="published"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["status"] == "published"

    async def test_promote_archived_returns_409(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(side_effect=ConflictError("archived"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 409

    async def test_promote_unknown_returns_404(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.promote = AsyncMock(side_effect=NotFoundError("nope"))
        app.dependency_overrides[prr.get_parse_rule_service] = lambda: fake_service

        r = await client.post(f"/api/v1/library/parse_rules/{uuid.uuid4()}/promote")
        assert r.status_code == 404
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_router_promote.py -v`
Expected: FAIL — endpoint 不存在

- [ ] **Step 3: 加 endpoint**

`app/modules/library/routers/parse_rule_router.py`，在 file 末尾加：

```python
@router.post(
    "/parse_rules/{rule_id}/promote",
    response_model=DataResponse[ParseRuleRead],
)
async def promote_parse_rule(
    rule_id: uuid.UUID,
    service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseRuleRead]:
    rule = await service.promote(rule_id)
    return DataResponse(data=ParseRuleRead.model_validate(rule))
```

> 確保 file 已經有 `get_parse_rule_service` factory（看起來 router 自己定義一個，沿用既有的）。

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_router_promote.py -v`
Expected: 3 passed

- [ ] **Step 5: 重新生 frontend types**

Run:
```bash
make dev-be
sleep 2
make gen-api
make stop-be
```

- [ ] **Step 6: Commit**

```bash
git add app/modules/library/routers/parse_rule_router.py \
        tests/unit/modules/library/test_parse_rule_router_promote.py \
        web/lib/api/types.ts
git commit -m "feat(c2): add POST /library/parse_rules/{id}/promote endpoint"
```

---

## Task 19: Integration test — Promote race / partial unique

**Files:**
- Create: `tests/integration/modules/library/test_promote_race.py`

- [ ] **Step 1: 寫 integration test**

```python
# tests/integration/modules/library/test_promote_race.py
"""Real PG: partial unique blocks two simultaneous publishes for the same log_type."""

import asyncio
import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.common.exceptions import ConflictError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.services.parse_rule_service import ParseRuleService

pytestmark = pytest.mark.integration


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return client


async def test_two_drafts_promote_simultaneously_only_one_wins(authenticated_client: AsyncClient):
    """Force partial unique conflict by manually inserting an extra draft row at status=published."""
    unique = uuid.uuid4().hex[:8]

    # Build a log_type with two drafts via API
    r = await authenticated_client.post(
        "/api/v1/library/vendors", json={"name": f"VR {unique}", "slug": f"vr-{unique}"}
    )
    assert r.status_code == 201
    vendor = r.json()["data"]
    r = await authenticated_client.post(
        f"/api/v1/library/vendors/vr-{unique}/products", json={"name": "P", "slug": "p"}
    )
    assert r.status_code == 201
    product = r.json()["data"]
    r = await authenticated_client.post(
        f"/api/v1/library/products/{product['id']}/log_types",
        json={"name": "LT", "slug": "lt", "format": "csv"},
    )
    assert r.status_code == 201
    lt = r.json()["data"]

    # First draft
    r = await authenticated_client.post(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules",
        json={"vrl_code": ".x = 1", "engine_version": "0.32"},
    )
    assert r.status_code == 201
    draft_a = r.json()["data"]

    # Promote first draft → success, becomes published
    r = await authenticated_client.post(
        f"/api/v1/library/parse_rules/{draft_a['id']}/promote"
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "published"

    # Second draft (creating another draft should NOT auto-publish)
    r = await authenticated_client.post(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules",
        json={"vrl_code": ".x = 2", "engine_version": "0.32"},
    )
    assert r.status_code == 201
    draft_b = r.json()["data"]

    # Promote second draft → success, draft_a auto-archived
    r = await authenticated_client.post(
        f"/api/v1/library/parse_rules/{draft_b['id']}/promote"
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "published"

    # Confirm draft_a is archived
    r = await authenticated_client.get(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules"
    )
    rules = {x["id"]: x["status"] for x in r.json()["data"]}
    assert rules[draft_a["id"]] == "archived"
    assert rules[draft_b["id"]] == "published"

    # Cleanup
    await authenticated_client.delete(f"/api/v1/library/log_types/{lt['id']}")
    await authenticated_client.delete(f"/api/v1/library/products/{product['id']}")
    await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")
```

- [ ] **Step 2: Run test**

Run:
```bash
make up
make migrate
uv run pytest tests/integration/modules/library/test_promote_race.py -v
```
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add tests/integration/modules/library/test_promote_race.py
git commit -m "test(c2): integration test for promote archive-and-publish behavior"
```

---

## Task 20: Frontend deps — recharts + react-diff-viewer-continued

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 安裝**

Run:
```bash
cd web && npm install recharts@^2.13 react-diff-viewer-continued@^4 && cd ..
```

- [ ] **Step 2: 確認安裝沒破壞**

Run: `cd web && npx tsc --noEmit && cd ..`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/package.json web/package-lock.json
git commit -m "chore(c2): add recharts and react-diff-viewer-continued deps"
```

---

## Task 21: `<CoverageSparkline>` — 純 SVG 元件

**Files:**
- Create: `web/components/library/coverage-sparkline.tsx`
- Test: `web/components/library/__tests__/coverage-sparkline.test.tsx`

- [ ] **Step 1: 寫 failing test**

```tsx
// web/components/library/__tests__/coverage-sparkline.test.tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CoverageSparkline } from "../coverage-sparkline";

describe("CoverageSparkline", () => {
  it("renders one bar per data point", () => {
    const { container } = render(<CoverageSparkline data={[0, 0.5, 1]} />);
    const bars = container.querySelectorAll("rect");
    expect(bars.length).toBe(3);
  });

  it("renders empty state when data is empty", () => {
    const { getByText } = render(<CoverageSparkline data={[]} />);
    expect(getByText(/—/)).toBeInTheDocument();
  });

  it("clamps values to 0..1", () => {
    const { container } = render(<CoverageSparkline data={[-0.5, 1.5]} />);
    const bars = container.querySelectorAll("rect");
    // implementation detail check via attribute
    const heights = Array.from(bars).map((b) => Number(b.getAttribute("height")));
    expect(heights[0]).toBeLessThanOrEqual(20);
    expect(heights[1]).toBeLessThanOrEqual(20);
    expect(heights[0]).toBeGreaterThanOrEqual(0);
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/coverage-sparkline.test.tsx --reporter=verbose && cd ..`
Expected: ImportError

- [ ] **Step 3: 實作 component**

```tsx
// web/components/library/coverage-sparkline.tsx
import { cn } from "@/lib/utils";

type Props = {
  data: number[];        // 0..1 success rate per day
  width?: number;        // default 70px
  height?: number;       // default 20px
  className?: string;
};

const CHART_HEIGHT = 20;

export function CoverageSparkline({ data, width = 70, height = CHART_HEIGHT, className }: Props) {
  if (data.length === 0) {
    return <span className={cn("text-xs text-muted-foreground", className)}>—</span>;
  }
  const barWidth = width / data.length;
  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label="success rate sparkline"
      className={className}
    >
      {data.map((v, i) => {
        const clamped = Math.max(0, Math.min(1, v));
        const barH = clamped * height;
        const x = i * barWidth;
        const y = height - barH;
        const color = clamped >= 0.95 ? "#22c55e" : clamped >= 0.7 ? "#eab308" : "#ef4444";
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(barWidth - 1, 1)}
            height={barH}
            fill={color}
          />
        );
      })}
    </svg>
  );
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/coverage-sparkline.test.tsx && cd ..`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add web/components/library/coverage-sparkline.tsx \
        web/components/library/__tests__/coverage-sparkline.test.tsx
git commit -m "feat(c2): add CoverageSparkline pure-SVG component"
```

---

## Task 22: API hooks — `useLogTypeStats` / `useProductCoverage` / `usePromoteParseRule`

**Files:**
- Create: `web/lib/api/queries/library-stats.ts`
- Modify: `web/lib/api/queries/library.ts` (or create separate parse-rules query module)
- Test: `web/lib/api/queries/__tests__/library-stats.test.ts`

- [ ] **Step 1: 寫 failing tests**

```ts
// web/lib/api/queries/__tests__/library-stats.test.ts
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { useLogTypeStats, useProductCoverage } from "@/lib/api/queries/library-stats";
import { usePromoteParseRule } from "@/lib/api/queries/parse-rules";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useLogTypeStats", () => {
  it("fetches stats with given range", async () => {
    server.use(
      http.get("/api/v1/library/log_types/abc/stats", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("range")).toBe("14d");
        return HttpResponse.json({
          data: {
            enabled: true,
            range_days: 14,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        });
      }),
    );

    const { result } = renderHook(() => useLogTypeStats("abc", "14d"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.range_days).toBe(14);
  });
});

describe("useProductCoverage", () => {
  it("fetches coverage for vendor/product", async () => {
    server.use(
      http.get("/api/v1/library/products/v/p/coverage", () =>
        HttpResponse.json({
          data: { enabled: true, range_days: 7, log_types: [] },
        }),
      ),
    );
    const { result } = renderHook(() => useProductCoverage("v", "p", "7d"), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.enabled).toBe(true);
  });
});

describe("usePromoteParseRule", () => {
  it("POSTs to /promote and resolves", async () => {
    server.use(
      http.post("/api/v1/library/parse_rules/r1/promote", () =>
        HttpResponse.json({
          data: {
            id: "r1",
            log_type_id: "lt1",
            version: 2,
            vrl_code: ".",
            engine_version: "0.32",
            status: "published",
            notes: null,
            created_at: "2026-05-08T00:00:00Z",
            updated_at: "2026-05-08T00:00:00Z",
          },
        }),
      ),
    );
    const { result } = renderHook(() => usePromoteParseRule(), { wrapper: wrapper() });
    const data = await result.current.mutateAsync("r1");
    expect(data.data.status).toBe("published");
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run lib/api/queries/__tests__/library-stats.test.ts && cd ..`
Expected: ImportError

- [ ] **Step 3: 實作 hooks**

```ts
// web/lib/api/queries/library-stats.ts
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type LogTypeStats = components["schemas"]["LogTypeStats"];
type ProductCoverage = components["schemas"]["ProductCoverage"];
type StatsRange = "7d" | "14d" | "30d" | "90d";

export function useLogTypeStats(logTypeId: string, range: StatsRange = "7d") {
  return useQuery<LogTypeStats>({
    queryKey: ["library", "log-type-stats", logTypeId, range],
    queryFn: async () => {
      const r = await apiFetch<{ data: LogTypeStats }>(
        `/api/v1/library/log_types/${logTypeId}/stats`,
        { searchParams: { range } },
      );
      return r.data;
    },
    staleTime: 1000 * 30,
  });
}

export function useProductCoverage(vendorSlug: string, productSlug: string, range: StatsRange = "7d") {
  return useQuery<ProductCoverage>({
    queryKey: ["library", "product-coverage", vendorSlug, productSlug, range],
    queryFn: async () => {
      const r = await apiFetch<{ data: ProductCoverage }>(
        `/api/v1/library/products/${vendorSlug}/${productSlug}/coverage`,
        { searchParams: { range } },
      );
      return r.data;
    },
    staleTime: 1000 * 30,
  });
}
```

```ts
// web/lib/api/queries/parse-rules.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

export function useParseRulesByLogType(logTypeId: string | null) {
  return useQuery<ParseRuleRead[]>({
    enabled: logTypeId !== null,
    queryKey: ["library", "parse-rules", logTypeId],
    queryFn: async () => {
      const r = await apiFetch<{ data: ParseRuleRead[] }>(
        `/api/v1/library/log_types/${logTypeId}/parse_rules`,
      );
      return r.data;
    },
  });
}

export function usePromoteParseRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) =>
      apiFetch<{ data: ParseRuleRead }>(
        `/api/v1/library/parse_rules/${ruleId}/promote`,
        { method: "POST" },
      ),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["library", "parse-rules", data.data.log_type_id] });
      qc.invalidateQueries({ queryKey: ["library", "product-detail"] });
      qc.invalidateQueries({ queryKey: ["library", "overview"] });
    },
  });
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run lib/api/queries/__tests__/library-stats.test.ts && cd ..`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/queries/library-stats.ts web/lib/api/queries/parse-rules.ts \
        web/lib/api/queries/__tests__/library-stats.test.ts
git commit -m "feat(c2): add useLogTypeStats / useProductCoverage / usePromoteParseRule hooks"
```

---

## Task 23: `<LogTypeStatsTab>` — recharts 雙線圖 + range 切換

**Files:**
- Create: `web/components/library/log-type-stats-tab.tsx`
- Test: `web/components/library/__tests__/log-type-stats-tab.test.tsx`

- [ ] **Step 1: 寫 failing test**

```tsx
// web/components/library/__tests__/log-type-stats-tab.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { LogTypeStatsTab } from "../log-type-stats-tab";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("LogTypeStatsTab", () => {
  it("shows banner when stats disabled", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: false,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(withQuery(<LogTypeStatsTab logTypeId="lt1" />));
    await waitFor(() =>
      expect(screen.getByText(/啟用 ClickHouse/i)).toBeInTheDocument(),
    );
  });

  it("renders empty state when timeline has no entries", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: true,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(withQuery(<LogTypeStatsTab logTypeId="lt1" />));
    await waitFor(() =>
      expect(screen.getByText(/無 parse 紀錄/i)).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/log-type-stats-tab.test.tsx && cd ..`
Expected: ImportError

- [ ] **Step 3: 實作 component**

```tsx
// web/components/library/log-type-stats-tab.tsx
"use client";

import { useState } from "react";
import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLogTypeStats } from "@/lib/api/queries/library-stats";
import { cn } from "@/lib/utils";

type StatsRange = "7d" | "14d" | "30d" | "90d";
const RANGES: StatsRange[] = ["7d", "14d", "30d", "90d"];

type Props = { logTypeId: string };

export function LogTypeStatsTab({ logTypeId }: Props) {
  const [range, setRange] = useState<StatsRange>("7d");
  const query = useLogTypeStats(logTypeId, range);

  if (query.isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">載入中…</p>;
  }
  if (query.isError) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-sm">
        暫時無法取得統計
        <button
          type="button"
          className="ml-3 underline"
          onClick={() => query.refetch()}
        >
          重試
        </button>
      </div>
    );
  }
  const stats = query.data!;
  if (!stats.enabled) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-sm text-muted-foreground">
        Stats 功能需啟用 ClickHouse（環境變數 <code>CLICKHOUSE_URL</code>）
      </div>
    );
  }
  if (stats.timeline.length === 0) {
    return (
      <div className="flex flex-col gap-3 p-6">
        <RangeToggle range={range} onChange={setRange} />
        <p className="text-sm text-muted-foreground">過去 {stats.range_days} 天無 parse 紀錄</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <RangeToggle range={range} onChange={setRange} />
        <div className="text-xs text-muted-foreground">
          總計 {stats.totals.total} · 成功 {stats.totals.success} · 失敗 {stats.totals.error} · 成功率{" "}
          {(stats.totals.success_rate * 100).toFixed(1)}%
        </div>
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart
            data={stats.timeline.map((p) => ({
              day: p.day,
              successRate: Number((p.success_rate * 100).toFixed(2)),
              volume: p.total,
            }))}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="successRate"
              stroke="#22c55e"
              dot={false}
              name="Success rate"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="volume"
              stroke="#6366f1"
              dot={false}
              name="Volume"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RangeToggle({
  range,
  onChange,
}: {
  range: StatsRange;
  onChange: (r: StatsRange) => void;
}) {
  return (
    <div className="flex gap-1">
      {RANGES.map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => onChange(r)}
          className={cn(
            "rounded border px-2 py-0.5 text-xs",
            r === range
              ? "border-purple-600 bg-purple-100 text-purple-900"
              : "border-transparent text-muted-foreground hover:border-muted",
          )}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/log-type-stats-tab.test.tsx && cd ..`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add web/components/library/log-type-stats-tab.tsx \
        web/components/library/__tests__/log-type-stats-tab.test.tsx
git commit -m "feat(c2): add LogTypeStatsTab with recharts and range toggle"
```

---

## Task 24: `<VersionsTab>` — 版本表 + Promote button

**Files:**
- Create: `web/components/library/versions-tab.tsx`
- Test: `web/components/library/__tests__/versions-tab.test.tsx`

- [ ] **Step 1: 寫 failing test**

```tsx
// web/components/library/__tests__/versions-tab.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { VersionsTab } from "../versions-tab";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

const VERSIONS = [
  { id: "r3", log_type_id: "lt1", version: 3, vrl_code: ". = 3", engine_version: "0.32", status: "draft", notes: null, created_at: "2026-05-08T00:00:00Z", updated_at: "2026-05-08T00:00:00Z" },
  { id: "r2", log_type_id: "lt1", version: 2, vrl_code: ". = 2", engine_version: "0.32", status: "published", notes: null, created_at: "2026-05-07T00:00:00Z", updated_at: "2026-05-07T00:00:00Z" },
  { id: "r1", log_type_id: "lt1", version: 1, vrl_code: ". = 1", engine_version: "0.32", status: "archived", notes: null, created_at: "2026-05-01T00:00:00Z", updated_at: "2026-05-01T00:00:00Z" },
];

describe("VersionsTab", () => {
  it("renders rows for all versions with status badges", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => {
      expect(screen.getByText("v3")).toBeInTheDocument();
      expect(screen.getByText("v2")).toBeInTheDocument();
      expect(screen.getByText("v1")).toBeInTheDocument();
    });
    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.getByText("published")).toBeInTheDocument();
    expect(screen.getByText("archived")).toBeInTheDocument();
  });

  it("shows Promote only for draft", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => screen.getByText("v3"));
    const promoteButtons = screen.getAllByRole("button", { name: /Promote/i });
    expect(promoteButtons).toHaveLength(1);
  });

  it("clicking Promote opens confirm and POSTs on confirm", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
      http.post("/api/v1/library/parse_rules/r3/promote", () =>
        HttpResponse.json({ data: { ...VERSIONS[0], status: "published" } }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => screen.getByText("v3"));

    fireEvent.click(screen.getByRole("button", { name: /Promote/i }));
    const confirm = await screen.findByRole("button", { name: /確定/i });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /確定/i })).not.toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/versions-tab.test.tsx && cd ..`
Expected: ImportError

- [ ] **Step 3: 實作 component**

```tsx
// web/components/library/versions-tab.tsx
"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  useParseRulesByLogType,
  usePromoteParseRule,
} from "@/lib/api/queries/parse-rules";
import { cn } from "@/lib/utils";

type Props = { logTypeId: string };

export function VersionsTab({ logTypeId }: Props) {
  const query = useParseRulesByLogType(logTypeId);
  const promote = usePromoteParseRule();
  const [confirming, setConfirming] = useState<string | null>(null);

  if (query.isLoading) return <p className="p-6 text-sm text-muted-foreground">載入中…</p>;
  if (query.isError) return <p className="p-6 text-sm text-destructive">無法取得版本列表</p>;
  const rules = query.data ?? [];
  if (rules.length === 0) {
    return <p className="p-6 text-sm text-muted-foreground">尚無版本</p>;
  }

  return (
    <div className="flex flex-col gap-2 p-6">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2">Version</th>
            <th className="py-2">Status</th>
            <th className="py-2">Created</th>
            <th className="py-2">Engine</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id} className={cn("border-t", r.status === "archived" && "opacity-60")}>
              <td className="py-2 font-mono">v{r.version}</td>
              <td className="py-2">
                <StatusBadge status={r.status} />
              </td>
              <td className="py-2 text-xs text-muted-foreground">{r.created_at}</td>
              <td className="py-2 text-xs">{r.engine_version}</td>
              <td className="py-2 text-right">
                {r.status === "draft" && (
                  <button
                    type="button"
                    className="rounded border px-2 py-0.5 text-xs hover:bg-muted"
                    onClick={() => setConfirming(r.id)}
                  >
                    Promote
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {confirming && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        >
          <div className="w-80 rounded-lg bg-card p-4 shadow-lg">
            <h3 className="text-sm font-semibold">Promote 確認</h3>
            <p className="mt-2 text-xs text-muted-foreground">
              這個版本將取代目前的 published rule，舊版會被 archive。確定？
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded border px-3 py-1 text-xs"
                onClick={() => setConfirming(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded bg-purple-600 px-3 py-1 text-xs text-white"
                onClick={async () => {
                  try {
                    await promote.mutateAsync(confirming!);
                  } finally {
                    setConfirming(null);
                  }
                }}
              >
                確定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant: "default" | "secondary" | "outline" =
    status === "published" ? "default" : status === "archived" ? "secondary" : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/versions-tab.test.tsx && cd ..`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add web/components/library/versions-tab.tsx \
        web/components/library/__tests__/versions-tab.test.tsx
git commit -m "feat(c2): add VersionsTab with Promote confirm dialog"
```

---

## Task 25: `<VersionDiffModal>` — react-diff-viewer-continued

**Files:**
- Create: `web/components/library/version-diff-modal.tsx`
- Test: `web/components/library/__tests__/version-diff-modal.test.tsx`

- [ ] **Step 1: 寫 failing test**

```tsx
// web/components/library/__tests__/version-diff-modal.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VersionDiffModal } from "../version-diff-modal";

const RULES = [
  { id: "r2", version: 2, vrl_code: ".x = 2" },
  { id: "r1", version: 1, vrl_code: ".x = 1" },
];

describe("VersionDiffModal", () => {
  it("renders diff between selected versions", () => {
    render(<VersionDiffModal rules={RULES as any} initialLeftId="r1" initialRightId="r2" onClose={vi.fn()} />);
    // diff viewer shows both texts somewhere
    expect(screen.getByText(/\.x = 1/)).toBeInTheDocument();
    expect(screen.getByText(/\.x = 2/)).toBeInTheDocument();
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(<VersionDiffModal rules={RULES as any} initialLeftId="r1" initialRightId="r2" onClose={onClose} />);
    screen.getByRole("button", { name: /關閉|close/i }).click();
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/version-diff-modal.test.tsx && cd ..`
Expected: ImportError

- [ ] **Step 3: 實作 component**

```tsx
// web/components/library/version-diff-modal.tsx
"use client";

import { useMemo, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";

import type { components } from "@/lib/api/types";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

type Props = {
  rules: ParseRuleRead[];
  initialLeftId: string;
  initialRightId: string;
  onClose: () => void;
};

export function VersionDiffModal({ rules, initialLeftId, initialRightId, onClose }: Props) {
  const [leftId, setLeftId] = useState(initialLeftId);
  const [rightId, setRightId] = useState(initialRightId);

  const left = useMemo(() => rules.find((r) => r.id === leftId), [rules, leftId]);
  const right = useMemo(() => rules.find((r) => r.id === rightId), [rules, rightId]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6"
    >
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-lg bg-card shadow-lg">
        <header className="flex items-center justify-between border-b p-3">
          <h3 className="text-sm font-semibold">版本比對</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-2 py-0.5 text-xs"
            aria-label="close"
          >
            關閉
          </button>
        </header>
        <div className="flex gap-3 border-b p-3 text-xs">
          <Selector label="Left" value={leftId} onChange={setLeftId} rules={rules} />
          <Selector label="Right" value={rightId} onChange={setRightId} rules={rules} />
        </div>
        <div className="overflow-auto">
          <ReactDiffViewer
            oldValue={left?.vrl_code ?? ""}
            newValue={right?.vrl_code ?? ""}
            splitView
            useDarkTheme={false}
          />
        </div>
      </div>
    </div>
  );
}

function Selector({
  label,
  value,
  onChange,
  rules,
}: {
  label: string;
  value: string;
  onChange: (id: string) => void;
  rules: ParseRuleRead[];
}) {
  return (
    <label className="flex items-center gap-1">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border bg-background px-2 py-0.5"
      >
        {rules.map((r) => (
          <option key={r.id} value={r.id}>
            v{r.version} ({r.status})
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/version-diff-modal.test.tsx && cd ..`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add web/components/library/version-diff-modal.tsx \
        web/components/library/__tests__/version-diff-modal.test.tsx
git commit -m "feat(c2): add VersionDiffModal using react-diff-viewer-continued"
```

---

## Task 26: 把 sub-tabs (Overview / Stats / Versions) 接進 ProductDetailView

**Files:**
- Modify: `web/components/library/product-detail-view.tsx`
- Test: `web/components/library/__tests__/product-detail-view-tabs.test.tsx` (new)

- [ ] **Step 1: 寫 failing test（驗證新 sub-tabs 出現 + 切換 Stats / Versions render 對應 component）**

```tsx
// web/components/library/__tests__/product-detail-view-tabs.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { ProductDetailView } from "../product-detail-view";

const DETAIL = {
  id: "p1",
  vendor_id: "v1",
  name: "Test",
  slug: "test",
  version: null,
  description: null,
  deploy_type: null,
  doc_url: null,
  status: "active" as const,
  created_at: "2026-05-08T00:00:00Z",
  updated_at: "2026-05-08T00:00:00Z",
  log_types: [
    {
      id: "lt1",
      product_id: "p1",
      name: "LT",
      slug: "lt",
      format: "csv" as const,
      transport: null,
      status: "draft" as const,
      source: "manual" as const,
      current_parse_rule_id: null,
      description: null,
      published_at: null,
      created_at: "2026-05-08T00:00:00Z",
      updated_at: "2026-05-08T00:00:00Z",
      fields: [],
      current_parse_rule: null,
      samples: [],
    },
  ],
};

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("ProductDetailView sub-tabs", () => {
  it("renders Overview / Stats / Versions tab buttons per log type", () => {
    render(withQuery(<ProductDetailView vendorSlug="v" detail={DETAIL as any} />));
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stats" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Versions" })).toBeInTheDocument();
  });

  it("clicking Stats fetches log type stats", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: false,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(withQuery(<ProductDetailView vendorSlug="v" detail={DETAIL as any} />));
    fireEvent.click(screen.getByRole("button", { name: "Stats" }));
    await waitFor(() => expect(screen.getByText(/啟用 ClickHouse/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/product-detail-view-tabs.test.tsx && cd ..`
Expected: FAIL

- [ ] **Step 3: 改 ProductDetailView**

替換 `web/components/library/product-detail-view.tsx` 內容：

```tsx
"use client";

import { useState } from "react";

import { FieldTable } from "@/components/library/field-table";
import { LogTypeStatsTab } from "@/components/library/log-type-stats-tab";
import { LogTypeTabs } from "@/components/library/log-type-tabs";
import { SampleList } from "@/components/library/sample-list";
import { VersionsTab } from "@/components/library/versions-tab";
import { VrlDisplay } from "@/components/library/vrl-display";
import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ProductDetail = components["schemas"]["ProductDetail"];

type SubTab = "overview" | "stats" | "versions";
const SUB_TABS: { id: SubTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "stats", label: "Stats" },
  { id: "versions", label: "Versions" },
];

type Props = { vendorSlug: string; detail: ProductDetail };

export function ProductDetailView({ vendorSlug, detail }: Props) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [subTab, setSubTab] = useState<SubTab>("overview");
  const activeLogType = detail.log_types[activeIdx];

  const initials = vendorSlug.slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 rounded-lg border bg-card p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded bg-muted text-sm font-bold text-muted-foreground">
            {initials}
          </div>
          <div className="flex flex-1 flex-col">
            <h1 className="text-xl font-semibold tracking-tight">{detail.name}</h1>
            <p className="text-sm text-muted-foreground">
              {detail.version ?? "—"} · {vendorSlug}
            </p>
          </div>
          <Badge variant={detail.status === "active" ? "default" : "secondary"}>
            {detail.status}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-3">
          <Stat label="Log types" value={detail.log_types.length} />
          <Stat
            label="Fields"
            value={detail.log_types.reduce((s, lt) => s + lt.fields.length, 0)}
          />
          <Stat
            label="Samples"
            value={detail.log_types.reduce((s, lt) => s + lt.samples.length, 0)}
          />
        </div>
      </header>

      {detail.log_types.length === 0 ? (
        <p className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">
          這個 product 還沒有 log type — 用 API 或之後從 Analyzer 建立
        </p>
      ) : (
        <>
          <LogTypeTabs
            logTypes={detail.log_types}
            activeIdx={activeIdx}
            onChange={(i) => {
              setActiveIdx(i);
              setSubTab("overview");
            }}
          />
          {activeLogType && (
            <div className="rounded-lg border bg-card">
              <div className="flex gap-1 border-b px-3">
                {SUB_TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSubTab(t.id)}
                    className={cn(
                      "border-b-2 px-3 py-2 text-sm",
                      subTab === t.id
                        ? "border-purple-600 font-semibold"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              {subTab === "overview" && (
                <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-2">
                  <FieldTable fields={activeLogType.fields} />
                  <SampleList samples={activeLogType.samples} logTypeId={activeLogType.id} />
                  <div className="lg:col-span-2">
                    <VrlDisplay rule={activeLogType.current_parse_rule} logTypeId={activeLogType.id} />
                  </div>
                </div>
              )}
              {subTab === "stats" && <LogTypeStatsTab logTypeId={activeLogType.id} />}
              {subTab === "versions" && <VersionsTab logTypeId={activeLogType.id} />}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/product-detail-view-tabs.test.tsx && cd ..`
Expected: 2 passed

- [ ] **Step 5: 確認既有 component tests 沒退化**

Run: `cd web && npm test -- --run && cd ..`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add web/components/library/product-detail-view.tsx \
        web/components/library/__tests__/product-detail-view-tabs.test.tsx
git commit -m "feat(c2): add Overview/Stats/Versions sub-tabs to ProductDetailView"
```

---

## Task 27: Library overview sparkline column

**Files:**
- Modify: `web/components/library/library-overview-view.tsx` (主檔)
- Or: 適當的 vendor / overview 元件 — 視 overview 結構而定

**Research note:** 開始這 task 前先讀 `web/components/library/library-overview-view.tsx` 與 `vendor-group.tsx` 看 overview 用什麼結構列出 product 與 log_type，再決定 sparkline column 接在哪一層（最自然應該是 vendor-group 或下層的 product-card）。

- [ ] **Step 1: Inspect overview structure**

Run: `cat web/components/library/library-overview-view.tsx web/components/library/vendor-group.tsx`

- [ ] **Step 2: 寫 failing test（在最自然的元件）**

範例（若 overview-view 自己拉所有 vendor/product，加 useProductCoverage 的 query 並把 sparkline 傳下去）。

簡化版本：在每個 product 下顯示一個 7d sparkline，資料以 `useProductCoverage(vendor.slug, product.slug, "7d")` 取得。

```tsx
// web/components/library/__tests__/library-overview-coverage.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { LibraryOverviewView } from "../library-overview-view";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("LibraryOverviewView coverage column", () => {
  it("calls coverage endpoint per product and renders sparkline svg", async () => {
    server.use(
      http.get("/api/v1/library/overview", () =>
        HttpResponse.json({
          data: [
            {
              vendor: { id: "v", name: "V", slug: "v", logo_url: null },
              products: [
                {
                  id: "p1",
                  name: "P1",
                  slug: "p1",
                  status: "active",
                  log_type_counts: { total: 1, published: 1, draft: 0 },
                  is_empty: false,
                },
              ],
            },
          ],
        }),
      ),
      http.get("/api/v1/library/products/v/p1/coverage", () =>
        HttpResponse.json({
          data: {
            enabled: true,
            range_days: 7,
            log_types: [
              { log_type_id: "lt1", sparkline: [1, 1, 1, 1, 1, 1, 1], success_rate_avg: 1, volume: 7 },
            ],
          },
        }),
      ),
    );
    const { container } = render(withQuery(<LibraryOverviewView />));
    await waitFor(() => screen.getByText("P1"));
    await waitFor(() => expect(container.querySelector("svg")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run test, expect FAIL**

Run: `cd web && npx vitest run components/library/__tests__/library-overview-coverage.test.tsx && cd ..`
Expected: FAIL（目前 overview 沒整合 coverage）

- [ ] **Step 4: 在 LibraryOverviewView 加 sparkline**

讀現有 overview 結構，找到 render product 的地方，在每個 product 額外注入 `<CoverageSparkline data={...} />`。
資料來源：每個 product 用 `useProductCoverage(vendor.slug, product.slug, "7d")` 拿 coverage。彙整每個 product 下的 log_types 平均 success_rate 為 sparkline（**或顯示第一個 log_type 的 sparkline**，端看 UX 取捨；建議**「過去 7 天該 product 下所有 log_types 加總後的整體 success_rate per day」**作為 sparkline；若實作太重，先 fallback 取第一個 log_type）。

> 實作細節：先 fallback 顯示第一個 log_type 的 sparkline；之後再優化加總平均。

簡化版實作（在 LibraryOverviewView 或 product 渲染處）：

```tsx
import { CoverageSparkline } from "@/components/library/coverage-sparkline";
import { useProductCoverage } from "@/lib/api/queries/library-stats";

function ProductCoverageCell({ vendorSlug, productSlug }: { vendorSlug: string; productSlug: string }) {
  const { data } = useProductCoverage(vendorSlug, productSlug, "7d");
  if (!data || !data.enabled) return <span className="text-xs text-muted-foreground">—</span>;
  const first = data.log_types[0];
  if (!first) return <span className="text-xs text-muted-foreground">—</span>;
  return <CoverageSparkline data={first.sparkline} />;
}
```

把 `<ProductCoverageCell vendorSlug={v.vendor.slug} productSlug={p.slug} />` 接到每個 product 顯示處（可能是 vendor-group 或 product-card）。

- [ ] **Step 5: Run test, expect PASS**

Run: `cd web && npx vitest run components/library/__tests__/library-overview-coverage.test.tsx && cd ..`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/components/library/library-overview-view.tsx \
        web/components/library/vendor-group.tsx \
        web/components/library/__tests__/library-overview-coverage.test.tsx
git commit -m "feat(c2): show 7-day coverage sparkline per product on Library overview"
```

---

## Task 28: AnalyzerView — 帶 log_type_id / parse_rule_id 進 /parse

**Files:**
- Modify: `web/components/analyzer/analyzer-view.tsx`

- [ ] **Step 1: 找 useParse 呼叫點**

Run:
```bash
grep -rn "useParse\|/api/v1/analyzer/parse" web/components/analyzer web/lib/api
```

- [ ] **Step 2: 改 useParse / 對應 hook，把 preload 的 log_type_id / parse_rule_id 帶進 body**

`web/lib/api/queries/analyzer.ts` 找到 `useParse` 的 body 組裝處，加：

```ts
body: {
  vrl_code: vrl,
  logs,
  engine_version: engine,
  log_type_id: logTypeId ?? undefined,
  parse_rule_id: parseRuleId ?? undefined,
}
```

並從 `useParse` 的 caller 把 preload 的 log_type_id / parse_rule_id 傳下來。

`AnalyzerView` 從 `preload` 拿 log_type_id / parse_rule_id 維持 state（已在 C1 做過 preload 機制，沿用），呼叫 useParse 時把它們帶上。

- [ ] **Step 3: 加單元測試（驗證 hook 把 ids 帶上）**

```ts
// web/lib/api/queries/__tests__/use-parse-with-context.test.ts
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { useParse } from "@/lib/api/queries/analyzer";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useParse", () => {
  it("includes log_type_id and parse_rule_id in body when provided", async () => {
    let captured: any = null;
    server.use(
      http.post("/api/v1/analyzer/parse", async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({ data: { kind: "empty", engine: "0.32" } });
      }),
    );
    const { result } = renderHook(
      () =>
        useParse({
          vrl: ".x = 1",
          logs: ["a"],
          engine: "0.32",
          log_type_id: "lt1",
          parse_rule_id: "r1",
        }),
      { wrapper: wrapper() },
    );
    // wait for query
    await new Promise((r) => setTimeout(r, 50));
    expect(captured.log_type_id).toBe("lt1");
    expect(captured.parse_rule_id).toBe("r1");
  });
});
```

> 若 useParse 既有簽名不接 log_type_id / parse_rule_id，需先擴充。

- [ ] **Step 4: Run test, expect PASS**

Run: `cd web && npx vitest run lib/api/queries/__tests__/use-parse-with-context.test.ts && cd ..`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/queries/analyzer.ts web/components/analyzer/analyzer-view.tsx \
        web/lib/api/queries/__tests__/use-parse-with-context.test.ts
git commit -m "feat(c2): pass log_type_id and parse_rule_id from AnalyzerView to /parse

enables stats correlation with Library context"
```

---

## Task 29: Playwright e2e — Promote 流程

**Files:**
- Create: `web/test/e2e/c2-promote.spec.ts`

- [ ] **Step 1: 寫 e2e**

```ts
// web/test/e2e/c2-promote.spec.ts
import { test, expect } from "@playwright/test";

test("Promote v3 archives v2 and updates current rule", async ({ page, request }) => {
  // login
  await page.goto("/login");
  await page.fill('input[name="email"]', process.env.LOGSCOPE_ADMIN_EMAIL!);
  await page.fill('input[name="password"]', process.env.LOGSCOPE_ADMIN_PASSWORD!);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/library");

  // Seed: vendor + product + log_type + 2 drafts via API (faster than UI)
  const u = Math.random().toString(36).slice(2, 8);
  const v = await request.post("/api/v1/library/vendors", {
    data: { name: `V ${u}`, slug: `v-${u}` },
  });
  const vendor = (await v.json()).data;
  const p = await request.post(`/api/v1/library/vendors/v-${u}/products`, {
    data: { name: "P", slug: "p" },
  });
  const product = (await p.json()).data;
  const lt = await request.post(`/api/v1/library/products/${product.id}/log_types`, {
    data: { name: "LT", slug: "lt", format: "csv" },
  });
  const logType = (await lt.json()).data;
  const r1 = await request.post(`/api/v1/library/log_types/${logType.id}/parse_rules`, {
    data: { vrl_code: ".x = 1", engine_version: "0.32" },
  });
  await request.post(`/api/v1/library/parse_rules/${(await r1.json()).data.id}/promote`);
  const r2 = await request.post(`/api/v1/library/log_types/${logType.id}/parse_rules`, {
    data: { vrl_code: ".x = 2", engine_version: "0.32" },
  });
  const draft2 = (await r2.json()).data;

  // Navigate to product detail
  await page.goto(`/library/v-${u}/p`);
  await page.click('button:has-text("Versions")');
  await expect(page.locator(`text=v2`)).toBeVisible();
  await expect(page.locator(`text=v1`)).toBeVisible();

  // Promote v2 (the only draft)
  await page.click('button:has-text("Promote")');
  await page.click('button:has-text("確定")');

  // After promote, v1 should be archived, v2 published
  await expect(page.locator(`tr:has-text("v2") :text("published")`)).toBeVisible();
  await expect(page.locator(`tr:has-text("v1") :text("archived")`)).toBeVisible();

  // Cleanup
  await request.delete(`/api/v1/library/log_types/${logType.id}`);
  await request.delete(`/api/v1/library/products/${product.id}`);
  await request.delete(`/api/v1/library/vendors/${vendor.id}`);
});
```

- [ ] **Step 2: Run test**

Run:
```bash
make up
make migrate
make dev-be
make dev-fe
sleep 5
LOGSCOPE_ADMIN_EMAIL=$LOGSCOPE_ADMIN_EMAIL LOGSCOPE_ADMIN_PASSWORD=$LOGSCOPE_ADMIN_PASSWORD \
  cd web && npx playwright test test/e2e/c2-promote.spec.ts && cd ..
```
Expected: 1 passed

- [ ] **Step 3: Stop**

Run: `make stop-all`

- [ ] **Step 4: Commit**

```bash
git add web/test/e2e/c2-promote.spec.ts
git commit -m "test(c2): playwright e2e for promote draft -> published flow"
```

---

## Task 30: Makefile + .env.example finishing

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: 加 dev-stats target**

`Makefile` 在 `up:` 之上找適當位置插入：

```makefile
dev-stats:
	docker compose --profile stats up -d clickhouse
	@echo "ClickHouse on :8123 — set CLICKHOUSE_URL in .env to enable Stats"
```

並把 `dev-stats` 加進 `.PHONY`：

```makefile
.PHONY: ... dev-stats
```

- [ ] **Step 2: 試跑**

Run:
```bash
make dev-stats
```
Expected: clickhouse 啟動、看到提示

```bash
docker compose --profile stats down
```

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore(c2): add make dev-stats target"
```

---

## Task 31: 全綠 + Self-review

**Files:**
- 無

- [ ] **Step 1: 跑全部 lint + test**

Run:
```bash
make lint
make test
```
Expected: all green

- [ ] **Step 2: 跑 integration（CH + PG 都要起來）**

Run:
```bash
make up
docker compose --profile stats up -d clickhouse
make migrate
CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope make test-int
```
Expected: all green

- [ ] **Step 3: 跑 frontend tests**

Run:
```bash
make test-fe
```
Expected: all green

- [ ] **Step 4: 跑 e2e**

Run:
```bash
make dev-all
sleep 5
make test-fe-e2e
```
Expected: all green

```bash
make stop-all
```

- [ ] **Step 5: 手動 smoke**

啟動 stack（含 CH）：
```bash
docker compose --profile stats up -d
make migrate
make dev-all
```

逐項 smoke：
1. 登入 → 進 `/analyzer` → 貼 `.x = 1\n.` 與 `["one","two"]` → parse 三次
2. 進 `/library/<vendor>/<product>` → Stats tab → 應該看到 timeline / totals（過去 7 天）
3. 切 14d / 30d / 90d → chart refetch
4. 進 Versions tab → 看到歷史版本與 status
5. 對任何 draft 點 Promote → confirm → toast → status 變化
6. 在 Library overview 看 sparkline 列出
7. 把 CLICKHOUSE_URL 從 .env 拿掉 → 重啟 backend → 進 Stats tab 應該看到「需啟用 ClickHouse」灰字 banner，主功能不受影響

- [ ] **Step 6: 推上 branch + 開 PR**

Run:
```bash
git push -u origin feat/c2-stats-and-versions
gh pr create --title "feat: C2 — stats + parse rule version history" \
             --body "Implements docs/superpowers/specs/2026-05-08-c2-stats-and-versions-design.md"
```

---

## Self-Review

- ✅ Spec §1.1 進 v1 範圍：CH infra (Tasks 1-5) / parse stats 寫入 (Tasks 6-8, 12) / Stats 讀取 (Tasks 9-11) / 三態 + Versions (Tasks 13-19) / Frontend (Tasks 20-29)
- ✅ Spec §3 CH schema → Task 4 DDL 完整對應
- ✅ Spec §4 PG migration 0005 → Task 13；archive 既有重複 published 已包含
- ✅ Spec §5 前端 → Tasks 21-28；Stats tab、Versions tab、Diff modal、sparkline column 全列
- ✅ Spec §6 資料流 → Task 8 (parse stats 寫入)、Task 11 (coverage 讀取)、Task 16-17 (promote 流程)
- ✅ Spec §7 錯誤處理 → 各 router test 涵蓋 enabled=false / 503 / 404 / 409
- ✅ Spec §8 測試策略 → 每個 Task 有 unit + 必要的 integration / e2e
- ✅ Spec §9 docker-compose / Makefile / .env → Task 1, 2, 30
- ✅ Spec §10 驗收 → Task 31

**No placeholders found.** **Type consistency:** `StatsRecorder.record(event)` / `StatsService.log_type_stats(id, range)` / `ParseRuleService.promote(rule_id)` 在 backend / frontend / tests 用同名同簽名。

**Engine usage chart 未 render**：spec §1.2 已說明可選；schema 仍包 engine_usage data，UI 可後續加（不算缺口）。

**Caveat for executor (Next.js)**：`web/AGENTS.md` 警告此版本 Next.js 有 breaking changes。本 plan 沒新增頁面或 dynamic route，主要是改 client component；但 Task 26 改 `ProductDetailView` 與 Task 27 改 overview view 前，請先 grep `web/node_modules/next/dist/docs/` 確認 client/server boundary 與 use client 規則沒 break。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-08-c2-stats-and-versions.md`.**

兩種執行選項：

1. **Subagent-Driven（推薦）** — 我每個 task 派一隻 fresh subagent，task 之間我做 code review，迭代快、context 不混亂
2. **Inline Execution** — 直接在這個 session 內依序跑、每幾個 task 一個 checkpoint 給你看

請選一個。
