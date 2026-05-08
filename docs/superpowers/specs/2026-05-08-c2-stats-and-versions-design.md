# LogScope — C2: Analyzer Stats + Parse Rule 版本歷史 (Spec C2) Design

- 日期：2026-05-08
- 子專案編號：5（C2：ClickHouse parse stats + Library coverage UI + Parse rule 版本歷史）
- 已完成前置：Plan 1a / 1b / 1c / C1
- 後續 spec：D（Copilot）、E（LLM Pipeline）
- 上游文件：`docs/LogScope_Design_Document_v1.2.html` §8.5 資料庫職責分工（PG / CH / Redis）
- 來源：C1 Known gaps（`docs/superpowers/plans/2026-05-08-c1-analyzer.md`）

---

## 1. 範圍

### 1.1 進 v1（C2）

**ClickHouse infra**
- `docker-compose.yml` 加 `clickhouse` service，使用 profile `stats` 預設不啟動
- `app/core/clickhouse.py`：`clickhouse-connect` async client、FastAPI lifespan 管理、`get_clickhouse()` dependency
- `app/core/clickhouse_schema.py`：啟動時跑 `CREATE TABLE IF NOT EXISTS parse_events`
- `CLICKHOUSE_URL` 為 None 時整個 Stats 子系統 silently no-op（與 C1 `ANTHROPIC_API_KEY` 可選一致）

**Parse stats 寫入**
- `POST /api/v1/analyzer/parse` 成功處理後 schedule `BackgroundTasks` 寫一筆 `parse_events`
- 抽 `app/modules/analyzer/services/stats_recorder.py`：`StatsRecorder.record(event)` 介面，client=None 時 no-op；未來換 Redis Stream 不影響 caller

**Coverage / Stats 讀取**
- `GET /api/v1/library/log_types/{id}/stats?range=7d`：success rate timeline、volume timeline、engine 用量
- `GET /api/v1/library/products/{vendor}/{product}/coverage?range=7d`：該 product 下每個 log type 的 sparkline 用資料

**Library 詳情頁 UI**
- vendor 詳情頁的 log type 列表加 "Coverage 7d" 欄，render 純 SVG `<CoverageSparkline>`
- log type 詳情頁新增 `Stats` tab，與 `Samples` / `Fields` 並列；recharts 雙線圖（success rate + volume）+ 時間窗切換 7/14/30/90

**Parse rule 三態 + 版本歷史 UI**
- ParseRule.status 加 `archived`，DB partial unique 保證每個 log_type 同時最多一個 `published`
- Alembic migration `0003`：加 CHECK constraint、partial unique index、把現有「同一 log_type 多筆 published」整理成只留最新版 published、其餘 → archived
- `POST /api/v1/library/parse_rules/{id}/promote`：在單一 transaction 內把舊 published archive、目標 rule 設 published、更新 log_type.current_parse_rule_id
- log type 詳情頁新增 `Versions` tab：表列所有版本（version / status badge / created_by / created_at）+ Promote 按鈕（confirm dialog）+ Diff modal（react-diff-viewer，任兩版比對）

### 1.2 不進 C2（留給後續）

| 議題 | 後續 spec |
|---|---|
| Fingerprint index 替代或補強 LLM match | 之後優化 |
| LLM match 結果 cache | 視 cost / latency |
| Engine 用量分析（圓餅圖細分） | Stats tab 順手帶；不在驗收標準中 |
| Backfill 工具（CH 補資料） | 不做 — 從 C2 上線後累積即可 |
| Redis Stream + worker batch ingestion | 留到實際有負載時再升級；StatsRecorder interface 已預留 |
| Stats 跨多 log type 比較 / 全 product 概覽 | D / 之後 |

---

## 2. 後端架構

### 2.1 模組樹

