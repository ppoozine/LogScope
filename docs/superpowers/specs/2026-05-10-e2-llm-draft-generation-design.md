# LogScope — E2 LLM Draft Generation Spec

- 日期：2026-05-10
- 子專案編號：E2（E 系列「LLM Pipeline」第二步；E 系列分解為 E1/E2/E3 三個獨立 spec）
- 已完成前置：A 骨架、B Library 手動 CRUD、C1 Analyzer parse loop、C2 ClickHouse 統計、D1–D5 Copilot
- 相依：D-series 已建立 Anthropic SDK 整合與 prompt builder 慣例（Block 1 cached + Block 2 XML）
- 後續 spec：
  - **E1 — Doc Ingestion**：自動化 vendor 文件抓取（公開 URL fetcher + LLM 協助挖官方資料），E2 之後做
  - **E3 — Review UI**：`/review` 頁、diff 視覺、accept/reject UX，E1 之後做
- 上游文件：`docs/LogScope_Design_Document_v1.2.html`、`docs/superpowers/specs/2026-05-09-copilot-d2-design.md` §11

---

## 1. 範圍

E2 是 E 系列的第一個落地子專案。E 系列被分解成 E1（doc 抓取）、E2（draft 生成）、E3（review UI）三個獨立 spec，**E2 先做**理由：core 假設「LLM 寫得出可用 VRL」未驗證前，先做 E1 是賭機率，先做 E3 是空 queue UI。E2 落地後即可用 SQL 看 LLM 草稿、立即驗證假設。

### 1.1 進 E2

**新 module `app/modules/llm_pipeline/`**
- `docs` 表 + admin upload endpoint（E1 之後改為 crawler 寫入）
- `llm_generation_jobs` audit 表（紀錄每次 LLM call 的 input snapshot / output / error / cost）
- `POST /api/v1/llm-pipeline/drafts/generate` — 同步 endpoint，單次 Anthropic `messages.create` + tool-use 強制 structured output → VRL compile validate → 三表 transaction insert（log_type / field_schemas / parse_rule，皆 status=`llm_draft`、source=`llm_generated`）
- `prompt_builder` 沿用 D-series Block 1（cached persona + skill）+ Block 2（XML page_context）慣例

**Library schema 擴充**
- `LogTypeStatus` 加入 `"llm_draft"`、`LogTypeSource` 加入 `"llm_generated"`
- `ParseRuleStatus` 加入 `"llm_draft"`、新增 `parse_rule.source` 欄位（enum）
- 三表（log_type / parse_rule，**field_schema 不改**）新增 `source_job_id` FK 指向 `llm_generation_jobs`

**共用 refactor**
- Anthropic client 從 `app/modules/copilot/` 抽到 `app/core/deps.py` 的 `get_anthropic_client()`，copilot 與 llm_pipeline 共用 singleton
- VRL function cheatsheet 從 `copilot/services/prompt_builder._BLOCK1_VRL_GENERATE` 抽到 `copilot/services/_vrl_cheatsheet.py`，兩 module 共享避免 drift

**測試**：unit + integration（真 DB + mock anthropic），詳見 §6

### 1.2 不進 E2（明確留給 E1 / E3 / v2）

| 議題 | 留 |
|---|---|
| 自動爬取 vendor URL → markdown（含 SPA / robots / rate limit） | E1 |
| LLM 協助找 vendor 官方 doc URL | E1 |
| `/review` 頁、diff 視覺、accept/reject UX | E3 |
| Library detail 頁「AI 建庫」按鈕接到 generate endpoint | E3（review queue 存在後才接） |
| 大量批跑 / async job runner / 並行 | v2 |
| Doc RAG / chunking（截 top 20000 chars 不足時） | v2 |
| Per-field accept/reject in review | v2 |
| 同一 user rate limit 用 Redis（v1 用 in-memory） | v2 |

### 1.3 高階資料流（E2 階段）

