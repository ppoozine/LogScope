# LogScope — Analyzer (Spec C1) Design

- 日期：2026-05-08
- 子專案編號：4（C1：Parse loop + Library 比對 + Library 雙向）
- 已完成前置：Plan 1a / 1b / 1c
- 後續 spec：C2（ClickHouse 統計）、D（Copilot）、E（LLM Pipeline）
- 上游文件：`docs/LogScope_Design_Document_v1.2.html` §4 Log 分析器、§8.2 VRL 執行環境
- POC 參考：`/Users/amos/Documents/side-projects/pyvrl-playground`

---

## 1. 範圍

### 1.1 進 v1（C1）

**Parse loop（A）**
- VRL editor（CodeMirror 6 + 自寫 simple syntax）
- Raw log 輸入（textarea，多行）
- Parse 結果預覽（按 identifier / event / numeric 分組）
- Engine 版本選擇（0.25 / 0.32），預設 0.32
- 400ms debounce 自動 parse
- Compile error 顯示在 VRL 編輯器；runtime error 顯示在對應結果列

**Library 比對（B）**
- Match bar 在三欄上方
- raw log 改動 → 1000ms debounce → LLM 回 top 3 候選（vendor/product/log_type + 信心 % + 簡述理由）
- 「套用規則」按鈕：拉那個候選的 current PARSE_RULE 與第一筆 SAMPLE_LOG 進編輯器
- 顯式「Match」按鈕（不等 debounce 立刻打）

**Library 雙向（C）**
- **「在 Analyzer 試打」**：Library 詳情頁觸發，URL 帶 `log_type_id` + `sample_id` → Analyzer mount 時 server-side fetch 載入 VRL + sample
- **「存回 Library」**：當 Analyzer 有 `log_type_id` context 時 enable，POST 建新 PARSE_RULE draft（version+1），用戶看到 toast「已建立 v3 草稿」
- **「存為 sample」**：當 Analyzer 有 `log_type_id` context 時 enable，POST 一筆 SAMPLE_LOG（label dropdown）
- 沒 context 時兩個按鈕 disabled，hover 顯示「需要從 Library 詳情頁進入」

**狀態 persistence**
- localStorage key `analyzer:state` 存 `{vrl, logs, engine_version}`
- 切走再回來，自動還原（除非 URL 帶 `log_type_id` 則覆蓋）

**VRL engine packaging**
- POC 的 `engine/v25` + `engine/v32` Rust crate **搬進 LogScope** repo 頂層
- 用 maturin 建 wheel，`pyproject.toml` 的 `[tool.uv.sources]` 用 path 引用
- 文件化打包流程，新增 VRL 版本時 copy + 改幾行即可（見 §6）

### 1.2 不進 C1（留給 C2 / D / E）

| 議題 | 後續 spec |
|---|---|
| ClickHouse 寫 parse 統計（次數 / 成功率 / latency） | C2 |
| ClickHouse 連線層 + Redis batch worker | C2 |
| Fingerprint index 替代或補強 LLM match | 之後優化 |
| VRL 編輯器內聯 LLM 建議（⌘K 寫 VRL） | D |
| LLM 解釋 log / 解釋 VRL | D |
| 文件爬取 → LLM 草稿 → Review 流程 | E |
| Sample log 大量 import（CSV / 檔案上傳） | 視需求 |

---

## 2. 後端架構

### 2.1 `app/modules/analyzer/`

```
app/modules/analyzer/
├── __init__.py
├── models/
│   └── __init__.py             # 暫無 ORM model（C1 不寫 DB）
├── services/
│   ├── __init__.py
│   ├── vrl_runtime.py          # 從 POC 搬：包 PyO3 binding，提供 compile_program(source, engine)
│   ├── parser_service.py       # 從 POC 搬 + 適配：run(vrl, logs, engine) → ParseResponse
│   ├── match_service.py        # LLM-based vendor/product 比對
│   └── prompt_builder.py       # 建 Anthropic prompt + cache controls
├── routers/
│   ├── __init__.py
│   ├── parse_router.py         # POST /analyzer/parse
│   └── match_router.py         # POST /analyzer/match
└── schemas.py                  # ParseRequest/Response, MatchRequest/Response
```

### 2.2 Endpoints

#### `POST /api/v1/analyzer/parse`

