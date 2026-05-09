# Copilot D2 — VRL 生成 + 三頁 context + Quick-buttons

**Spec ID**: D2
**狀態**: Draft
**建立日期**: 2026-05-09
**前置 Spec**: D1（Chat infra + SSE + Log 解釋技能）

---

## 1. 範圍

### 1.1 進 D2

D2 沿用 D1 的 SSE streaming + Anthropic 整合 + panel UI 基礎，擴張為「Analyzer 工作流可用、Library 三頁可諮詢」的 Copilot。一份 spec、拆三個 milestone（每個 milestone 結束開 PR、過了再進下一個）。

| Milestone | 內容 |
|---|---|
| **M1** | VRL 生成技能 + Insert into editor（diff dialog）+ 「✦ 生成 VRL」quick-button + safety banner + per-skill model override |
| **M2** | Library 三種 page_context（overview / product / versions sub-tab）+ 對應 hook |
| **M3** | 三顆 quick-button（比對 Library / 最佳化 VRL / 找異常值）+ 對應 skill prompt（vrl_optimize / anomaly） |

每個 milestone 都可獨立 ship、獨立測。

### 1.2 不進 D2（留 D3+）

| 留給 | 內容 |
|---|---|
| D3 | ⌘K inline VRL（CodeMirror ghost text + accept/reject）；VRL 修錯（點 parse error 行 → Copilot 修） |
| 未來 spec | LLM auto re-parse 校驗 loop（agent 模式）；真 review 頁路由（`/library/<v>/<p>/review`）；Redis session / cross-device sync |
| 不做 | Conversation summarization；structured output（tool_use）；多 vrl block 的多顆 Insert chip |

### 1.3 與 D1 spec 的偏離

| 偏離 | 理由 |
|---|---|
| `PageContext` 從 single-shape 改 discriminated union（`page` 為 discriminator） | D1 的 single-shape 在 D2 加完三頁後欄位差異太大；union 比一堆 `Optional` 清楚、validation 精準。對 D1 既有 analyzer payload backwards-compatible（`page` literal D1 已是必填且 frontend 已送） |
| `ChatRequest.skill` 從 `Literal["log_explain"]` 擴成 `SkillName = Literal["log_explain","vrl_generate","vrl_optimize","anomaly"]` | 自然延伸；D1 prompt builder 已 dispatch table 化過 |
| 多 4 個 settings（`LLM_COPILOT_VRL_MODEL`, `LLM_COPILOT_MAX_LIBRARY_PRODUCTS_IN_CONTEXT` 等） | 沿用 D1 命名空間 |

---

## 2. Milestones

### 2.1 M1 — VRL 生成技能 + Insert

**後端：**
- `SkillName` 加 `vrl_generate`
- `prompt_builder` 加 `_BLOCK1_VRL_GENERATE`：process steps 規範 LLM 輸出 ` ```vrl ... ``` ` 區塊；安全規範「不 hard-code secret」
- `ChatService` 加 `_model_for(skill)` + `skill_models` DI，支援 per-skill override
- Settings 加 `llm_copilot_vrl_model: str | None = None`

**前端：**
- `useCopilotStore` 加 `editorBridge`（register/unregister `setVrl` callback + `currentVrl`）、`pendingInsert`、`lastSkill`
- `useAnalyzerCopilotContext` 擴張：同時 register editor bridge
- `extractVrlBlock(content)`：regex 抽 ` ```vrl ... ``` ` 第一個 block
- `finalizeMessage` 改有實作：對 assistant message 抽 `vrlBlock` 寫進 message
- `<MessageBubble>`：assistant message 有 `vrlBlock` 時 render Insert chip
- `<InsertVrlDialog>`：line-level 純色 diff（無第三方 dep）+ Confirm/Cancel
- `<SafetyBanner skill={...} />`：VRL skill active 時顯
- `quick-buttons.tsx`：加「✦ 生成 VRL」按鈕（analyzer page + has logs）

### 2.2 M2 — 三頁 page_context

**後端：**
- `PageContext` 改 discriminated union：`AnalyzerPageContext` / `LibraryOverviewPageContext` / `LibraryProductPageContext` / `LibraryVersionsPageContext`
- `prompt_builder` 加 `_render_library_overview_xml` / `_render_library_product_xml` / `_render_library_versions_xml`
- 共用 helper `_safe_cdata(text)` 處理 `]]>` escape

**前端：**
- `types.ts` 對應後端 union；`use-streaming-chat.toBackendPageContext` 改 `switch (ctx.page)` 各自轉 snake_case
- 新增 `useLibraryOverviewCopilotContext`（mount 在 `library-overview-view`，依 filters + groups data 推 pageContext）
- 新增 `useProductDetailCopilotContext`（mount 在 `product-detail-view`，內部依 active log type + active sub-tab + diff modal open 切 `page` 字串為 `library_product` 或 `library_versions`）
- 沒有獨立 versions hook —— sub-tab 切換只改同 hook 的 payload，避免兩個 hook 同時 register 打架
- `<ContextStrip>` 改：依 `ctx.page` 切換 pill 顯示（每個 page 不同欄位）

### 2.3 M3 — 三 quick-buttons + 收尾