```
[user 手動 POST /llm-pipeline/docs (markdown)]
                    ↓
                 docs 表
                    ↓
[user 手動 POST /llm-pipeline/drafts/generate (doc_id, product_id, hint?)]
                    ↓
        llm_generation_jobs.create(status=pending)
                    ↓
  Anthropic messages.create (sync, ~20s, tool-use structured output)
                    ↓
  parse tool input → self-consistency check → VRL compile validate
                    ↓
        ┌─ ok    → transaction:
        │           INSERT log_type   (status=llm_draft, source=llm_generated, source_job_id)
        │           bulk_replace field_schemas
        │           INSERT parse_rule (status=llm_draft, source=llm_generated, source_job_id)
        │           job.finish(succeeded, log_type_id, parse_rule_id, token usage)
        │         → 200 {log_type_id, parse_rule_id, job_id}
        │
        └─ fail  → job.finish(failed, error_code, error_message, raw_response[:4096])
                  → 4xx/5xx {job_id, error_code, error_message}
                    （無 DB writes 到 library 三表）
                    ↓
[reviewer 用 SQL 看 llm_draft 草稿；E3 之後接 /review 頁]
```

---

## 2. 資料模型變動

### 2.1 新表

#### `docs`

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | UUID PK | |
| vendor_id | UUID FK → vendors | 一份 doc 屬一個 vendor |
| url | varchar NULL | 來源 URL；E1 抓的有，E2 manual upload 可空 |
| title | varchar NULL | doc 標題 |
| content | text NOT NULL | markdown body |
| content_format | enum `doc_content_format` 值 `"markdown"` | 預留 `"html"` / `"pdf"` |
| fetched_at | timestamp | 內容取得時間 |
| fetched_by | enum `doc_fetched_by` 值 `"manual"` / `"crawler"` | E2 只有 manual |
| created_at, updated_at | timestamp | TimestampMixin |

Indexes：
- `unique(vendor_id, url) WHERE url IS NOT NULL`
- `(vendor_id, created_at DESC)` for vendor-scoped listing

#### `llm_generation_jobs`

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | UUID PK | |
| doc_id | UUID FK → docs | input |
| product_id | UUID FK → products | input |
| requested_by | UUID FK → users | input |
| status | enum `llm_job_status` 值 `"pending"` / `"succeeded"` / `"failed"` | |
| model | varchar NOT NULL | e.g. `claude-opus-4-7` |
| error_code | varchar NULL | 失敗時填，列舉值見 §5.4 |
| error_message | text NULL | 失敗時填 |
| raw_response | text NULL | 截 top 4096 chars 用於診斷 |
| input_tokens | int NULL | 來自 Anthropic response |
| output_tokens | int NULL | |
| cache_read_tokens | int NULL | |
| log_type_id | UUID NULL FK → log_types | 成功時填，作為 lineage 出口 |
| parse_rule_id | UUID NULL FK → parse_rules | 成功時填 |
| started_at | timestamp | |
| finished_at | timestamp NULL | 結束（成功或失敗）時間 |

Index：`(product_id, status, started_at DESC)`。

### 2.2 既有表擴充

| 表 | 改動 |
|---|---|
| `log_types` | enum `log_type_status` ADD VALUE `"llm_draft"`；enum `log_type_source` ADD VALUE `"llm_generated"`；新欄位 `source_job_id UUID NULL FK → llm_generation_jobs` |
| `parse_rules` | enum `parse_rule_status` ADD VALUE `"llm_draft"`；**新 enum** `parse_rule_source` 值 `"manual"` / `"llm_generated"`；新欄位 `source parse_rule_source NOT NULL DEFAULT 'manual'`；新欄位 `source_job_id UUID NULL FK → llm_generation_jobs` |
| `field_schemas` | **不改**。fields 是 log_type 附屬、lifecycle 跟隨 parent；review 不做 per-field accept/reject。E2 不需要 source 追蹤就能完整支援 partial accept（reviewer 改 fields 等同改 log_type，log_type 的 source 仍記錄起源） |

**為何不放 `source_doc_id` 在三表**：可透過 `source_job_id → llm_generation_jobs.doc_id` 拿到，避免多一份 denormalized FK 要同步。

### 2.3 Service-layer invariants（不放 DB constraint）