```
Body: {
  vrl_code: str,
  logs: list[str],            # 每行一筆 raw log；空字串會被過濾
  engine_version: "0.25" | "0.32"
}

Response: DataResponse[ParseResponse]
ParseResponse = {
  kind: "ok" | "compile_error" | "empty",
  engine: "0.25" | "0.32",
  compile_error?: str,        # kind == compile_error 時
  summary?: { total: int, success: int, error: int },
  results?: [{ index: int, input: str, status: "success" | "error", output?: dict, error?: str }]
}
```

行為與 POC 完全相同（直接搬 service 過來），只多了一層 LogScope 的 DataResponse 包裹。每次請求 logs 上限 500 行（在 schema 用 `Field(max_length=500)`），避免一次 compile 太久。

#### `POST /api/v1/analyzer/match`

```
Body: {
  raw_log: str,               # 第一筆即可，最多取前 500 字元送 LLM
  top_k: int = 3
}

Response: DataResponse[MatchResponse]
MatchResponse = {
  candidates: [{
    vendor_slug: str,
    product_slug: str,
    log_type_id: UUID,
    log_type_name: str,
    confidence: float,        # 0.0 ~ 1.0
    reason: str               # LLM 給的一句解釋
  }]
}
```

實作流程：
1. `MatchService.match(raw_log, top_k)` 從 DB 抓所有 LogType（**包含 draft 與 published 都納入候選**，含 vendor.name + product.name + format）做成「候選清單」
2. 用 prompt_builder 建 Anthropic prompt：system 是「Library 候選清單」用 cache（5 分鐘 TTL），user 是「raw log」+ 要求 JSON 格式回應
3. 解析 LLM JSON 回應，比對 log_type_id 是否真存在（防 LLM 幻覺），按 confidence 排序回前 top_k
4. 沒登入或 LLM key 缺失 → 回空 candidates 陣列（不擋使用）

### 2.3 dependencies

新加進 `pyproject.toml`：

```toml
[project]
dependencies = [
  # ...既有...
  "anthropic>=0.40",
  "pyvrl-playground-v25",
  "pyvrl-playground-v32",
]

[tool.uv.sources]
pyvrl-playground-v25 = { path = "engine/v25" }
pyvrl-playground-v32 = { path = "engine/v32" }
```

`.env.example` 補：

```
ANTHROPIC_API_KEY=
LLM_MATCH_MODEL=claude-haiku-4-5-20251001
```

`Settings`（`app/core/config.py`）對應加：

```python
anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
llm_match_model: str = Field("claude-haiku-4-5-20251001", alias="LLM_MATCH_MODEL")
```

### 2.4 LLM prompt 設計

System prompt（用 prompt cache，5min TTL）：

```
You are an expert at identifying log sources by their format. You will
be given a raw log line and a catalog of known vendor/product/log-type
combinations. Identify which (if any) candidates from the catalog best
match the log line. Respond with ONLY valid JSON in this shape:

{
  "candidates": [
    {
      "log_type_id": "<uuid from catalog>",
      "confidence": 0.0~1.0,
      "reason": "<one short sentence in 繁體中文>"
    }
  ]
}

If no candidate matches, return {"candidates": []}.
Sort by confidence descending. At most {{top_k}} entries.

Catalog:
{{ for each log_type: id, vendor_slug/product_slug, log_type_name, format, transport, sample if any }}
```

User message（每次都不一樣，不 cache）：

```
Raw log:
<first 500 chars of raw_log>

Identify the best candidates.
```

---

## 3. 前端架構

### 3.1 `/analyzer` 頁面

**File**: `web/app/(authed)/analyzer/page.tsx` — server component

```tsx
type SearchParams = { log_type_id?: string; sample_id?: string };

export default async function AnalyzerPage({ searchParams }) {
  const sp = await searchParams;
  let preload = null;
  if (sp.log_type_id) {
    // server-side fetch log_type detail（含 fields/current_parse_rule/samples）
    preload = await fetchLogTypeDetail(sp.log_type_id, sp.sample_id);
  }
  return <AnalyzerView preload={preload} />;
}
```

**File**: `web/components/analyzer/analyzer-view.tsx` — client component（owns parse + match state）

布局：

```
┌─────────────────────────────────────────────────────────────┐
│ MatchBar  [Palo Alto·PAN-OS·Traffic 94%][Fortinet 61%] [套用] [Match]│
├─────────────────┬─────────────────┬─────────────────────────┤
│ EditorPane      │ LogPane         │ ResultPane              │
│ <CodeMirror>    │ <textarea>      │ 識別欄位                │
│ Engine: ▼       │                 │ 事件欄位                │
│ ✓ ok / ✗ N行錯  │                 │ 數值欄位                │
│                 │                 │ [存回 Library][存為 sample]│
└─────────────────┴─────────────────┴─────────────────────────┘
```