```
app/
├── core/
│   ├── clickhouse.py                  # NEW: client + lifespan + dependency
│   └── clickhouse_schema.py           # NEW: CREATE TABLE IF NOT EXISTS on startup
├── modules/
│   ├── analyzer/
│   │   ├── routers/parse_router.py    # CHANGE: 加 BackgroundTasks 寫 stats
│   │   └── services/
│   │       └── stats_recorder.py      # NEW: 抽 StatsRecorder 介面
│   └── library/
│       ├── routers/
│       │   ├── parse_rule_router.py   # CHANGE: 加 promote endpoint
│       │   └── stats_router.py        # NEW: log type stats / product coverage
│       └── services/
│           ├── parse_rule_service.py  # CHANGE: promote() + archive 舊 published
│           └── stats_service.py       # NEW: 查 CH 算 success rate / volume
└── migrations/versions/
    └── 0003_parse_rule_archived_status.py   # NEW
```

### 2.2 ClickHouse client（`app/core/clickhouse.py`）

```python
from typing import AsyncIterator
from contextlib import asynccontextmanager
from clickhouse_connect.driver.asyncclient import AsyncClient
import clickhouse_connect

from app.core.config import settings

_client: AsyncClient | None = None

async def init_clickhouse() -> None:
    global _client
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
    """FastAPI dependency. None when CLICKHOUSE_URL is unset."""
    return _client
```

`init_clickhouse` / `close_clickhouse` 在 FastAPI lifespan 呼叫一次。

### 2.3 StatsRecorder（`app/modules/analyzer/services/stats_recorder.py`）

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import hashlib

@dataclass(frozen=True)
class ParseEvent:
    ts: datetime
    log_type_id: UUID | None
    parse_rule_id: UUID | None
    engine_version: str
    total: int
    success: int
    error: int
    latency_ms: int
    user_id: UUID | None
    raw_log_hash: bytes  # 16 bytes
    vrl_hash: bytes      # 16 bytes


def _hash16(data: str) -> bytes:
    """Truncated blake2b(16 bytes)."""
    return hashlib.blake2b(data.encode("utf-8"), digest_size=16).digest()


class StatsRecorder:
    def __init__(self, client) -> None:  # client: AsyncClient | None
        self._client = client

    async def record(self, event: ParseEvent) -> None:
        if self._client is None:
            return
        try:
            await self._client.insert(
                "parse_events",
                [self._to_row(event)],
                column_names=[
                    "ts", "log_type_id", "parse_rule_id", "engine_version",
                    "total", "success", "error", "latency_ms",
                    "user_id", "raw_log_hash", "vrl_hash",
                ],
            )
        except Exception as exc:  # noqa: BLE001 — fire-and-forget by design
            structlog.get_logger().warning("stats_record_failed", error=str(exc))