- `parse_rule.status = 'llm_draft'` ⇒ `source = 'llm_generated' AND source_job_id IS NOT NULL`
- `log_type.current_parse_rule_id` 只能指向 `status='published'` 的 parse_rule（E2 不變既有規則；llm_draft 不會被誤套到 production parse pipeline）

理由：DB-level cross-column constraint 維護成本高（migration 棘手 / debug 不直觀）；service 守住 invariant + integration test 涵蓋邊界 case 是更好的 trade-off。

### 2.4 Migration 順序

`llm_generation_jobs` 與 `log_types` / `parse_rules` 互相 FK 引用（jobs.log_type_id ↔ log_types.source_job_id；jobs.parse_rule_id ↔ parse_rules.source_job_id）— 形成 **circular FK**。處理方式：兩端都是 `NULL`，在最後一個 migration 統一 `ADD CONSTRAINT`。

1. `add_docs_table.py` — 建 docs 表 + 兩個 enum types（`doc_content_format`、`doc_fetched_by`）
2. `add_llm_generation_jobs_table.py` — 建 jobs 表 + `llm_job_status` enum；`log_type_id` / `parse_rule_id` 欄位先建為 `UUID NULL` **不加 FK constraint**
3. `extend_log_type_for_llm.py` — `ALTER TYPE log_type_status ADD VALUE 'llm_draft'`、`ALTER TYPE log_type_source ADD VALUE 'llm_generated'`、`ALTER TABLE log_types ADD COLUMN source_job_id UUID NULL`（**不加 FK constraint**）
4. `extend_parse_rule_for_llm.py` — `ALTER TYPE parse_rule_status ADD VALUE 'llm_draft'`、`CREATE TYPE parse_rule_source AS ENUM ('manual', 'llm_generated')`、`ALTER TABLE parse_rules ADD COLUMN source parse_rule_source NOT NULL DEFAULT 'manual'`、`ADD COLUMN source_job_id UUID NULL`（**不加 FK constraint**）
5. `add_llm_lineage_fk_constraints.py` — 統一 `ADD CONSTRAINT FOREIGN KEY` 四條：`log_types.source_job_id → llm_generation_jobs(id)`、`parse_rules.source_job_id → llm_generation_jobs(id)`、`llm_generation_jobs.log_type_id → log_types(id)`、`llm_generation_jobs.parse_rule_id → parse_rules(id)`

PostgreSQL 對 `ALTER TYPE ... ADD VALUE` 不 rebuild table、不影響既有 row，安全。

---

## 3. 後端架構

### 3.1 新 module 結構

```
app/modules/llm_pipeline/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── doc.py
│   └── llm_generation_job.py
├── repositories/
│   ├── __init__.py
│   ├── doc_repository.py
│   └── llm_generation_job_repository.py
├── services/
│   ├── __init__.py
│   ├── doc_service.py             # upload / dedup
│   ├── prompt_builder.py          # Block 1 (cached) + Block 2 (XML)
│   ├── llm_draft_service.py       # 核心 orchestration
│   └── vrl_validator.py           # thin wrapper over analyzer.vrl_runtime.compile_program
├── routers/
│   ├── __init__.py
│   ├── doc_router.py              # POST /llm-pipeline/docs
│   └── draft_router.py            # POST /llm-pipeline/drafts/generate
└── schemas.py
```

**為何新開 module 而不是塞進 `library`**：
1. `library` 是「資料展示 + 手動 CRUD」領域，schemas 已 322 行；混進 LLM call / job tracking / prompt 會破壞職責邊界
2. E1（crawler）是 ETL job、不是 library 概念；放 library 內愈做愈大
3. E3 review queue 是 cross-cutting 讀者，read 兩邊是 OK 的；但「產出 LLM draft」這個動作的領域屬於 llm_pipeline

### 3.2 共用 refactor

#### 3.2.1 Anthropic client 抽到 `app/core/deps.py`

目前 `app/modules/copilot/` 內有 anthropic client 建構與生命週期管理。E2 把它抽到 `app/core/deps.py`：

```python
# app/core/deps.py（新增）
@lru_cache(maxsize=1)
def _get_anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=settings.anthropic_api_key)

def get_anthropic_client() -> AsyncAnthropic:
    return _get_anthropic_client()
```