### 3.2 主要 components

| 路徑 | 職責 |
|---|---|
| `web/components/analyzer/analyzer-view.tsx` | 頂層 client component，握 state、debounce、調 hooks |
| `web/components/analyzer/editor-pane.tsx` | 包 CodeMirror 6 + 引擎 selector + parse error indicator |
| `web/components/analyzer/log-pane.tsx` | textarea + clear 按鈕 + 行數顯示 |
| `web/components/analyzer/result-pane.tsx` | 三段分組（識別/事件/數值），「存回 Library」「存為 sample」按鈕 |
| `web/components/analyzer/match-bar.tsx` | top 3 候選 + 套用 + 顯式 Match 按鈕 |
| `web/components/analyzer/vrl-syntax.ts` | CodeMirror 6 streamLanguage：VRL keywords / fields / strings / comments |
| `web/lib/api/queries/analyzer.ts` | `useParse(filters)` debounced query、`useMatch()` mutation、`useLogTypeDetail(id)` |

### 3.3 CodeMirror 6 wrapper

```tsx
import CodeMirror from "@uiw/react-codemirror";
import { vrlLanguage } from "@/components/analyzer/vrl-syntax";

<CodeMirror
  value={vrl}
  extensions={[vrlLanguage]}
  theme="dark"
  onChange={(v) => setVrl(v)}
  basicSetup={{ lineNumbers: true, highlightActiveLine: true, foldGutter: false }}
/>
```

`vrl-syntax.ts` 用 `@codemirror/language` 的 `StreamLanguage.define(...)`，token rules：
- comments: `#` 開頭
- string: 雙引號
- keyword: `if`、`else`、`null`、`true`、`false`、`del`、`exists`
- builtin: VRL stdlib functions（從 POC keyword list 抽）
- field-access: `.field_name`

### 3.4 觸發時機與 debounce

| 動作 | 觸發 | Debounce |
|---|---|---|
| Parse | VRL / logs / engine_version 任一改動 | 400ms |
| Match | logs 改動 | 1000ms |
| 顯式 Match 按鈕 | onClick | 0ms（立刻打） |
| 「套用規則」 | onClick | 0ms |