**後端：**
- `SkillName` 加 `vrl_optimize`、`anomaly`
- `prompt_builder` 加 `_BLOCK1_VRL_OPTIMIZE`、`_BLOCK1_ANOMALY`
- `ChatService.skill_models`：vrl_optimize 共用 `llm_copilot_vrl_model`（與 vrl_generate 同模型）；anomaly fallback default

**前端：**
- `quick-buttons.tsx`：加「比對 Library」「最佳化 VRL」「找異常值」三顆，依條件渲染
- 比對 Library 點下後：`apiFetch("/api/v1/analyzer/match", { raw_log: logs[0], top_k: 3 })` → 把 candidates 串成 user message → `send(text, { skill: "log_explain" })`
- 最佳化 VRL：`send` 預設 prompt + `skill: "vrl_optimize"`（reuse M1 的 vrl block + Insert 路徑）
- 找異常值：`send` 預設 prompt + `skill: "anomaly"`

---

## 3. 後端架構

### 3.1 Schemas（`app/modules/copilot/schemas.py`）

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field

SkillName = Literal["log_explain", "vrl_generate", "vrl_optimize", "anomaly"]


class ChatMessage(BaseModel):                # D1 不變
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ParseResult(BaseModel):                # D1 不變
    index: int
    status: Literal["ok", "error"]
    message: str | None = None


class MatchHypothesis(BaseModel):            # D1 不變
    vendor_slug: str
    product_slug: str
    log_type_name: str
    confidence: float


class AnalyzerPageContext(BaseModel):        # D1 既有 PageContext 改名
    page: Literal["analyzer"]
    vrl: str | None = None
    vrl_engine: str | None = None
    logs: list[str] = Field(default_factory=list)
    parse_results: list[ParseResult] = Field(default_factory=list)
    match_top_candidate: MatchHypothesis | None = None


class LibraryOverviewPageContext(BaseModel):
    page: Literal["library_overview"]
    filters: dict[str, str | None] = Field(default_factory=dict)   # {"status": "...", "q": "..."}
    vendor_count: int
    product_count: int
    # 「未建庫」list；前端從現有 OverviewProduct 推導：
    #   is_empty=true OR log_type_counts.published===0
    # 不需 prereq 擴 backend schema
    products_missing_parse_rule: list[str] = Field(default_factory=list)  # "vendor_slug/product_slug"


class FieldSummary(BaseModel):
    name: str
    type: str
    required: bool


class ActiveLogTypeContext(BaseModel):
    name: str
    fields: list[FieldSummary] = Field(default_factory=list)
    samples_count: int = 0
    parse_rule_head: str | None = None       # 前 60 行（粗 cap）


class LibraryProductPageContext(BaseModel):
    page: Literal["library_product"]
    vendor_slug: str
    product_slug: str
    product_status: str
    active_log_type: ActiveLogTypeContext | None = None


class VersionDiffContext(BaseModel):
    base_version: str
    head_version: str
    base_vrl: str | None = None
    head_vrl: str | None = None


class LibraryVersionsPageContext(BaseModel):
    page: Literal["library_versions"]
    vendor_slug: str
    product_slug: str
    log_type_name: str
    diff: VersionDiffContext | None = None


PageContext = Annotated[
    AnalyzerPageContext
    | LibraryOverviewPageContext
    | LibraryProductPageContext
    | LibraryVersionsPageContext,
    Field(discriminator="page"),
]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    skill: SkillName | None = None
    page_context: PageContext | None = None
```

驗證（D1 既有 + 新增）：
- 最後一則 `messages` 必須是 `role="user"`（router 入口檢查，回 422）
- `page` 不在四個 literal → Pydantic 自動 422
- 必填欄位缺失（如 `LibraryOverviewPageContext.vendor_count`）→ 422

### 3.2 PromptBuilder（`app/modules/copilot/services/prompt_builder.py`）

```python
_SKILL_BLOCKS: dict[SkillName, str] = {
    "log_explain":  _BLOCK1_LOG_EXPLAIN,
    "vrl_generate": _BLOCK1_VRL_GENERATE,
    "vrl_optimize": _BLOCK1_VRL_OPTIMIZE,
    "anomaly":      _BLOCK1_ANOMALY,
}


def _build_block1(skill: SkillName | None) -> str:
    if skill is None:
        return _BLOCK1_PERSONA + _BLOCK1_NO_SKILL
    return _BLOCK1_PERSONA + _SKILL_BLOCKS[skill]


def _render_page_context_xml(ctx: PageContext, *, max_log_lines, max_vrl_chars,
                             max_library_products) -> str:
    match ctx.page:
        case "analyzer":         return _render_analyzer_xml(ctx, max_log_lines=max_log_lines, max_vrl_chars=max_vrl_chars)
        case "library_overview": return _render_library_overview_xml(ctx, max_products=max_library_products)
        case "library_product":  return _render_library_product_xml(ctx, max_vrl_chars=max_vrl_chars)
        case "library_versions": return _render_library_versions_xml(ctx, max_vrl_chars=max_vrl_chars)
```

### 3.3 Skill prompts（核心 process）

#### `vrl_generate`

```
# Skill: vrl_generate

You are generating VRL (Vector Remap Language) parse rules.

## Process (follow in order)
1. Read <logs> + <current_vrl>; identify format and existing structure.
2. List the fields to extract. State each field's source position
   (regex group / json path / csv index).
3. Write VRL. Wrap the code in ```vrl ... ``` (exactly one fenced block,
   language tag must be `vrl`). The block is what the user will Insert
   into the editor.