```

**呼叫端（parse_router.py）**：

```python
@router.post("/parse")
async def parse(
    body: ParseRequest,
    background: BackgroundTasks,
    parser: Annotated[ParserService, Depends(get_parser_service)],
    recorder: Annotated[StatsRecorder, Depends(get_stats_recorder)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseResponse]:
    started = perf_counter()
    response = await parser.run(body.vrl_code, body.logs, body.engine_version)
    latency_ms = int((perf_counter() - started) * 1000)

    event = ParseEvent(
        ts=datetime.now(timezone.utc),
        log_type_id=body.log_type_id,         # 從 body 帶（C2 schema 變更）
        parse_rule_id=body.parse_rule_id,     # 從 body 帶
        engine_version=body.engine_version,
        total=response.summary.total if response.summary else 0,
        success=response.summary.success if response.summary else 0,
        error=response.summary.error if response.summary else 0,
        latency_ms=latency_ms,
        user_id=user.id,
        raw_log_hash=_hash16(body.logs[0] if body.logs else ""),
        vrl_hash=_hash16(body.vrl_code),
    )
    background.add_task(recorder.record, event)
    return DataResponse(data=response)
```

**Schema 異動**：`AnalyzerParseRequest` 加 `log_type_id: UUID | None = None` 與 `parse_rule_id: UUID | None = None`，前端在「從 Library 進來」/「套用規則」時帶上；冷啟動時兩者皆 None。

**user_id**：C1 已將 `/analyzer/parse` 設為登入後可用（`current_user` required），故實務上 `user_id` 不會是 NULL。CH schema 仍宣告為 `Nullable(UUID)` 是為了未來引入 API token / public demo 模式時不需 schema migration。

### 2.4 StatsService（`app/modules/library/services/stats_service.py`）

```python
class StatsService:
    def __init__(self, client) -> None:  # client: AsyncClient | None
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def log_type_stats(self, log_type_id: UUID, range_days: int) -> LogTypeStats:
        if not self.enabled:
            return LogTypeStats(enabled=False, ...)
        rows = await self._client.query(
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
            parameters={"lt": log_type_id, "days": range_days},
        )
        return self._build_stats(rows)

    async def product_coverage(
        self,
        log_type_ids: list[UUID],
        range_days: int,
    ) -> ProductCoverage:
        if not self.enabled or not log_type_ids:
            return ProductCoverage(enabled=self.enabled, range_days=range_days, log_types=[])
        rows = await self._client.query(
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
            parameters={"ids": log_type_ids, "days": range_days},
        )
        return self._build_coverage(rows, log_type_ids, range_days)
```

Router 先從 PG 拿到該 vendor/product 下的 log_type_id 列表，再把 ids 與 range 一起傳給 service；service 一次 query CH 取得多 log_type 聚合資料，per-log-type 補 0 填齊缺日，回 sparkline array（長度 = range_days）。

### 2.5 Endpoints

#### `POST /api/v1/library/parse_rules/{id}/promote`

```
Response: DataResponse[ParseRuleRead]
```

**Service flow**（`parse_rule_service.promote()`）：

```python
async def promote(self, rule_id: UUID) -> ParseRule:
    async with self._session.begin():  # explicit transaction
        rule = await self._rules.get_for_update(rule_id)
        if rule is None:
            raise NotFoundError(...)
        if rule.status == "archived":
            raise ConflictError("cannot promote archived rule")
        if rule.status == "published":
            return rule  # idempotent
        # rule.status == "draft"

        old_published = await self._rules.get_current_published(rule.log_type_id)
        if old_published is not None:
            old_published.status = "archived"
            await self._rules.update(old_published)

        rule.status = "published"
        await self._rules.update(rule)

        log_type = await self._log_types.get_for_update(rule.log_type_id)
        log_type.current_parse_rule_id = rule.id
        log_type.status = "published"
        log_type.published_at = datetime.now(timezone.utc)
        await self._log_types.update(log_type)

        return rule
```

`partial unique index` 在 race condition 下會 fail，SQLAlchemy 拋 `IntegrityError`，router 轉 `409 Conflict`。

#### `GET /api/v1/library/log_types/{id}/stats?range=7d`

```
Query: range = "7d" | "14d" | "30d" | "90d"  (default "7d")

Response: DataResponse[LogTypeStats]
LogTypeStats = {
  enabled: bool,
  range_days: int,
  timeline: [{ day: "YYYY-MM-DD", total: int, success: int, error: int, success_rate: float }],
  engine_usage: [{ engine_version: "0.25" | "0.32", count: int }],
  totals: { total: int, success: int, error: int, success_rate: float }
}
```

`enabled: false` 時其他欄位回空陣列／0。

#### `GET /api/v1/library/products/{vendor_slug}/{product_slug}/coverage?range=7d`

```
Response: DataResponse[ProductCoverage]
ProductCoverage = {
  enabled: bool,
  range_days: int,
  log_types: [{
    log_type_id: UUID,
    sparkline: [float],          # 每天 success_rate，長度 = range_days
    success_rate_avg: float,     # 範圍內平均
    volume: int                  # 範圍內總量
  }]
}
```

### 2.6 dependencies

```toml
# pyproject.toml
[project]
dependencies = [
  # ...既有...
  "clickhouse-connect>=0.8",
]
```

`.env.example` 補：

```
# ClickHouse (optional — Stats 功能需要)
CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope
```

`Settings`：

```python
clickhouse_url: str | None = Field(default=None, alias="CLICKHOUSE_URL")
```

---

## 3. ClickHouse schema

```sql
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
TTL ts + INTERVAL 90 DAY;
```

**設計選擇**：

- `ORDER BY (log_type_id, ts)` 讓 「某 log type 過去 N 天」走索引；`Nullable(UUID)` 在 ORDER BY 中 ClickHouse 會把 NULL 排在最前，cold start 寫入仍走 partition pruning 不影響查詢效能
- `LowCardinality(String) engine_version` 內部字典壓縮，引擎只有 0.25 / 0.32 兩個值
- TTL 在 server side、自動清理；90 天足以做季度回顧又不會無限長大
- 不存 raw / vrl 全文（v1.2 §8.5「ClickHouse 不存 log 原始資料」），只存 16-byte hash 給未來 dedup
- Schema migration：v1 啟動時跑 `CREATE TABLE IF NOT EXISTS`；之後若要 ALTER，引入 `clickhouse-migrations` 工具（不是現在）

---

## 4. PostgreSQL schema 異動

### 4.1 Alembic migration `0003_parse_rule_archived_status.py`

```python
def upgrade() -> None:
    # 1. drop 既有 status check（如有）以利新增 archived
    op.drop_constraint(
        "parse_rules_status_check", "parse_rules", type_="check", if_exists=True,
    )

    # 2. 既有資料整理：每個 log_type 留最新 published，其餘 published → archived
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
        UPDATE parse_rules
        SET status = 'archived'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    # 3. 新增 status check
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
    op.drop_constraint("parse_rules_status_check", "parse_rules", type_="check")
    op.execute(
        "UPDATE parse_rules SET status = 'published' WHERE status = 'archived'"
    )
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published')",
    )