實作用 [`useDebouncedValue`](https://www.npmjs.com/package/use-debounce) 或自寫 hook。

### 3.5 狀態 persistence

```tsx
useEffect(() => {
  // 讀 localStorage 還原（除非 preload 有 log_type_id）
  if (preload) return;
  const raw = localStorage.getItem("analyzer:state");
  if (raw) restore(JSON.parse(raw));
}, []);

useEffect(() => {
  localStorage.setItem("analyzer:state", JSON.stringify({ vrl, logs, engine_version }));
}, [vrl, logs, engine_version]);
```

### 3.6 Library 雙向

**「在 Analyzer 試打」按鈕在詳情頁**（從 Plan 1c `<VrlDisplay>` / `<SampleList>`）：

```tsx
<Link href={`/analyzer?log_type_id=${lt.id}&sample_id=${s.id}`}>在 Analyzer 試打</Link>
```

server component 拿 `log_type_id` → fetch nested detail → 把 VRL + sample 注入 `<AnalyzerView preload={...}>`。Client 用 preload 覆蓋 localStorage。

**「存回 Library」**：

```tsx
const save = useMutation(({ vrlCode }) =>
  apiFetch(`/api/v1/library/log_types/${logTypeId}/parse_rules`, {
    method: "POST",
    body: { vrl_code: vrlCode, engine_version, notes: null },
  })
);
```

成功後彈 toast；refetch product detail（若用戶後續切回 Library）。

**「存為 sample」**：dialog 選 label（normal/edge_case/error）→ POST `/log_types/{id}/samples` body 用第一行 raw_log。

### 3.7 deps

```json
{
  "dependencies": {
    "@codemirror/state": "^6",
    "@codemirror/view": "^6",
    "@codemirror/language": "^6",
    "@codemirror/commands": "^6",
    "@codemirror/lang-javascript": "^6",
    "@uiw/react-codemirror": "^4",
    "use-debounce": "^10"
  }
}
```

---

## 4. 資料流

### 4.1 Parse 流程

```
User 改 VRL or Logs
    │ 400ms debounce
    ▼
useParse({vrl, logs, engine})
    │ TanStack Query mutation
    ▼
POST /api/v1/analyzer/parse
    │
    ▼
ParserService.run(vrl, logs, engine)
    │ compile once → remap each line
    ▼
ParseResponse { kind, summary, results }
    │
    ▼
ResultPane render (識別/事件/數值 分組)
```

「識別/事件/數值」分組：根據 LogType 的 FIELD_SCHEMA 判斷 — 若有 `log_type_id` context，server-side fetch fields 對 result key 標記 is_identifier；若沒 context（cold start），純按 type heuristic：`int|float` → 數值；其他 → 事件。

### 4.2 Match 流程

```
User 改 logs 或點 Match
    │ 1000ms debounce or 0ms
    ▼
useMatch({raw_log: logs[0]})
    │
    ▼
POST /api/v1/analyzer/match
    │
    ▼
MatchService.match(raw_log, top_k=3)
    │ DB query: all LogTypes
    │ build prompt (cached system + uncached user)
    ▼
Anthropic API (Claude Haiku 4.5)
    │ JSON response
    ▼
parse + validate log_type_id 真實存在
    ▼
sort by confidence, top 3
    ▼
MatchBar render candidates
```

### 4.3 「套用規則」

```
User click 套用 (in MatchBar)
    │
    ▼
client navigate /analyzer?log_type_id=<id>&sample_id=<first sample>
    │
    ▼
Server component re-fetch detail
    │
    ▼
preload = { log_type_id, vrl_code, engine_version, sample_raw_log }
    │
    ▼
Client overwrites localStorage with preload, sets state
```

### 4.4 「存回 Library」

```
User edits VRL in Analyzer (with log_type_id context)
    │
    ▼
Click 存回 Library button
    │
    ▼
POST /library/log_types/{id}/parse_rules
    body: { vrl_code, engine_version, notes: "via Analyzer" }
    │
    ▼
Server creates new draft (version+1)
    │
    ▼
Toast「已建立 v3 草稿」
    invalidate ["library","product-detail",vendorSlug,productSlug]
```

---

## 5. 錯誤處理

| 情境 | 處理 |
|---|---|
| VRL compile error | `ParseResponse.kind = "compile_error"`、訊息顯示在 EditorPane 底部紅字 + 設置 CodeMirror diagnostic（如可解析錯誤行號） |
| 個別 log runtime error | 該 result 標 `status: "error"`，ResultPane 顯示紅色框 + error 訊息 |
| Match LLM 無 key / quota / 失敗 | service raise → router 回 503，前端 MatchBar 顯示「無法比對」灰字，不擋 parse |
| 「存回 Library」遇 conflict（current rule already published） | 後端已是 409，前端 toast 顯示錯誤訊息 |
| logs 行數 > 500 | 422 with detail，前端 textarea 上顯示「最多 500 行」紅字 |
| LLM 回非 JSON 或 schema 不對 | 後端 caught，回空 candidates；log structlog warning |

---

## 6. VRL Engine Packaging

POC 的 `engine/v25` 與 `engine/v32` 是 Rust crate（PyO3 + maturin），整個 crate 搬進 LogScope **repo top-level** `engine/v25/`、`engine/v32/`。

### 6.1 目錄結構（每個 version 都長一樣）

```
engine/v25/
├── Cargo.toml          # [package].name = pyvrl_playground_v25, vrl = "0.25.0"
├── pyproject.toml      # name = pyvrl-playground-v25, build-backend = maturin
└── src/
    ├── lib.rs          # PyO3 module: Transform class with __new__(source) + remap(data)
    └── value.rs        # VRL Value ↔ Python 雙向轉換
```

### 6.2 為什麼一個 version 一個 crate

不能在同一個 process 同時 link 兩個版本的 `vrl` crate（Rust 的 crate 不可同時存在多 version 在 single binary）。所以**每個 VRL 版本要編成一個獨立的 cdylib**（不同 cdylib name → 不同 .so → Python 可以同時 import 兩個 module）。

### 6.3 Build dependencies

- **Rust toolchain**：`rustup toolchain install stable`（macOS / Linux）
- **maturin**：python build backend，`uv sync` 會自動帶
- `abi3-py38` feature：build 一次，跑得起 CPython >= 3.8（包括 3.13 / 3.14）

### 6.4 Build 流程

開發期：

```bash
# 在 LogScope repo 根目錄
cd engine/v25 && uv run maturin develop --release && cd ../..
cd engine/v32 && uv run maturin develop --release && cd ../..
```

`maturin develop` 把 .so 安裝到 `.venv/lib/python3.13/site-packages/`，之後 `import pyvrl_playground_v25` 就能用。

CI / production：

```bash
cd engine/v25 && maturin build --release --out ../../wheels/
cd engine/v32 && maturin build --release --out ../../wheels/
```

產生 `wheels/pyvrl_playground_v25-0.1.0-cp38-abi3-*.whl` 等檔；deploy 時 `pip install wheels/*.whl`。

### 6.5 在 LogScope `pyproject.toml` 引用

```toml
[project]
dependencies = [
  "pyvrl-playground-v25",
  "pyvrl-playground-v32",
]

[tool.uv.sources]
pyvrl-playground-v25 = { path = "engine/v25" }
pyvrl-playground-v32 = { path = "engine/v32" }
```

`uv sync` 看到 source 是本地路徑會自動跑 maturin build。第一次 sync 會花 1-2 分鐘編 Rust。

### 6.6 新增 VRL 版本（例如 0.33）

1. **Copy** `engine/v32/` → `engine/v33/`
2. 改 `engine/v33/Cargo.toml`：
   - `[package].name = "pyvrl_playground_v33"`
   - `[lib].name = "pyvrl_playground_v33"`
   - `vrl = "0.33.0"`
3. 改 `engine/v33/pyproject.toml`：
   - `[project].name = "pyvrl-playground-v33"`
   - `[tool.maturin].module-name = "pyvrl_playground_v33"`
4. 改 `engine/v33/src/lib.rs`：把唯一的 `#[pymodule] fn pyvrl_playground_v32` rename 成 `pyvrl_playground_v33`（PyO3 規定 function name 必須等於 module name）
5. 在 LogScope `pyproject.toml`：
   - `dependencies` 加 `pyvrl-playground-v33`
   - `[tool.uv.sources]` 加 `pyvrl-playground-v33 = { path = "engine/v33" }`
6. 在 `app/modules/analyzer/services/vrl_runtime.py` 註冊：
   ```python
   import pyvrl_playground_v33
   _ENGINES["0.33"] = pyvrl_playground_v33
   ```
7. 在 `app/modules/library/schemas.py` 把 `EngineVersion` Literal 加 `"0.33"`
8. `uv sync` → 自動 build → `make test` 確認過了

### 6.7 vrl crate 的 Rust API 變更怎麼處理

VRL upstream 的 Rust API 在 minor 版本之間有時會 break（例如 0.25 → 0.32 中 `compile`/`Program`/`Context` 等 type 簽名有變）。`engine/v25/src/lib.rs` 與 `engine/v32/src/lib.rs` 不完全一樣，正是因應這些差異。

新增版本時：
1. 先 `cd engine/v33 && cargo check` 試編。如果通過，沒事
2. 如果 cargo 報錯：上 [vrl crate docs.rs](https://docs.rs/vrl/) 看新 API → 修 `lib.rs`
3. 通常需要修的是 `compile()`、`Context::new()`、`TargetValue` 的 field

---

## 7. 測試策略

### 7.1 Backend

| 層 | Test 內容 |
|---|---|
| `parser_service` unit | mock POC engine module，測 wrap_lines、compile error path、runtime error per line、empty input |
| `match_service` unit | mock Anthropic SDK，測 prompt 組裝、JSON 解析、log_type_id 不存在過濾、empty Library 處理 |
| `prompt_builder` unit | 直接斷 prompt 字串內容（system 含 catalog，user 含 raw_log，tool: "json"） |
| `parse_router` | router test mock service，測 422 logs 太多、200 success、500 unexpected |
| `match_router` | 同上 + 測 503 LLM 失敗時降級 |
| Integration | 真 PyO3 引擎 + 真 DB（不打 LLM）：跑「貼 PAN-OS 樣本 + 簡單 VRL → 200 with results」一條完整 flow |

### 7.2 Frontend

| 層 | Test 內容 |
|---|---|
| `vrl-syntax.ts` unit | 給字串輸入，測 token classify 結果（comment / string / keyword / field-access） |
| `editor-pane` component | render、改值觸發 onChange、engine selector 切換 |
| `log-pane` component | 行數正確、清空按鈕 |
| `result-pane` component | 三段分組 render、按鈕在沒 log_type_id 時 disabled |
| `match-bar` component | 顯示候選、套用按鈕觸發 navigate（mock router） |
| `analyzer-view` integration | 整頁 with mocked hooks，測 debounce 與 state 連動 |
| Hooks (`useParse`, `useMatch`) | MSW mock backend，測成功 / 422 / 503 |
| Playwright e2e | 1 條 happy path：登入 → /library/[v]/[p] → 「在 Analyzer 試打」→ /analyzer 載入 VRL + sample → 看到 Parse 結果 → 「存回 Library」→ Library 詳情頁刷新看到 v2 |

---

## 8. 本地開發

### 8.1 docker-compose 變更

無。C1 不啟用 ClickHouse（C2 才啟用）。沿用 1c 的 PG + Redis。

### 8.2 Makefile 變更

不需新增 target；`make dev-all` 包含 backend 自動 import VRL engines。第一次 `uv sync` 多花 1-2 分鐘 build Rust。

新增 helper：

```makefile
build-engines:
	cd engine/v25 && maturin develop --release
	cd engine/v32 && maturin develop --release
```

供開發者修改 Rust 後手動重 build。

### 8.3 .env.example 新增

```
# Anthropic（Match bar 用）
ANTHROPIC_API_KEY=
LLM_MATCH_MODEL=claude-haiku-4-5-20251001
```

`ANTHROPIC_API_KEY` 沒設值時 Match bar 一律回空候選 — 不擋使用 Analyzer 的 parse loop（讓沒 key 的人也能跑 demo）。

---

## 9. 驗收標準

- [ ] `make setup`（`uv sync` 自動 build 兩個 Rust crate）成功
- [ ] `make test` 全綠（含 analyzer 新單元測試）
- [ ] `make test-int` 全綠（含 analyzer integration 測 real PyO3 engine）
- [ ] `make test-fe` 全綠（含 analyzer 元件測試）
- [ ] `make test-fe-e2e` 全綠（含 Library → Analyzer → 存回流程的 spec）
- [ ] `make lint` 全綠
- [ ] `/analyzer` 開頁面後：貼 PAN-OS Traffic CSV 樣本 + 簡單 VRL → 看到 ✓ parse ok 與三段欄位
- [ ] 同一頁面切換 engine 0.25 / 0.32 都能 parse 同樣 VRL
- [ ] Match bar 在 raw log 變更後 1 秒內出現候選（前提：有 ANTHROPIC_API_KEY 且 Library 有資料）
- [ ] 從 Library 詳情頁「在 Analyzer 試打」進來，VRL + sample 自動載入
- [ ] 「存回 Library」成功後 Library 詳情頁出現 v2 draft
- [ ] localStorage 還原：在 Analyzer 改 VRL → 切到 /library → 切回 /analyzer → 內容還在
- [ ] 沒設 `ANTHROPIC_API_KEY` 時 Analyzer 還是能用，只是 Match bar 顯示「無法比對」

---

## 10. 風險與待確認

| 議題 | 處理 |
|---|---|
| VRL engine 第一次 `uv sync` 需要 Rust toolchain | README 與 setup task 加裝 rustup 提示。CI 圖片要預裝 Rust |
| PyO3 跨平台：本地 build 出來的 .so 不能跨 macOS / Linux | dev 都自己 build；prod 部署時用 Docker image 預先 build |
| Anthropic SDK 版本鎖定 | 用 `>=0.40,<1.0` 鎖小版號漂移範圍 |
| LLM 幻覺 log_type_id 不存在 | service 層過濾不存在的 id（已在 §2.2 設計） |
| Prompt cache 對 Anthropic 的 cost 影響 | system prompt 用 `cache_control`；catalog 變動才會 cache miss（vendor / product 列表變更頻率低） |
| 大量 SAMPLE_LOG 時 catalog 太長 | 每個 log_type 只取一筆 sample 第一行送進 prompt；預估 v1 規模 < 100 log types 不會炸 |
| `vrl` crate 0.33+ Rust API break | 加 VRL 版本時要看 docs.rs，可能要改 lib.rs。文件已記 §6.7 |
| Anthropic SDK 在 LLM 服務端要 server-side 用 | 不從前端直接呼叫 LLM，所有比對走 backend，避免 key 外漏 |

---

## 11. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| C2 | Analyzer ClickHouse stats | 接 ClickHouse 寫 parse 統計（次數 / 成功率 / latency / engine 用量），Redis batch worker 30s flush |
| D | Copilot | SSE streaming chat、各頁面 prompt 注入、三技能（VRL 生成、Log 解釋、Library 比對 inline） |
| E | LLM Pipeline | 爬文件、草稿、Review diff、source = `llm_generated` |