4. After the code block, list edge cases or limitations:
   - what fields might be missing in some logs
   - which engine version this targets (read <vrl_engine> from <facts>)
   - what was intentionally NOT extracted

## You must NOT
- Invent fields not visibly present in <logs>.
- Hard-code API keys, tokens, passwords, hostnames of production systems.
  Use VRL `del()` if a sensitive field needs removal.
- Use VRL syntax that the engine version in <facts><vrl_engine> doesn't
  support (e.g., 0.32 syntax when engine is 0.25).
- Output more than one ```vrl block. If you need to show alternative
  approaches, describe them in prose; pick one canonical version for the
  fenced block.

## Example output structure
這個 log 是 syslog + PAN-OS CSV 結構。我會用 parse_syslog 抓 header，
再用 split 處理 CSV 段：

```vrl
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.timestamp = parts[1]
.action    = parts[3]
```

注意：
- 若 message 不是 CSV 結構（如某些 log_subtype）會 split 失敗 → 保留 raw
- 此例針對 engine 0.32；0.25 需把 string! 改成 to_string!
```

#### `vrl_optimize`

```
# Skill: vrl_optimize

You are reviewing existing VRL for redundancy and reliability problems.

## Process
1. Read <current_vrl> + <parse_results>. Note which lines triggered errors.
2. Find:
   - unsafe unwrap (`!`) where `??` fallback would be safer
   - redundant assignments
   - branches that never fire given <logs>
   - field types likely wrong (string assigned to a numeric field)
3. Output the refactored VRL in a single ```vrl ... ``` fenced block.
4. List "改了什麼" with one line per change citing the original line number.

## You must NOT
- Change semantics that aren't broken (e.g., reformat just for style).
- Hard-code values from <logs> as constants.
- Output more than one ```vrl block.
```

#### `anomaly`

```
# Skill: anomaly

You are flagging unusual values in the user's log sample.

## Process
1. For each log in <logs>, scan for anomalies: malformed timestamp,
   private/public IP direction reversed, unusually long opaque strings,
   base64-looking blobs, repeated identical fields suggesting truncation.
2. Output a list. Each entry:
   - "第 N 筆"（cite index from <logs>）
   - one-line description
   - 〔依據：明確/推測/未知〕

## You must NOT
- Speculate on attack scenarios unless the user asked.
- Flag fields that look fine just because they exist (no false positives
  for "this IP could be malicious"-style guesses).