```

**Repository 改動**（`parse_rule_repository.py`）：

新增 `get_for_update(rule_id)`、`get_current_published(log_type_id)`、`get_versions_with_authors(log_type_id)`。

---

## 5. 前端架構

### 5.1 新元件

| 路徑 | 職責 |
|---|---|
| `web/components/library/coverage-sparkline.tsx` | 純 SVG 7-bar mini chart，0-1 success_rate；接 `data: number[]`；無依賴 |
| `web/components/library/log-type-stats-tab.tsx` | Stats tab 內容；recharts `<LineChart>` 雙 Y 軸（success_rate 0-100% / volume）；time range 切換 7/14/30/90；enabled=false 顯示「需啟用 ClickHouse」灰字 |
| `web/components/library/versions-tab.tsx` | 版本表（version / status badge / created_by / created_at）；Promote 按鈕（draft only，confirm dialog）；Diff modal 觸發 |
| `web/components/library/version-diff-modal.tsx` | 用 `react-diff-viewer-continued` 比對任兩版 vrl_code |
| `web/lib/api/queries/library-stats.ts` | `useLogTypeStats(id, range)`、`useProductCoverage(vendor, product, range)` |
| `web/lib/api/queries/parse-rules.ts` | 既有檔加 `usePromoteParseRule()` mutation |

### 5.2 既有檔案改動

- `web/components/library/product-detail.tsx`（vendor 詳情頁）— log type 列表加 "Coverage 7d" 欄；批次拉一次 `useProductCoverage` 把資料分發給每列
- `web/app/(authed)/library/[vendor]/[product]/[logType]/page.tsx` — Tab 從 `Samples / Fields` 變 `Samples / Fields / Stats / Versions`
- `web/components/analyzer/analyzer-view.tsx` — `useParse` 呼叫時帶 `log_type_id` / `parse_rule_id`（從 preload 或當前 active rule）

### 5.3 deps

```json
{
  "dependencies": {
    "recharts": "^2.13",
    "react-diff-viewer-continued": "^4"
  }
}
```

### 5.4 Stats tab 互動

- 進 tab 預設 range=7d
- 切 range 觸發 `useLogTypeStats(id, newRange)` refetch
- enabled=false → 顯示 banner「Stats 功能需啟用 ClickHouse（環境變數 `CLICKHOUSE_URL`）」+ 不 render chart
- 0 資料（範圍內無事件）→ chart 顯示空態文字「過去 N 天無 parse 紀錄」

### 5.5 Versions tab 互動

```
┌────────────────────────────────────────────────────────────┐
│ Versions                                                   │
├────────────────────────────────────────────────────────────┤
│ v3  [draft]      amos    2 hours ago    [Promote] [View] [Diff]│
│ v2  [published]  amos    3 days ago     [View] [Diff]          │
│ v1  [archived]   amos    1 week ago     [View] [Diff]          │
└────────────────────────────────────────────────────────────┘
```

- Promote 按鈕只對 status=draft 顯示；點擊跳 confirm dialog 顯示「v3 將取代 v2 成為 current rule，v2 會 archive。確定？」
- Diff 按鈕跳 modal，左 dropdown 預設「上一版」、右 dropdown 預設「當前」，react-diff-viewer 顯示
- View 按鈕跳 modal 純檢視 vrl_code（read-only CodeMirror）
- Promote 成功 → toast「v3 已 published」、invalidate `["library","log-type-detail",id]` 與 `["library","versions",id]`

---

## 6. 資料流

### 6.1 Parse stats 寫入流程

```
POST /api/v1/analyzer/parse
    │
    ▼