Copilot 與 llm_pipeline 共用同一 singleton，避免兩份 connection pool。Copilot 既有 dependency injection 改吃 `Depends(get_anthropic_client)`。

#### 3.2.2 VRL cheatsheet 抽出共享

從 `app/modules/copilot/services/prompt_builder.py` 的 `_BLOCK1_VRL_GENERATE` 把 VRL function cheatsheet 段（parse_syslog / parse_json / parse_key_value / parse_regex / parse_csv / split / to_int / to_float / to_bool / to_string / to_timestamp / del / exists / string + `!` vs `??` 規則 + 0.25 vs 0.32 差異）抽到 `app/modules/copilot/services/_vrl_cheatsheet.py`，export 為 `VRL_CHEATSHEET: str`。Copilot 與 llm_pipeline 兩處 import 共用，避免 cheatsheet 兩處 drift。

### 3.3 跨 module 互動

`llm_draft_service` 寫入 library 三表時直接用 **library 的 repositories**（不走 library service，避免觸發 publish 等 side effect）：
- `LogTypeRepository.create_with_lineage(...)` — 若不存在則新增
- `FieldSchemaRepository.bulk_replace(log_type_id, fields)` — 既有，沿用
- `ParseRuleRepository.create_with_lineage(...)` — 若不存在則新增

一個 async DB transaction 跨兩個 module 是合法的（inject 同一個 session）。新 repository 方法的細節由 plan 階段補。

### 3.4 `llm_draft_service.generate_draft` 主流程

**Transaction 邊界**：
- **TX-1**（`job_repo.create_pending`，獨立小 transaction）：先寫 `pending` job row、立即 commit；確保即使後續任何階段失敗，audit 都有紀錄。
- **TX-2**（library 三表 + job.finish(succeeded)，同一 transaction）：成功時原子寫入；失敗則整體 rollback、library 三表沒有殘餘 row。
- **TX-3**（`job_repo.finish_failed`，獨立小 transaction）：任何階段 raise 時呼叫；確保即使 TX-2 已 rollback 或從未進入，failure 紀錄仍能寫入。

實作上 repository 兩個方法 `create_pending` / `finish_failed` 各自開新 session（`async with session_factory() as new_session: ...`），不依賴 request-scope session 狀態。

```python
async def generate_draft(
    *, doc_id: UUID, product_id: UUID, requested_by: UUID, hint: str | None
) -> GenerationResult:
    doc = await doc_repo.get_or_404(doc_id)
    product = await product_repo.get_or_404(product_id)
    vendor = await vendor_repo.get_or_404(product.vendor_id)
    existing_log_types = await log_type_repo.list_by_product(product_id)

    # TX-1: pending job 立即落 DB
    job = await job_repo.create_pending(
        doc_id=doc_id, product_id=product_id, requested_by=requested_by,
        model=settings.llm_pipeline_draft_model,
    )
    response = None  # 用於 except 分支取 raw_response

    try:
        system_blocks = prompt_builder.build(
            vendor=vendor, product=product, doc=doc,
            existing_log_types=existing_log_types, hint=hint,
        )
        response = await anthropic_client.messages.create(
            model=settings.llm_pipeline_draft_model,
            max_tokens=4096,
            system=system_blocks,
            messages=[{"role": "user", "content": "Generate draft."}],
            tools=[DRAFT_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "submit_draft"},
        )
        draft = parse_tool_use(response)            # raises SchemaMismatchError
        check_self_consistency(draft)               # raises VrlFieldsDisjointError
        vrl_validator.validate(draft.vrl_code, draft.engine_version)  # raises VrlCompileError

        # TX-2: library 三表 + job.finish(succeeded) 同 transaction
        async with session.begin():
            log_type = await log_type_repo.create_with_lineage(
                product_id=product_id, status="llm_draft", source="llm_generated",
                source_job_id=job.id, **draft.log_type.model_dump(),
            )
            await field_schema_repo.bulk_replace(log_type.id, draft.fields)
            parse_rule = await parse_rule_repo.create_with_lineage(
                log_type_id=log_type.id, status="llm_draft", source="llm_generated",
                source_job_id=job.id, vrl_code=draft.vrl_code,
                engine_version=draft.engine_version, notes=draft.notes,
            )
            await job_repo.finish_succeeded(
                job.id, log_type_id=log_type.id, parse_rule_id=parse_rule.id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_read_tokens=response.usage.cache_read_input_tokens,
            )
        return GenerationResult.success(log_type, parse_rule, job)

    except (SchemaMismatchError, VrlFieldsDisjointError,
            VrlCompileError, AnthropicError, DbWriteError) as e:
        # TX-3: 獨立 transaction 寫 failed
        await job_repo.finish_failed(
            job.id,
            error_code=e.error_code,        # 各 exception class 自帶 error_code 屬性
            error_message=str(e),
            raw_response=truncate(response, 4096) if response is not None else None,
        )
        raise
```