```

`log_explain` 不變（D1 既有）。

### 3.4 ChatService（`app/modules/copilot/services/chat_service.py`）

```python
class ChatService:
    def __init__(
        self,
        *,
        anthropic_client,
        anthropic_api_key: str | None,
        default_model: str,
        skill_models: dict[str, str],          # 新
        max_history: int,
        max_log_lines_in_context: int,
        max_vrl_chars_in_context: int,
        max_library_products_in_context: int,  # 新
    ) -> None: ...

    def _model_for(self, skill: SkillName | None) -> str:
        if skill and skill in self._skill_models:
            return self._skill_models[skill]
        return self._default_model

    async def stream(self, *, request: ChatRequest) -> AsyncIterator[bytes]:
        # ... no api_key 路徑同 D1
        system_blocks = build_system_blocks(
            skill=request.skill,
            page_context=request.page_context,
            max_log_lines=self._max_log_lines,
            max_vrl_chars=self._max_vrl_chars,
            max_library_products=self._max_library_products,
        )
        model = self._model_for(request.skill)   # ← 替換 D1 寫死的 self._model
        async with self._client.messages.stream(
            model=model, max_tokens=2048, system=system_blocks,
            messages=anthropic_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield self._sse(SSE_EVENT_TEXT_DELTA, {"text": text})
        # 其餘 except / finally 同 D1
```

DI 從 settings 組 `skill_models`，只塞有 override 的：

```python
# M1：只塞 vrl_generate
skill_models: dict[str, str] = {}
if settings.llm_copilot_vrl_model:
    skill_models["vrl_generate"] = settings.llm_copilot_vrl_model
# M3 加 vrl_optimize 時：
#     skill_models["vrl_optimize"] = settings.llm_copilot_vrl_model
# log_explain / anomaly 沒 override 就 fallback default
```

### 3.5 Settings 新增（`app/core/config.py`）

```python
class Settings(BaseSettings):
    # D1 既有 llm_copilot_model 不改名（D1 已 ship）；
    # ChatService 內部以 default_model 命名讀取，僅是程式碼可讀性
    llm_copilot_vrl_model: str | None = None
    llm_copilot_max_library_products_in_context: int = 20
```

`.env.example` 同步加（VRL_MODEL 留空示意 optional）：

```
# Copilot — D2 additions
LLM_COPILOT_VRL_MODEL=                          # optional; e.g. claude-sonnet-4-6
LLM_COPILOT_MAX_LIBRARY_PRODUCTS_IN_CONTEXT=20
```

### 3.6 Page context XML 範例

#### `library_overview`

```xml
<page_context page="library_overview">
  <facts>
    <filters status="published" q="palo"/>
    <vendor_count>12</vendor_count>
    <product_count>34</product_count>
  </facts>
  <products_missing_parse_rule count="8" showing="8">
    <product slug="paloalto/panorama"/>
    <product slug="cisco/ftd"/>
    ...
  </products_missing_parse_rule>
</page_context>
```

#### `library_product`

```xml
<page_context page="library_product">
  <facts>
    <vendor_slug>paloalto</vendor_slug>
    <product_slug>pan-os</product_slug>
    <product_status>active</product_status>
  </facts>
  <active_log_type name="traffic">
    <fields count="12">
      <field name="src_ip" type="string" required="true"/>
      <field name="dst_ip" type="string" required="true"/>
      ...
    </fields>
    <samples_count>23</samples_count>
    <parse_rule_head><![CDATA[
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
...
    ]]></parse_rule_head>
  </active_log_type>
</page_context>
```

#### `library_versions`

```xml
<page_context page="library_versions">
  <facts>
    <vendor_slug>paloalto</vendor_slug>
    <product_slug>pan-os</product_slug>
    <log_type_name>traffic</log_type_name>
  </facts>
  <diff base_version="v3" head_version="v4">
    <base_vrl><![CDATA[...]]></base_vrl>
    <head_vrl><![CDATA[...]]></head_vrl>
  </diff>
</page_context>
```

無 diff（user 在 sub-tab 但未開 modal）：`<diff>` 整個省略。

---

## 4. 前端架構

### 4.1 Store 擴張（`web/lib/copilot/store.ts`）

```ts
type EditorBridge = {
  setVrl: ((next: string) => void) | null;
  getVrl: () => string;                       // 給 Insert dialog 顯 diff
};

type PendingInsert = {
  proposedVrl: string;
  messageId: string;
} | null;

type CopilotState = {
  // ... D1 既有 ...
  editorBridge: EditorBridge;
  pendingInsert: PendingInsert;
  lastSkill: SkillName | null;

  registerEditor: (b: { setVrl: (s: string) => void; getVrl: () => string }) => void;
  unregisterEditor: () => void;
  requestInsert: (proposedVrl: string, messageId: string) => void;
  confirmInsert: () => void;
  cancelInsert: () => void;
  setLastSkill: (s: SkillName | null) => void;
};
```

`partialize`（D1）不變 —— `editorBridge` / `pendingInsert` / `lastSkill` 都 in-memory only（function reference 不能序列化）。

`finalizeMessage` 改有實作：

```ts
finalizeMessage: (id) =>
  set((s) => ({
    messages: s.messages.map((m) =>
      m.id === id && m.role === "assistant"
        ? { ...m, vrlBlock: extractVrlBlock(m.content) ?? undefined }
        : m,
    ),
  }))
```

`ChatMessage` type 加 `vrlBlock?: string`。

### 4.2 PageContext 在 store 用 union（types.ts）

```ts
export type AnalyzerPageContext = {
  page: "analyzer";
  vrl: string | null; vrlEngine: string | null;
  logs: string[];
  parseResults: ParseResult[];
  matchTopCandidate: MatchHypothesis | null;
};

export type LibraryOverviewPageContext = {
  page: "library_overview";
  filters: { status?: string | null; q?: string | null };
  vendorCount: number; productCount: number;
  productsMissingParseRule: string[];
};

export type LibraryProductPageContext = {
  page: "library_product";
  vendorSlug: string; productSlug: string; productStatus: string;
  activeLogType: ActiveLogTypeContext | null;
};

export type LibraryVersionsPageContext = {
  page: "library_versions";
  vendorSlug: string; productSlug: string; logTypeName: string;
  diff: VersionDiffContext | null;
};

export type PageContext =
  | AnalyzerPageContext | LibraryOverviewPageContext
  | LibraryProductPageContext | LibraryVersionsPageContext;
```

`use-streaming-chat.toBackendPageContext` 改 `switch (ctx.page)` 各自轉 snake_case。

### 4.3 Page context hooks

| Hook | Mount 處 | 注入內容 | Cleanup |
|---|---|---|---|
| `useAnalyzerCopilotContext` (M1 擴張) | `analyzer-view.tsx` | analyzer ctx + register editor bridge（`setVrl` from useState、`getVrl` from useRef latest） | `setPageContext(null)` + `unregisterEditor()` |
| `useLibraryOverviewCopilotContext` (M2) | `library-overview-view.tsx` | filters + 統計（`groups.flatMap(...).length`）+ missing list（filter `is_empty \|\| log_type_counts.published === 0`）；用 `useDebounce(filters, 200)` 避免每按字都 push | `setPageContext(null)` |
| `useProductDetailCopilotContext` (M2) | `product-detail-view.tsx` | 接收 `{ vendorSlug, productSlug, productStatus, activeLogType, subTab, openDiff }`：依 `subTab` 切 `page="library_product"` 或 `page="library_versions"` | `setPageContext(null)` |

—— **沒有獨立的 versions hook**：sub-tab 切換只更新 hook 的 payload，`page` 字串內部換。確保任何時刻 analyzer-view + library-overview-view + product-detail-view 三個 hook 中只有一個 register。

### 4.4 Insert into editor 流程

| 元件 | 行為 |
|---|---|
| `<MessageBubble>` | assistant message 結束後，從 `message.vrlBlock` 拿出 vrl 字串。若有 + `editorBridge.setVrl !== null`：render `<InsertChip onClick={() => requestInsert(vrlBlock, message.id)}>`。`setVrl===null`（換頁了）時 chip disabled + tooltip「需在 Analyzer 頁才能 Insert」 |
| `<InsertVrlDialog>` | 監聽 `pendingInsert`：`!== null` 開 dialog。內容：左欄 `editorBridge.getVrl()`（label「目前 VRL」）、右欄 `pendingInsert.proposedVrl`（label「Copilot 提議」）。Confirm → `confirmInsert()` → bridge.setVrl 觸發、清 pending；Cancel/ESC → `cancelInsert()` |
| Diff render | 自寫 line-level 純色 diff：split `\n`，按行對 longest-common-subsequence（不對齊 hunk，dumb but enough）：相同行灰、新增行綠 bg、刪除行紅 bg。M1 不引第三方 diff lib（節省 ~30KB）。後續若品質不夠再升級 |
| `extractVrlBlock` | regex `/```vrl\n([\s\S]*?)\n```/`，取第一個 capture group。streaming 過程**不抽**（避免不完整 block），只在 `finalizeMessage` 抽一次寫入 message metadata |

### 4.5 Quick-buttons 條件渲染（`quick-buttons.tsx`）

| Button | 顯示條件 | onClick | skill |
|---|---|---|---|
| ✦ 解釋這幾筆 log | `page="analyzer" && logs.length>0` | send 預設 prompt | log_explain |
| ✦ 生成 VRL | `page="analyzer" && logs.length>0` | send 預設 prompt | vrl_generate |
| ✦ 比對 Library | `page="analyzer" && logs.length>0` | 先 fetch `/api/v1/analyzer/match` → 串成 user message → send | log_explain |
| ✦ 最佳化 VRL | `page="analyzer" && vrl.length>0` | send 預設 prompt | vrl_optimize |
| ✦ 找異常值 | `page="analyzer" && logs.length>0` | send 預設 prompt | anomaly |

Library 三頁不顯任何 quick-button（D2 沒設計按鈕；自由輸入即可）。

### 4.6 自由輸入 skill heuristic

`useStreamingChat.send` 接受可選第二參數 `{ skill?: SkillName }`。決策：

```ts
function pickSkill(ctx: PageContext | null, requested?: SkillName): SkillName | null {
  if (requested) return requested;             // quick-button 明訂優先
  if (!ctx || ctx.page !== "analyzer") return null;
  return "log_explain";                         // analyzer 自由輸入保守選 log_explain
}
```

VRL 自由輸入要走 vrl skill 的話從 quick-button —— 避免 heuristic 誤判。

### 4.7 Safety banner

`<SafetyBanner skill={lastSkill} />` 放 `<ContextStrip>` 下方：

```tsx
if (skill !== "vrl_generate" && skill !== "vrl_optimize") return null;
return (
  <div className="border-b bg-amber-50 px-3 py-1.5 text-[11px] text-amber-800">
    ⚠ 生成的 VRL 不要 hard-code API key / token / password
  </div>
);
```

`lastSkill` 在每次 `send` 時更新；切到非 VRL skill 時自動消失。

### 4.8 Dependencies（前端 package.json）

無新增。React 內建 + 既有 zustand / react-markdown 已夠。

---

## 5. 資料流

### 5.1 VRL 生成 + Insert 完整流程

```
User 在 /analyzer 點 ✦ 生成 VRL（quick-button）
  ↓
quick-buttons.onClick:
  send("請依照 <logs> 與 <current_vrl> 寫一段 VRL，輸出 ```vrl ... ``` 區塊。",
       { skill: "vrl_generate" })
  ↓
useStreamingChat.send:
  - store.appendUserMessage(text)
  - store.appendAssistantPlaceholder() → assistantId
  - store.setLastSkill("vrl_generate")    # SafetyBanner 開始顯
  - body = { messages, skill: "vrl_generate", page_context: analyzerCtx }
  ↓
POST /api/v1/copilot/chat (SSE)
  ↓
Backend:
  - chat_router validate
  - chat_service.stream(request):
      model = self._model_for("vrl_generate") → settings.llm_copilot_vrl_model or default
      system = build_system_blocks(skill="vrl_generate", page_context=analyzerCtx, ...)
      async with client.messages.stream(...) as stream:
        async for text in stream.text_stream: yield SSE text_delta
  ↓
Frontend SSE consumer:
  - text_delta → store.appendDelta(assistantId, text)
  - done → store.finalizeMessage(assistantId)
            └→ extractVrlBlock(content) → 存 message.vrlBlock
  ↓
<MessageBubble> re-render: 偵測 message.vrlBlock 存在 → render <InsertChip>
  ↓
User 點 InsertChip:
  store.requestInsert(message.vrlBlock, message.id)
  → pendingInsert = { proposedVrl, messageId }
  ↓
<InsertVrlDialog> open:
  顯示 diff: editorBridge.getVrl()  vs  pendingInsert.proposedVrl
  ↓
User Confirm:
  store.confirmInsert():
    editorBridge.setVrl(pendingInsert.proposedVrl)
    pendingInsert = null
  → analyzer-view setVrl 觸發 React state 更新
  → useEffect debounced parse 自動跑
  → useAnalyzerCopilotContext 推新 vrl 到 pageContext
  → 對話可繼續、下次 send 帶到的就是新 VRL
```

### 5.2 比對 Library quick-button 流程（M3）

```
User 點 ✦ 比對 Library
  ↓
quick-buttons.onClick:
  setIsMatching(true)
  const r = await apiFetch("/api/v1/analyzer/match",
                            { raw_log: ctx.logs[0], top_k: 3 })
  ↓
構造 user message（純文字）：
  「請依下列 candidates 比對 <logs> 中的 log，告訴我哪一個最可能、為什麼，
   以及不符合的地方。

   Candidate 1: paloalto/pan-os, traffic, confidence=0.94
     reason: <reason 1>
   Candidate 2: cisco/asa, syslog, confidence=0.42
     reason: <reason 2>
   Candidate 3: ...」
  ↓
send(message, { skill: "log_explain" })
  # hypotheses 內 top1 不變；完整 candidates 走 user message
  ↓
（其餘流程同 5.1：stream → 顯示 → 結束）
```

理由：candidates 是 user 主動觸發的對比資料，當 user message 送最自然。不擴 page_context schema（避免為一顆按鈕加 `match_candidates` 欄位）；不塞 hypotheses（D1 prompt 寫明「hypotheses 不是 ground truth」）。

### 5.3 換頁與 editor bridge 行為

| 情境 | 行為 |
|---|---|
| `/analyzer` → `/library` | analyzer-view unmount → `unregisterEditor()` → bridge.setVrl=null。已存在的 message 帶 vrlBlock 仍保留，但 InsertChip 變 disabled |
| Insert dialog 開著時換頁 | analyzer-view unmount → store cancelInsert（dialog 關） |
| Streaming 中換頁 | stream 不中斷（D1 既有），結束後 vrlBlock 仍寫入；切回 analyzer 重新 register editor 後可 Insert |
| `/library` → `/library/cisco/asa` | overview hook unmount + product hook mount。setPageContext 中間有「null」一瞬間（接受） |
| Versions sub-tab 切換 | product hook payload 換，page 字串切到 `library_versions`；無新 hook register |

### 5.4 三頁 hook 衝突避免

**原則**：page-level component 只 register 一個 hook；sub-tab / modal 開關只改該 hook 的 payload，不另外 register hook。

實作：
- `library-overview-view.tsx`：`useLibraryOverviewCopilotContext({ filters, groups })`
- `product-detail-view.tsx`：`useProductDetailCopilotContext({ vendorSlug, productSlug, productStatus, activeLogType, subTab, openDiff })`
  - `subTab="versions"` 時 hook 內部 `setPageContext({ page: "library_versions", ..., diff: openDiff })`
  - `subTab="overview" | "stats"` 時 `setPageContext({ page: "library_product", ... })`

---

## 6. 錯誤處理

| 情境 | Backend | Frontend |
|---|---|---|
| `LLM_COPILOT_VRL_MODEL` 設了但模型 ID 無效 | Anthropic SDK 拋 → catch → SSE `error{anthropic_failed}` | 既有路徑（紅框 + 重試 chip） |
| VRL skill 但 LLM 沒輸出 ` ```vrl ` block | 無感（純 free text） | `extractVrlBlock` 回 null，**不顯** Insert chip。Bubble 正常顯示文字 |
| LLM 輸出多個 ` ```vrl ` block | regex 抽**第一個**；其餘文字保留在 bubble | 一顆 Insert chip 對應第一個 block |
| Insert 時 `editorBridge.setVrl=null`（換頁） | n/a | InsertChip disabled，hover tooltip「需在 Analyzer 頁才能 Insert」 |
| 比對 Library quick-button：`/analyzer/match` 503 | n/a | `apiFetch` 拋 → button spinner 收掉、跳 toast「比對暫時無法使用」、不開始 chat |
| Versions sub-tab 注入但無 active log type | n/a | hook skip 注入；保留 `library_product` ctx |
| Library overview filters 變動快速連動 | n/a | hook 用 `useDebounce(filters, 200)` |
| User 在 streaming 中切 quick-button | n/a | onClick 內檢查 `isStreaming` 直接 return（D1 既有 send 防重入） |
| Insert dialog Confirm 點兩次 | n/a | `confirmInsert` 內 `if (!pendingInsert) return` |
| Discriminated union 解析失敗（前端送了 backend 不認得的 page） | Pydantic 422 | request 拋 → toast、不 streaming |

---

## 7. 測試策略

### 7.1 Backend

| 檔 | 重點 |
|---|---|
| `tests/unit/modules/copilot/test_schemas.py` | (1) `page="analyzer"` 解析到 AnalyzerPageContext；(2) `page="library_overview"` 缺 vendor_count → 422；(3) 不認得的 page → 422；(4) skill 限四值；(5) D1 既有 ChatRequest 解析 backwards-compatible |
| `test_prompt_builder.py`（擴充） | 每個 skill block 1 含關鍵字斷言：vrl_generate 含「```vrl」「You must NOT」「hard-code」；vrl_optimize 含「parse_results」；anomaly 含「異常」。每個 page renderer XML 結構正確（library_overview cap 邏輯：products_missing_parse_rule 超過 cap 時 truncate；library_product 的 active_log_type=None 時 element 省略；library_versions 的 diff=None 時 `<diff>` 省略） |
| `test_chat_service.py`（擴充） | (1) `_model_for("vrl_generate")` 在有 override 時用 override，沒 override 時 fallback default；(2) 三 skill 都 dispatch 正確（mock 檢查傳給 SDK 的 model 字串） |

### 7.2 Frontend

| 檔 | 重點 |
|---|---|
| `web/lib/copilot/__tests__/store.test.ts`（擴充） | (1) `registerEditor`/`unregisterEditor` 狀態轉移；(2) `requestInsert` → `pendingInsert` 設好；(3) `confirmInsert` 呼 bridge.setVrl 且 clear pending；(4) `cancelInsert` 不呼 bridge；(5) `lastSkill` 隨 send 更新 |
| `__tests__/extract-vrl-block.test.ts`（新） | 4 case：標準 ```vrl block 抽出 inner / 無 block → null / 多 block → 第一個 / 不完整 block → null |
| `__tests__/insert-vrl-dialog.test.tsx`（新） | open 時顯 diff、Confirm 呼 confirmInsert、Cancel 呼 cancelInsert、ESC 當 Cancel |
| `__tests__/quick-buttons.test.tsx`（擴充） | 按 page 條件渲染：analyzer 有 logs/vrl 各組合下顯哪幾顆；library 三頁不顯 |
| `__tests__/use-library-overview-context.test.tsx`（新，M2） | mount/unmount + filters 變動 push pageContext；debounce 行為 |
| `__tests__/use-product-detail-context.test.tsx`（新，M2） | activeLogType 變、subTab 切 versions、diff modal 開關 → pageContext.page 與 payload 對應 |
| `__tests__/safety-banner.test.tsx`（新） | skill=vrl_generate / vrl_optimize 顯；其他 skill 不顯 |

### 7.3 不寫的測試（明確）

- LLM 是否真的把 VRL 包進 ```vrl block —— flaky，靠 production sample 觀察
- LLM 是否遵守不 hard-code secret —— 同上
- 跨頁 Copilot context 在 layout-level panel 是否真的不殘留 —— 要 Cypress E2E，D2 不開 E2E pipeline；改 manual smoke
- Diff 演算法的「正確性」（diff 是顯示用、不參與 confirm 邏輯，line-by-line 顯示就夠）

---

## 8. 驗收標準

按 milestone 逐一驗收，每個 milestone 結束開 PR、過了再進下一個。

### M1 驗收

1. /analyzer 頁可看到「✦ 生成 VRL」quick-button（有 logs 時）；點下後 streaming 出 ```vrl block
2. assistant 訊息結束後出現 Insert chip；點下開 dialog 顯 current vs proposed diff
3. Confirm 後 CodeMirror 內容更新；自動觸發 parse 重跑
4. VRL skill active 時 panel 頂顯 safety banner；切到 log_explain 時消失
5. `LLM_COPILOT_VRL_MODEL` 未設時 fallback default model；設了走 override（後端 mock 測）
6. 換頁離開 /analyzer 後 Insert chip disabled
7. D1 的 log_explain 行為不變（regression）

### M2 驗收

1. 進 /library overview，panel context strip 顯示 filters / 統計 pills
2. 進 /library/cisco/asa，context strip 顯示 product/log type / parse rule head
3. 切到 Versions sub-tab，pill 改顯 versions 字樣；打開 diff modal pill 多一顆「diff」
4. 三頁皆可自由對話（skill=null），LLM 收到 page_context 摘要
5. 切回 /analyzer 後 pageContext 正確切回 analyzer shape
6. M1 Insert chip 在非 analyzer 頁仍 disabled

### M3 驗收

1. /analyzer 三顆新 quick-button（比對 Library / 最佳化 VRL / 找異常值）按條件渲染
2. 比對 Library 點下後先呼 /api/v1/analyzer/match，再 send chat（user message 含 candidates）
3. 最佳化 VRL：output 帶 vrl block，Insert chip 可用（reuse M1 路徑）
4. 找異常值：output 含「第 X 筆」index 引用 + 〔依據：明確/推測/未知〕
5. 全部 milestone 結束後，D1 的 log_explain + analyzer 行為不變（regression）

---

## 9. Module 結構彙整

### 後端

```
app/modules/copilot/
├── schemas.py                                # 改：discriminated union PageContext + 4 SkillName
├── constants.py                              # 改：+SKILL_VRL_GENERATE / VRL_OPTIMIZE / ANOMALY
└── services/
    ├── prompt_builder.py                     # 改：dispatch table + 4 page renderers
    └── chat_service.py                       # 改：_model_for(skill) + skill_models DI

app/core/config.py                            # 改：+llm_copilot_vrl_model + max_library_products
.env.example                                  # 改：+2 lines
tests/unit/modules/copilot/
├── test_schemas.py                           # 改：union 解析測試
├── test_prompt_builder.py                    # 改：4 skill + 4 page 渲染
└── test_chat_service.py                      # 改：model dispatch
```

### 前端

```
web/lib/copilot/
├── types.ts                                  # 改：union PageContext + EditorBridge + PendingInsert
├── store.ts                                  # 改：editor bridge / pending insert / lastSkill
├── extract-vrl-block.ts                      # 新（M1）
└── hooks/
    ├── use-analyzer-context.ts               # 改（M1）：擴 register editor bridge
    ├── use-streaming-chat.ts                 # 改：toBackendPageContext switch / lastSkill / heuristic
    ├── use-library-overview-context.ts       # 新（M2）
    └── use-product-detail-context.ts         # 新（M2，含 versions sub-tab 模式）

web/components/copilot/
├── insert-vrl-dialog.tsx                     # 新（M1）
├── safety-banner.tsx                         # 新（M1）
├── quick-buttons.tsx                         # 改（M1+M3）
├── context-strip.tsx                         # 改（M2）：依 ctx.page 切 pill
└── message-bubble.tsx                        # 改（M1）：偵測 vrlBlock → Insert chip

web/components/analyzer/analyzer-view.tsx     # 改（M1）：傳 register editor 進 hook
web/components/library/library-overview-view.tsx  # 改（M2）：mount hook
web/components/library/product-detail-view.tsx    # 改（M2）：mount hook + sub-tab/diff 同步
```

---

## 10. 風險與待確認

| 項目 | 處理 |
|---|---|
| Sonnet 4.6 stream 速度比 Haiku 慢 ~2-3x | 接受；UI 已有 streaming dots。若實測 latency > 10s 再考慮 streaming 開頭顯「正在生成 VRL，需要約 10 秒…」 |
| `extractVrlBlock` 在 LLM 把 VRL 包成 ` ```rust ` 或無 lang tag 時抽不到 | M1 prompt 嚴格要求「```vrl」+ few-shot；若 production 觀察到 LLM 偷懶用其他 lang tag，prompt v2 加 ` ```vrl ` 與 ` ``` `（無 tag）兩種都接受 |
| 自寫 line-level diff 品質低 | M1 接受；後續若品質不夠再評估 `react-diff-viewer-continued`（+ ~30KB gzip） |
| Library overview「缺 parse rule 列表」資料來源 | 現有 `OverviewProduct` 已有 `is_empty: bool` 與 `log_type_counts.{total, published, draft}`。前端從 `is_empty \|\| published === 0` 推導，**不需 prereq 擴 backend schema** |
| M2 新增 page renderer XML 失敗（特殊字元 escape bug） | 共用 `_safe_cdata` helper + per-page 單測 |
| Versions sub-tab 注入時沒 diff 資料的時機 | 進 sub-tab 但未開 modal：`page="library_versions"` + `diff=null`。LLM 收到「在 versions 頁但沒選具體 version」的訊號 |
| Per-skill model dict 散在 settings | M3 後若 4 skill 各 override 變成 4 個 env var；接受。未來真要管理化再考慮從 yaml 讀 |
| `useAnalyzerCopilotContext` 既有 `JSON.stringify` dep key 在加 editor bridge 後增加 stringify 開銷 | 不影響：editor bridge 不在 dep（用 useRef 抓 latest setVrl，register 只跑一次） |
| Discriminated union 對 D1 既有 frontend 是 breaking 嗎 | 不是：D1 frontend 已送 `page="analyzer"`；新增的 page literal 是 D2 才開始送的，舊 frontend 仍可工作 |
| 既有 `diff-pane.tsx`（analyzer parse 結果 diff）能否 reuse 在 InsertVrlDialog | 不直接 reuse —— diff-pane 是 parse 結果（dict v0.25 vs v0.32），InsertVrlDialog 要的是 VRL 文字逐行 diff。M1 自寫 line-level diff |

---

## 11. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| D3 | Copilot — ⌘K inline VRL + parse error 修錯 | CodeMirror 內嵌 ghost text + accept/reject；點 parse error 行 → Copilot 給修正建議。獨立 spec 因 UX 工程量遠大於 panel chat |
| E | LLM Pipeline | 爬文件、草稿、Review diff、source = `llm_generated`（與 Copilot 平行） |

---

## 附錄 A：vrl_generate skill 完整 Block 1 範例

當 `skill="vrl_generate"`、`page_context=AnalyzerPageContext(...)`：

````
You are LogScope Copilot. The user is a security engineer.

Respond in 繁體中文. Engineers want answers, not paragraphs.

# Output rules
- Cite data by tag: "在 <logs> 的第 3 筆…"、"<current_vrl> 第 18 行…"
- Code in fenced blocks with language hint.
- For each claim about a field's MEANING (not just its position), end with
  one of: 〔依據：明確〕〔依據：推測〕〔依據：未知〕

# Skill: vrl_generate

You are generating VRL (Vector Remap Language) parse rules.

## Process (follow in order)
1. Read <logs> + <current_vrl>; identify format and existing structure.
2. List the fields to extract. State each field's source position.
3. Write VRL. Wrap the code in ```vrl ... ``` (exactly one fenced block,
   language tag must be `vrl`). The block is what the user will Insert.
4. After the code block, list edge cases or limitations.

## You must NOT
- Invent fields not visibly present in <logs>.
- Hard-code API keys, tokens, passwords, hostnames of production systems.
- Use VRL syntax that the engine version in <facts><vrl_engine> doesn't support.
- Output more than one ```vrl block.
````

## 附錄 B：library_versions XML 完整範例

```xml
<page_context page="library_versions">
  <facts>
    <vendor_slug>paloalto</vendor_slug>
    <product_slug>pan-os</product_slug>
    <log_type_name>traffic</log_type_name>
  </facts>
  <diff base_version="v3" head_version="v4">
    <base_vrl><![CDATA[
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.timestamp = parts[1]
    ]]></base_vrl>
    <head_vrl><![CDATA[
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.timestamp = parse_timestamp!(parts[1], "%Y/%m/%d %H:%M:%S")
.action    = parts[3]
    ]]></head_vrl>
  </diff>
</page_context>
```