ParserService.run(vrl, logs, engine)
    │ measure latency_ms
    ▼
Build ParseEvent (含 hash, user_id, log_type_id?, parse_rule_id?)
    │
    ▼
BackgroundTasks.add_task(StatsRecorder.record, event)
    │
    ▼
Response 立即送回客戶端
    │（response 已送出，BackgroundTask 執行）
    ▼
StatsRecorder.record:
   if client is None → return
   else: client.insert("parse_events", [row])
   on exception: log warning, swallow
```

### 6.2 Coverage 顯示流程（vendor 詳情頁）

```
useProductDetail(vendor, product) → PG，拿 log_types 列表
useProductCoverage(vendor, product, "7d") → 後端 service
    │
    ▼
StatsService.product_coverage:
   先從 PG 拿 log_type_ids
   一次 CH query: SELECT log_type_id, day, sum(success)/sum(total) AS rate
                  FROM parse_events
                  WHERE log_type_id IN ({ids}) AND ts >= now() - 7d
                  GROUP BY log_type_id, toDate(ts)
   build per-log-type sparkline
    │
    ▼
ProductCoverage { log_types: [{ id, sparkline, success_rate_avg, volume }] }
    │
    ▼
ProductDetail render：每個 log type row 取對應 sparkline
```

### 6.3 Promote 流程

```
User click Promote v3 → confirm dialog
    │ confirm
    ▼
POST /api/v1/library/parse_rules/{v3.id}/promote
    │
    ▼
ParseRuleService.promote in transaction:
   lock parse_rules row v3
   v3 status: draft → published
   if exists 舊 published v2: v2.status → archived
   lock log_types row, set current_parse_rule_id = v3.id, status = 'published'
   commit
    │
    ▼
DataResponse[ParseRuleRead]
    │
    ▼