### 3.5 Endpoints

#### `POST /api/v1/llm-pipeline/docs`

```
Body: {
  vendor_id: UUID,
  url: str | null,
  title: str | null,
  content_format: "markdown",
  content: str        # markdown body, max 200000 chars
}
Response: DataResponse[DocRead]
Auth: require login（E2 不分 role）
```

行為：插入 docs 表；若 `(vendor_id, url)` 已存在則 409 conflict。

#### `POST /api/v1/llm-pipeline/drafts/generate`

```
Body: {
  doc_id: UUID,
  product_id: UUID,
  hint: str | null    # optional free-text，最大 1000 chars
}
Response on success: DataResponse[{ log_type_id, parse_rule_id, job_id }]
Response on failure: ErrorResponse { job_id, error_code, error_message }
Auth: require login
Throttle: 同 user 每 60 秒最多 10 次（in-memory；§7）
Sync block: ~20s（前端應顯示 spinner，proxy timeout 須 ≥ 60s）
```

#### 不開的 endpoints

E2 不開 GET / list endpoint。Reviewer 用 SQL（或 admin shell）看 llm_draft 草稿。E3 才開 `/review` 相關 endpoints。

---

## 4. LLM I/O 合約

### 4.1 Tool schema (`submit_draft`)

```python
DRAFT_TOOL_SCHEMA = {
    "name": "submit_draft",
    "description": (
        "Submit a single LogType draft (metadata + fields + VRL parse rule) "
        "extracted from the vendor doc. Call this exactly once per request."
    ),
    "input_schema": {
        "type": "object",
        "required": ["log_type", "fields", "vrl_code", "engine_version", "notes"],
        "properties": {
            "log_type": {
                "type": "object",
                "required": ["name", "format"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 200},
                    "format": {"type": "string", "enum": ["syslog", "json", "cef", "leef", "csv", "other"]},
                    "transport": {"type": "string", "enum": ["syslog_udp", "syslog_tcp", "http", "file", "other"]},
                    "description": {"type": "string", "maxLength": 1000},
                },
            },
            "fields": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "required": ["field_name", "field_type"],
                    "properties": {
                        "field_name": {"type": "string", "minLength": 1, "maxLength": 100},
                        "field_type": {"type": "string", "enum": ["string", "int", "float", "bool", "timestamp", "ip", "object", "array"]},
                        "description": {"type": "string"},
                        "is_required": {"type": "boolean", "default": False},
                        "is_identifier": {"type": "boolean", "default": False},
                        "example_value": {"type": "string"},
                    },
                },
            },
            "vrl_code": {"type": "string", "minLength": 1},
            "engine_version": {"type": "string", "enum": ["0.25", "0.32"], "default": "0.32"},
            "notes": {
                "type": "string",
                "description": "Reviewer-facing notes — what was uncertain, alternative interpretations, fields not extracted",
                "maxLength": 2000,
            },
        },
    },
}
```

**設計理由**：

- **One tool（不拆成 log_type / fields / parse_rule 三個）**：三 artefact 互相依賴（fields 對齊 VRL extract、log_type 名稱對齊內容）；單 tool 強迫 LLM 一次思考完。三 tool 還增 ambiguity（LLM 不知哪個先呼叫）。
- **One log_type per call（不允許一次回多 log_type）**：一份 doc 可能涵蓋多 subtype（PAN-OS doc 同時描述 TRAFFIC / THREAT / URL）；user 用 hint 指定哪個 subtype，多 subtype 多次呼叫。理由：reviewer 一筆一筆 review；多 log_type 草稿讓 review queue 結構複雜。
- **field_name 不加 regex pattern**：library 既有 `FieldSchemaItem.field_name` 也沒 pattern，硬加會 reject 合理名字（e.g. `URL`、`X_Forwarded_For`）。snake_case convention 走 Block 1 文字 + `<existing_log_types>` 範例引導。
- **`tool_choice={"type":"tool","name":"submit_draft"}`**：強迫 LLM 必呼叫此 tool；schema 不符 SDK 直接 422 不需自寫 parser。

### 4.2 Block 1（cached persona + skill）

固定字串 ~3500–4500 chars，`cache_control: ephemeral`。內容：

- **Persona**：「You are LogScope's library builder. Read a vendor doc and propose ONE LogType draft via the `submit_draft` tool.」
- **Output rules**：
  - No prose response. Submit only via tool.
  - Do not invent fields not described in the doc.
  - snake_case field names matching `<existing_log_types>` convention.
  - For each claim, in `notes` 寫對應的 `〔依據：明確/推測/未知〕`（沿用 D1 慣例）
- **Process（順序）**：
  1. Identify the LogType in the doc. If doc covers multiple subtypes, pick the one matching `<hint>`. Otherwise pick the first / most prominent.
  2. List fields with: source position in doc / VRL extraction strategy / type.
  3. Write VRL targeting `engine_version` (default 0.32; if doc indicates older syntax or hint specifies, use 0.25).
  4. Cross-check: every field in `fields[]` must be assigned in `vrl_code`; every field assigned in `vrl_code` must appear in `fields[]`.
- **VRL function cheatsheet**：sourced from `_vrl_cheatsheet.VRL_CHEATSHEET`（同 copilot）。
- **You must NOT**：
  - 編造 doc 沒寫的 field
  - 編造 VRL function 名稱（cheatsheet 外的不能用）
  - hard-code secret / token / production hostname
  - 把同一個 field 拆兩個 fields[] entry
- **不確定處理**：在 `notes` 寫「無法確定：<原因>」，仍提交可運作的 VRL（即使欄位減少）；不要為填空硬編。
- **One end-to-end example**（PAN-OS TRAFFIC log）— 完整 doc snippet → 完整 tool input。

### 4.3 Block 2（per-request XML，no cache）

```xml
<vendor name="..." slug="..." />
<product name="..." slug="..." version="..." deploy_type="..." />

<existing_log_types count="3">
  <log_type name="PAN-OS TRAFFIC" format="syslog" transport="syslog_udp">
    <fields>
      <field name="src_ip" type="ip" required="true" />
      <field name="dst_ip" type="ip" required="true" />
      ...
    </fields>
  </log_type>
  ...
</existing_log_types>

<doc title="..." url="..." truncated_to="20000">
  <![CDATA[<markdown body, top 20000 chars>]]>
</doc>

<hint><![CDATA[<user free text，e.g. "focus on URL filtering subtype, target engine 0.25">]]></hint>
```

- `<existing_log_types>` 永遠 render（即使 0 個，render `count="0"` 空 element），讓 LLM 看到結構
- doc CDATA 內套用 `_safe_cdata`（沿用 copilot/prompt_builder 的 `]]>` escaping）
- `<hint>` 不存在則整個 element 省略

### 4.4 文件截斷

v1 截 top 20000 chars + `truncated_to="20000"` 屬性。Vendor doc 動輒 50K+ chars，full-doc + RAG/chunking 等 v2 再說（要等 quality data 來決定 chunking 策略）。

### 4.5 Engine version & hint

- 預設 `engine_version="0.32"`（也是 tool schema default）
- 不開 user-facing engine 選擇 input；要切 0.25 user 在 hint 寫「target engine 0.25」即可
- Hint 是 optional free-text、最大 1000 chars

### 4.6 Token & 成本預估（Opus 4.7）