toast「v3 已 published」
invalidate ["library","log-type-detail",id], ["library","versions",id]
```

---

## 7. 錯誤處理

| 情境 | 處理 |
|---|---|
| `CLICKHOUSE_URL` 未設 | StatsRecorder skip 寫入；StatsService.enabled=False，stats endpoints 回 `{enabled: false, ...}`；前端 Stats tab + sparkline 列顯示「需啟用 ClickHouse」灰字 |
| CH 寫入連線失敗 | StatsRecorder caught；structlog warning；BackgroundTask 結束。用戶 parse 完全無感 |
| CH 讀取失敗（service exception） | router 回 503；前端 Stats tab 顯示「暫時無法取得統計」+ 重試按鈕；sparkline 列顯示「—」 |
| Promote 一個 archived rule | service raise `ConflictError`，router 回 409，前端 toast「不可 promote 已歸檔版本」 |
| Promote 已是 published 的 rule | service idempotent return；前端 toast「已是當前版本」 |
| Promote 競爭（partial unique conflict） | SQLAlchemy IntegrityError → router 回 409 「已有其他人 promote 該版本」；前端 invalidate refetch 後再試 |
| Stats range 不在白名單 | Pydantic validator reject，422 |

---

## 8. 測試策略

### 8.1 Backend

| 層 | 測試內容 |
|---|---|
| `clickhouse.py` unit | mock settings；`init_clickhouse` 在 url=None 時 short-circuit、有 url 時呼叫 `get_async_client` 且 ensure_schema 跑一次 |
| `stats_recorder` unit | mock CH client；client=None 時 record() no-op 不拋例外；正常時 row 欄位正確 mapping；CH 拋例外時被吞且 log warning |
| `stats_service` unit | mock CH client.query；計算 success_rate 正確；空資料回 0；enabled=False 時不打 CH |
| `parse_rule_service.promote()` unit | (a) draft no published → 直接設 published、log_type 更新；(b) draft 有 published → 舊 archived、新 published；(c) archived → ConflictError；(d) published → idempotent return |
| `parse_rule_service.promote()` integration | 真 PG，partial unique 衝突場景：兩 coroutine 同時 promote 同 log_type 不同 draft，第二個失敗 |
| `parse_router` | router test mock service，測 BackgroundTask 被 schedule（mock background.add_task）、ParseEvent 欄位正確 |
| `stats_router` | mock service，測 enabled=false 路徑回 200 + enabled=false、CH 失敗回 503 |
| `parse_rule_router.promote` | mock service，測 200 / 404 / 409 |
| CH integration | docker compose --profile stats up；寫一筆 → 讀回對得上 timestamp、欄位、hash bytes |
| Migration test | 0003 上 → 同 log_type 多筆 published 被整理成只有最新一筆 published、其餘 archived；partial unique 阻擋第二筆 published 寫入 |

### 8.2 Frontend

| 層 | 測試內容 |
|---|---|
| `coverage-sparkline` unit | 純 component test，input data → 對應 SVG path/rect 數量；空陣列空態 |
| `log-type-stats-tab` | render with mocked hook；切 range refetch；enabled=false 顯示 banner；0 資料空態文字 |
| `versions-tab` | 表渲染正確；Promote 按鈕只在 draft 顯示；Promote 點擊跳 confirm；mutation 完 refetch；archived rule 不顯示 Promote |
| `version-diff-modal` | 兩 dropdown 選取後 diff render；同版本 diff 顯示「無變更」 |
| Hooks (`useLogTypeStats`, `useProductCoverage`, `usePromoteParseRule`) | MSW mock；成功 / 503 / 409 / enabled=false 分支 |
| Playwright e2e | log type detail → Versions tab → Promote v3 → 看到 v2 archived、v3 published；Library overview sparkline 顯示資料；Stats tab 切 range chart refetch |

---

## 9. 本地開發

### 9.1 docker-compose 變更

```yaml
services:
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

volumes:
  chdata:
```

預設 `docker compose up` 不啟 ClickHouse；要用 Stats：`docker compose --profile stats up -d`。

### 9.2 Makefile 變更

```makefile
dev-stats:
	docker compose --profile stats up -d clickhouse
	@echo "ClickHouse on :8123, set CLICKHOUSE_URL in .env to enable Stats features"

test-int:
	docker compose --profile stats up -d
	# ...既有 integration test 指令...