- Block 1 cached ~4500 chars ≈ 1100 tokens（cache hit 後 charge cache read）
- Block 2 ~25000 chars ≈ 6000 tokens（doc 是大宗）
- Output ~2000 tokens
- Opus 4.7 pricing（$15 input / $75 output / $1.5 cache read per M）：
  - Cache hit：6000 × $15/M + 1100 × $1.5/M + 2000 × $75/M ≈ **$0.24 / draft**
- 驗證階段每天 20 次 ≈ $5/day
- Sonnet 4.6（~$0.05/draft）作為成本切換選項，等 quality data 出來再決定，**不在 E2 spec 內 hardcode**；走 `settings.llm_pipeline_draft_model` config

---

## 5. Validation & 錯誤處理

### 5.1 Validation 階段

依序執行；任一失敗即 short-circuit。

1. **Tool-use schema mismatch**：Anthropic SDK 422 → `error_code="schema_mismatch"`
2. **Self-consistency check**（service-layer）：
   - **若 vrl_code 含 splat-assign**（`. = parse_json!(...)` / `. = parse_syslog!(...)` / `. = parse_key_value!(...)`）：跳過 fields 交集檢查（fields 由 parser 隱式賦值到 root）
   - **否則**：至少有一個 `field.field_name` 字面字串出現在 `vrl_code` 任意位置（簡單 substring match；snake_case 名稱誤判機率低）。完全不交集 → `error_code="vrl_fields_disjoint"`
   - vrl_code 不含 inline-mode sentinel（`<|cursor|>` / `<|sel_start|>` / `<|sel_end|>`）→ `error_code="schema_mismatch"`
3. **VRL compile**（`vrl_validator.validate(vrl, engine)`）→ PyO3 exception → `error_code="vrl_compile_failed"`，error_message 帶 compiler diagnostic
4. **DB write transaction** → 失敗 rollback → `error_code="db_write_failed"`

### 5.2 Anthropic 暫時失敗

- 5xx / timeout / rate limit / auth → `error_code="anthropic_failed"`、不 retry
- v1 不做 retry：user 直接重試 endpoint；retry 需 idempotency key 才安全（避免兩份 draft），留 v2

### 5.3 Audit 落地

所有失敗 case 共用 `job_repo.finish(status="failed", ...)` 漏斗：
- `error_code` + `error_message`（短）
- `raw_response`：截 top 4096 chars（schema_mismatch / vrl_fields_disjoint / vrl_compile_failed 必填；anthropic_failed 通常無 response 可存）
- `db_write_failed` 不應該發生；若發生，error_message 帶 SQLAlchemy exception class name 即可

### 5.4 Router → HTTP status mapping

| error_code | HTTP | 語意 |
|---|---|---|
| `schema_mismatch` | 422 | LLM 輸出格式錯 |
| `vrl_fields_disjoint` | 422 | LLM fields[] 與 vrl_code 失聯 |
| `vrl_compile_failed` | 422 | LLM 給的 VRL 無法 compile |
| `anthropic_failed` | 502 | 上游 Anthropic 錯誤 |
| `db_write_failed` | 500 | E2 內部錯誤 |
| doc / product 不存在 | 404 | 前置條件 |
| throttle 超限 | 429 | §7 |

Response body：`{ job_id, error_code, error_message }`；user 拿 job_id 查 raw_response 看 LLM 到底回了什麼。

---

## 6. 測試策略

### 6.1 Unit

- `prompt_builder`：snapshot test Block 1 + Block 2 渲染
  - Block 2 含 `existing_log_types` 為空 / 有 3 個 / `hint` 有 / 沒有 / doc 超過 20000 chars 截斷
- `llm_draft_service.generate_draft`：mock anthropic_client + mock vrl_validator + 真 in-memory DB（沿用既有 conftest）
  - Happy path：三表 row 全在、status=`llm_draft`、source=`llm_generated`、source_job_id 設定、job 是 succeeded
  - 每個 error_code 路徑：schema_mismatch / vrl_fields_disjoint / vrl_compile_failed / anthropic_failed / db_write_failed
  - Transaction rollback：mock parse_rule_repo.create raise → log_type / field_schemas 也要 rollback、job 是 failed
  - Token usage：mock response 帶 usage → job row 有正確 token 數
- `vrl_validator`：少量 case 確認 PyO3 exception 翻譯為 `VrlCompileError`，不重複測 engine 本身
- `doc_service`：unique(vendor_id, url) 衝突 → 409
- 新 repository 方法：`create_with_lineage` / `list_by_product` 等

### 6.2 Integration（真 DB + mock anthropic）

- 完整 happy flow：upload doc → generate draft → assert 三表 row + job + 正確 lineage FK
- 失敗 flow：mock anthropic 回 schema 不符 → assert library 三表沒寫入 + job row 是 failed + raw_response 有截斷
- VRL compile fail：mock anthropic 回語法錯 VRL → 同上
- 既有 published log_type 不被覆蓋：先建 published log_type，再 generate 同 product；新 draft 是新 row 不衝突

### 6.3 不寫 e2e

E2 純 API、無前端改動；前端整合留 E3。

---

## 7. Risks & 限制

### 7.1 Sync HTTP block ~20s

- Reverse proxy / load balancer idle timeout 須 ≥ 60s
- 寫進 deployment note：「llm-pipeline endpoints 走 Anthropic 同步呼叫，proxy timeout 設 60s 起跳」
- 前端整合（E3）顯示 spinner + 預期文案「LLM 正在生成草稿，約需 20 秒…」

### 7.2 Cost runaway

- 同 user 連點 generate 會疊加成本
- E2 在 router 加 **in-memory throttle**：同 `requested_by` 每 60 秒最多 10 次，超出 429
- 實作走簡單 dict + lock（FastAPI worker 內），多 worker 部署時 limit 不精準但接受
- Redis-based 精準 throttle 留 v2

### 7.3 Doc 20000 字截斷可能漏關鍵段

- Mitigation 1：notes 欄位 + hint 機制讓 user 補充 / 引導
- Mitigation 2：review queue 是最後防線（即使 LLM 寫錯也會被 reviewer reject）
- E2 不解決，留 v2 RAG / chunking

### 7.4 LLM 幻覺 field

- Mitigation 1：Block 1 「You must NOT 編造 field」明確指令
- Mitigation 2：§5.1 self-consistency check（fields[] 與 vrl_code 至少一交集）catches 部分 case
- Mitigation 3：review queue
- 殘餘風險：LLM 可能寫出「看起來合理但 doc 沒提」的欄位；這是 LLM 本質限制，靠 reviewer judgment

### 7.5 `current_parse_rule_id` 仍是 `published` only

- E2 不變既有 invariant
- llm_draft 不會被誤套用到 production parse pipeline（C1 Analyzer 的 match / parse 都只看 published）
- 安全保證：即使 LLM 寫出爛 VRL 進 DB，也不會影響任何 production traffic

### 7.6 共用 refactor 的 blast radius

- Anthropic client 抽到 `app/core/deps.py`：copilot 既有 chat / inline endpoints 都依賴；E2 plan 的第一步要先做這個 refactor + run copilot integration tests 確認沒破
- VRL cheatsheet 抽出：copilot snapshot tests 會抓到字串差異；確認移動後 cheatsheet 內容 byte-identical

---

## 8. E1 / E3 預告

### E1 — Doc Ingestion（E2 之後）

- 自動化 vendor 文件抓取
- 公開 URL fetcher（static HTML / PDF）+ markdownify 入 `docs` 表
- LLM 協助挖官方資料（給 vendor 名 → LLM 推薦 doc URLs）
- v1 排除動態 SPA 文件（Playwright 留 v2）
- E2 已建好 `docs` schema + admin upload；E1 只是改寫 `fetched_by="crawler"` 路徑、不需動 schema

### E3 — Review UI（E1 之後）

- 新開 `/review` 路由
- 顯示 `llm_draft` queue（log_type / parse_rule 並排）
- Diff vs current published（沿用 C2 versions diff 元件）
- Operations：accept（promote 為 published、升 version）/ reject（archived）
- **無 auto-promote**（即使 LLM confidence 高也走 queue，避免 LLM 幻覺進 production）
- Library detail 頁「AI 建庫」按鈕在此 spec 接到 generate endpoint
- E2 已建好 status / source / source_job_id；E3 只是加 endpoints + frontend route