```

### 9.3 .env.example

```
# ClickHouse (optional — required for Stats / Coverage features)
CLICKHOUSE_URL=http://logscope:logscope@localhost:8123/logscope
```

不設值時 Analyzer parse / Library 主功能完全不受影響，只是 Stats tab 與 sparkline 列顯示 disabled banner。

---

## 10. 驗收標準

- [ ] `make setup` 成功（不需要 ClickHouse 也能跑通主流程）
- [ ] `make test` 全綠（含 stats_recorder / stats_service / promote 新單元測試）
- [ ] `make test-int` 全綠（含 CH integration、migration 0003、partial unique 衝突）
- [ ] `make test-fe` 全綠（含 sparkline / stats-tab / versions-tab）
- [ ] `make test-fe-e2e` 全綠（含 Promote 流程）
- [ ] `make lint` 全綠
- [ ] `docker compose --profile stats up -d` + 設 `CLICKHOUSE_URL` 後：在 Analyzer parse 幾次 → log type Stats tab 看得到 timeline 與 totals
- [ ] vendor 詳情頁 log type 列表的 "Coverage 7d" 欄正確顯示 sparkline；0 資料時顯示空態
- [ ] log type Versions tab 顯示所有版本與正確的 status badge；Promote draft → 看到舊 published 變 archived、新版變 current
- [ ] Diff modal 任兩版比對顯示正確 vrl_code 差異
- [ ] 不啟動 ClickHouse / 不設 `CLICKHOUSE_URL` 時：Analyzer 仍能 parse、Library 列表仍能瀏覽、log type 詳情頁的 Samples / Fields tab 正常、只有 Stats tab 與 sparkline 列顯示 disabled banner
- [ ] Promote 在 partial unique 衝突時前端顯示 409 toast 並 refetch 列表

---

## 11. 風險與待確認

| 議題 | 處理 |
|---|---|
| `clickhouse-connect` async API 是 threadpool wrap 而非真 async I/O | C2 寫入頻次低、查詢資料量小，差別不顯著；若日後成瓶頸再評估 native protocol |
| ClickHouse server 第一次啟動時 schema 還沒建，並發第一筆 insert 可能失敗 | `init_clickhouse` 在 lifespan 一次跑 `ensure_schema`（CREATE TABLE IF NOT EXISTS），啟動完才開放 traffic |
| Migration 0003 把現有重複 published 整理成 archived | 開發 / Demo 環境影響小，未來上 prod 前要再確認資料一致 |
| Promote 的 partial unique 在 race 下會拋 IntegrityError | 已在 service 設計納入；router 轉 409，前端 invalidate refetch |
| BackgroundTasks 在 server 重啟時會丟失 in-flight task | 接受 — fire-and-forget by design；之後若量大再升級 Redis Stream |
| Demo 沒裝 ClickHouse 的人完全看不到 Stats 功能 | 設計就接受；Stats 是 optional value-add，主功能不受影響 |
| ClickHouse 25.x 對 ARM Mac 的 image 支援 | image `clickhouse/clickhouse-server` 官方支援 linux/arm64，M-series Mac 無問題 |
| C1 設計文件 v1.2 §8.5 寫的「Redis Stream + 30s batch worker」未實作 | C2 改用 BackgroundTasks；StatsRecorder interface 已預留升級空間，不算偏離設計，只是延後升級 |

---

## 12. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| D | Copilot | SSE streaming chat、各頁面 prompt 注入、三技能（VRL 生成、Log 解釋、Library 比對 inline）；可疊用 Versions tab 「LLM explain diff」 |
| E | LLM Pipeline | 爬文件、草稿、Review diff、source = `llm_generated` |
| 之後優化 | Fingerprint index 取代 / 補強 LLM match | 從 SAMPLE_LOG + FIELD_SCHEMA 建特徵；降低 LLM cost |
| 之後升級 | Redis Stream + worker batch ingestion | 當 BackgroundTasks 在實際負載下開始造成壓力時切換 |
