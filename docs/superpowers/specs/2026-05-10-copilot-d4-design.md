# Copilot D4 — VRL Compile-Error Inline Fix（Lint Diagnostic Action）

**Spec ID**: D4
**狀態**: Draft
**建立日期**: 2026-05-10
**前置 Spec**: D3（⌘K Inline VRL — ghost text infra）

---

## 1. 範圍

### 1.1 進 D4

D4 是 Copilot 的小型 vertical slice：當 VRL 在編輯器內 compile error 時，於 lint diagnostic tooltip 內提供「✨ Fix with Copilot」按鈕，點下後 reuse D3 的 inline ghost text 機制自動 replace 出錯那一行。

| 項目 | 內容 |
|---|---|
| Trigger | CodeMirror lint diagnostic 的 `Diagnostic.actions` 內加按鈕「✨ Fix with Copilot」 |
| 範圍 | **僅** VRL compile error（`vrl-lint.ts` 已產生的 diagnostic）。Runtime parse error 已由 D2 的 `AskCopilotChip`（result-pane）走 panel chat / vrl_optimize，不動 |
| Streaming UX | reuse D3：邊 stream 邊顯 ghost text，hint bar「⌛ 生成中… Esc 取消 / ✓ Tab 接受 · Esc 拒絕」 |
| Skill | 新 `vrl_fix`（共用 `LLM_COPILOT_VRL_MODEL`） |
| Endpoint | **沿用** `POST /api/v1/copilot/inline/vrl`，透過 `skill` 欄位 dispatch（不開新 endpoint） |
| Mode | 強制 `replace`（diagnostic 拿到的就是行範圍） |
| Conversation | 完全獨立於 panel chat（同 D3）|

D4 是單一 milestone、單一 PR。

### 1.2 不進 D4

| 留給 | 內容 |
|---|---|
| 未來 spec | Runtime parse error inline fix（既有 D2 chip 已夠用）；多行 selection 的 fix（lint diagnostic 一次 cover 一行就夠）|
| 不做 | Quick-fix keymap（`⌘.`）；gutter lightbulb popup |

### 1.3 與 D3 spec §10 預告的偏離

D3 spec §10 寫 D4 是「點 parse error 行 → Copilot 修錯」。本 spec 把「parse error」明確收斂到 **VRL compile error**（即 vrl-lint 的 diagnostic）。Runtime parse error（log 不符 VRL 預期）由 result-pane 的 `AskCopilotChip` 既有路徑處理，不在 D4。理由：
- 兩種 error 的 anchor 不同（compile error → VRL 行；runtime parse error → log 行）
- 兩種 error 的修法不同（compile fix 通常局部一行；runtime fix 常需要多行重寫）
- Inline ghost text UX 對「局部一行」最自然
- 一個 spec 把兩種一起做會肥、Plan 規模差距大

---

## 2. 架構總覽

```
┌── User journey ─────────────────────────────────────────────┐
│ 1. User 寫 VRL，CM6 lint 顯示 diagnostic（紅波浪 underline）│
│ 2. Hover diagnostic → tooltip 出現 + "✨ Fix with Copilot"  │
│ 3. 點下 → useInlineVrl.send (skill=vrl_fix, mode=replace)   │
│ 4. ghost text streaming 取代該行                             │
│ 5. Tab 接受 / Esc 拒絕（D3 keymap）                          │
└──────────────────────────────────────────────────────────────┘

┌── Backend changes (small) ──────────────────────────────────┐
│  app/modules/copilot/                                        │
│    ├── constants.py   ✎+SKILL_VRL_FIX                        │
│    ├── schemas.py     ✎ extend InlineVrlRequest              │
│    │                     +skill: Literal["vrl_inline","vrl_fix"]│
│    │                     +compile_error: str | None          │
│    │                     validator: vrl_fix → error required │
│    ├── services/                                              │
│    │   ├── prompt_builder.py  ✎+_BLOCK1_VRL_FIX +dispatch    │
│    │   └── chat_service.py    ✎ skill_models["vrl_fix"]      │
│    │                          (model dispatch via request.skill)│
│    └── routers/chat_router.py ✎ DI 加 vrl_fix 的 model 對應   │
└──────────────────────────────────────────────────────────────┘

┌── Frontend changes (small) ─────────────────────────────────┐
│  web/components/analyzer/                                     │
│    ├── vrl-lint.ts            ✎ Diagnostic.actions 加 fix    │
│    └── analyzer-view.tsx      ✎ inlineProviders 多 onCheck   │
│                                  fix trigger 注入             │
│                                                                │
│  web/lib/copilot/types.ts     ✎ InlineVrlRequest 加 skill +   │
│                                  compile_error                │
└──────────────────────────────────────────────────────────────┘
```

完全 reuse D3 的 ghost text widget / hint bar / keymap / StateField / useInlineVrl hook。

---

## 3. 後端架構

### 3.1 Schemas — extend `InlineVrlRequest`

```python
InlineMode = Literal["insert", "replace"]
InlineSkill = Literal["vrl_inline", "vrl_fix"]


class InlineVrlRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2_000)
    skill: InlineSkill = "vrl_inline"           # ★ 新（default 不破壞 D3 既有 client）
    mode: InlineMode
    current_vrl: str = Field(default="", max_length=50_000)
    cursor_offset: int | None = Field(default=None, ge=0)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)
    vrl_engine: Literal["0.25", "0.32"] = "0.32"
    logs: list[str] = Field(default_factory=list, max_length=50)
    compile_error: str | None = Field(default=None, max_length=20_000)   # ★ 新

    @model_validator(mode="after")
    def _check(self) -> "InlineVrlRequest":
        # existing offset checks ...
        if self.skill == "vrl_fix":
            if self.compile_error is None or not self.compile_error.strip():
                raise ValueError("vrl_fix skill requires compile_error")
            if self.mode != "replace":
                raise ValueError("vrl_fix skill requires mode=replace")
        return self
```

**Backwards-compat**：D3 既有 client（不送 `skill` 欄位）會走 default `"vrl_inline"`，行為不變。

### 3.2 Constants

```python
SKILL_VRL_FIX = "vrl_fix"
```

### 3.3 PromptBuilder — `_BLOCK1_VRL_FIX`

```
You are LogScope's VRL compile-error fixer. The user has VRL that
fails to compile. You output ONLY the fixed VRL that replaces the
marked region — no prose, no fence, no explanation.

# Process
1. Read <current_vrl> with the broken region wrapped in
   <|sel_start|>...<|sel_end|>.
2. Read <compile_error> — the exact diagnostic from the VRL compiler
   (typically `error[Exxx]:` block with `:line:col` location).
3. Output the minimal fix that resolves the cited error, preserving
   the original intent of the marked region.

# Output rules (strict)
- Output ONLY raw VRL that REPLACES the region between markers.
- No markdown fences, no leading/trailing prose, no comments.
- No trailing newline.
- The output should be syntactically valid VRL of the engine
  version specified in <facts><vrl_engine>.
- If you cannot determine a safe fix from the data, output exactly:
  `// 無法修復：<原因>`

# Don't
- Don't change semantics outside the marked region.
- Don't invent fields, functions, or types not in <current_vrl>.
- Don't use VRL functions outside the standard set (parse_syslog,
  parse_json, parse_key_value/parse_kv, parse_regex, parse_csv,
  split, to_int/to_float/to_bool/to_string/to_timestamp, del,
  exists, string).

# Example
<facts><vrl_engine>0.32</vrl_engine></facts>
<current_vrl><![CDATA[
. = parse_syslog!(.message)
<|sel_start|>parts = split(.message, ",")<|sel_end|>
.src_ip = parts[6]
]]></current_vrl>
<compile_error><![CDATA[
error[E110]: function "split" expected `string`, got `bytes`
  ┌─ :2:18
  │
2 │ parts = split(.message, ",")
  │              ^^^^^^^^^^^^^^^
]]></compile_error>

OUTPUT:
parts = split(string!(.message), ",")
```

### 3.4 PromptBuilder dispatch

`build_inline_system_blocks` 改 dispatch by `request.skill`：

```python
def build_inline_system_blocks(request, *, max_log_lines, max_vrl_chars):
    block1_text = _BLOCK1_VRL_FIX if request.skill == "vrl_fix" else _BLOCK1_VRL_INLINE
    blocks = [{
        "type": "text",
        "text": block1_text,
        "cache_control": {"type": "ephemeral"},
    }]

    # ... existing safe_vrl / inject_marker / truncate logic ...

    parts = [f"<facts><vrl_engine>{request.vrl_engine}</vrl_engine></facts>"]
    if kept is not None:
        # ... existing <current_vrl> ...
    if request.skill == "vrl_fix" and request.compile_error:
        parts.append(
            f"<compile_error><![CDATA[{_safe_cdata(request.compile_error)}]]></compile_error>"
        )
    if request.logs:
        # ... existing <logs> ...
    blocks.append({"type": "text", "text": "\n".join(parts)})
    return blocks
```

### 3.5 ChatService — model dispatch

`stream_inline` 改 model dispatch：

```python
async def stream_inline(self, *, request: InlineVrlRequest):
    # ... no_api_key check ...
    system_blocks = build_inline_system_blocks(request, ...)
    anthropic_messages = [{"role": "user", "content": request.instruction}]
    try:
        async with self._client.messages.stream(
            model=self._model_for(request.skill),    # ★ 改 — 從 vrl_inline → request.skill
            ...
        ): ...
```

### 3.6 DI — chat_router

```python
skill_models: dict[str, str] = {}
if settings.llm_copilot_vrl_model:
    skill_models["vrl_generate"] = settings.llm_copilot_vrl_model
    skill_models["vrl_optimize"] = settings.llm_copilot_vrl_model
    skill_models["vrl_inline"] = settings.llm_copilot_vrl_model
    skill_models["vrl_fix"] = settings.llm_copilot_vrl_model     # ★ 新
```

無新 settings env var。

---

## 4. 前端架構

### 4.1 Frontend types — extend `InlineVrlRequest`

```typescript
export type InlineSkill = "vrl_inline" | "vrl_fix";

export type InlineVrlRequest = {
  instruction: string;
  skill?: InlineSkill;             // ★ 新 — 預設 server-side 走 vrl_inline
  mode: InlineMode;
  current_vrl: string;
  cursor_offset?: number;
  selection_start?: number;
  selection_end?: number;
  vrl_engine: "0.25" | "0.32";
  logs: string[];
  compile_error?: string;          // ★ 新
};
```

### 4.2 vrl-lint.ts — `Diagnostic.actions`

CodeMirror `Diagnostic.actions` 是內建欄位，render 在 tooltip 內為按鈕。

```typescript
type FixDispatcher = (
  view: EditorView,
  diag: Diagnostic,
) => void;

let _fixDispatcher: FixDispatcher | null = null;

/** Set by analyzer-view at mount; called from diagnostic action. */
export function setVrlFixDispatcher(dispatcher: FixDispatcher | null): void {
  _fixDispatcher = dispatcher;
}

export function parseVrlDiagnostics(compileError: string, view: EditorView): Diagnostic[] {
  // existing logic to map error -> Diagnostic[] ...
  // For each diagnostic, add the "Fix with Copilot" action:
  for (const d of diagnostics) {
    d.actions = [
      {
        name: "✨ Fix with Copilot",
        apply: (view, _from, _to) => {
          _fixDispatcher?.(view, d);
        },
      },
    ];
  }
  return diagnostics;
}
```

### 4.3 analyzer-view.tsx — wire fix dispatcher

```typescript
useEffect(() => {
  setVrlFixDispatcher((view, diag) => {
    const sendInline = sendInlineRef.current;
    const line = view.state.doc.lineAt(diag.from);
    sendInline({
      instruction: "Fix this VRL compile error",
      skill: "vrl_fix",
      mode: "replace",
      current_vrl: view.state.doc.toString(),
      selection_start: line.from,
      selection_end: line.to,
      vrl_engine: engineVersion,
      logs: [],
      compile_error: diag.message,
    });
  });
  return () => setVrlFixDispatcher(null);
}, [engineVersion]);
```

注意：`sendInlineRef` 在 D3 已建立、跨 render 持最新 send。`engineVersion` 變動時 effect 重 run（只更新 closure，不影響 D3 in-flight）。

### 4.4 不動的東西

- D3 的 `useInlineVrl`、`InlineState`、`ghost-text-widget`、`hint-bar-widget`、`prompt-input-widget`、`inline-keymap`、`inline-decorations`、`inline-extension` 一行不改
- D2 的 `AskCopilotChip`（result-pane）行為不變

### 4.5 構件樹（前端追加）

```
web/lib/copilot/types.ts                 ✎ +InlineSkill +skill?+compile_error?
web/components/analyzer/vrl-lint.ts      ✎ +Diagnostic.actions +setVrlFixDispatcher
web/components/analyzer/analyzer-view.tsx ✎ +useEffect 註冊 fix dispatcher
```

---

## 5. 資料流

### 5.1 D4 完整流程

```
User 在 /analyzer 編輯 VRL，CM6 lint 跑 /analyzer/check
  ↓
backend 回 compile_error: "error[E110]: function `split` expected ..."
  ↓
parseVrlDiagnostics:
  - 解析 error block 拿到 line/col
  - 產生 Diagnostic[]，每個 diag.actions = [{ name: "✨ Fix with Copilot", apply }]
  ↓
User hover red underline → tooltip 顯示 → 看到 button
User 點 "✨ Fix with Copilot"
  ↓
diag.actions[0].apply(view, from, to) → _fixDispatcher(view, diag)
  ↓
analyzer-view 內注入的 dispatcher:
  line = view.state.doc.lineAt(diag.from)
  sendInline({
    instruction: "Fix this VRL compile error",
    skill: "vrl_fix",
    mode: "replace",
    current_vrl: doc.toString(),
    selection_start: line.from,
    selection_end: line.to,
    vrl_engine,
    logs: [],
    compile_error: diag.message,
  })
  ↓
useInlineVrl.send (D3 既有):
  - dispatch InlineState → streaming
  - GhostTextWidget + HintBarWidget mount via decoration（D3 既有）
  - selection range 半透明 strikethrough（D3 既有 cm-inline-replace-original）
  ↓
streamInlineVrl → POST /api/v1/copilot/inline/vrl (skill=vrl_fix)
  ↓
backend chat_service.stream_inline:
  build_inline_system_blocks → block 1 = _BLOCK1_VRL_FIX
                              block 2 含 <current_vrl> + <compile_error> + <logs>
  model = self._model_for("vrl_fix")
  ↓
streaming text_delta → ghost grows → done → ready
  ↓
User Tab → handleTabAccept (D3 既有) → ghost replace 該行 → state idle
  ↓
onChange 觸發 → setVrl 更新 → 自動 parse 重跑 → lint 重跑 → diagnostic 消失
```

### 5.2 與 D3 並存

User 同時可用 ⌘K（D3）與 lint action（D4）— 它們走同一個 InlineState，後啟動的 abort 前一個（D3 既有 `handleCmdK` 的 abort 邏輯一致 cover D4）。

---

## 6. 錯誤處理

| 情境 | 處理 |
|---|---|
| 無 API key / Anthropic 失敗 | 同 D3：hint bar 顯紅 + 5s auto idle |
| LLM 違反規則出 fence / prose | 同 D3：不 strip；信任 prompt + few-shot |
| LLM 輸出 `// 無法修復：...` 註解 | 與 D3 一致：ready state，user Tab 會插入註解，通常 Esc |
| Diagnostic 消失但 inline 還在 streaming | docChanged → 自動 abort（D3 StateField 邏輯）|
| 同時點兩個 diagnostic 的 fix button | 第二次 dispatch 會覆寫 InlineState，但 first stream 仍跑（前一個 controller 沒 abort）。簡化：dispatcher 入口先檢查 `view.state.field(inlineField)`，active 時先 reset+abort 再 trigger（與 D3 cmdK 一致） |
| compile_error 字串太長（>20KB）| 422 |
| Diagnostic 涵蓋多行（少見）| `lineAt(diag.from)` 只取第一行；不處理跨行（D4 scope 限制）|

---

## 7. 測試策略

### 7.1 Backend tests（擴充既有）

| 檔 | 重點 |
|---|---|
| `tests/unit/modules/copilot/test_schemas.py` | (1) `skill="vrl_fix"` 缺 `compile_error` → 422；(2) `skill="vrl_fix"` + `mode="insert"` → 422；(3) `skill="vrl_fix"` + `compile_error="   "` → 422；(4) `skill="vrl_fix"` + `mode="replace"` + valid `compile_error` → ok；(5) 預設 `skill` is `"vrl_inline"`（backwards-compat） |
| `tests/unit/modules/copilot/test_prompt_builder.py` | (1) `build_inline_system_blocks(req, skill="vrl_fix")` block 1 用 `_BLOCK1_VRL_FIX`（含「VRL compile-error fixer」「<\|sel_start\|>」）；(2) block 2 含 `<compile_error>` element；(3) `skill="vrl_inline"` 不含 `<compile_error>`；(4) `_BLOCK1_VRL_FIX` 含關鍵字「無法修復」「Output ONLY」 |
| `tests/unit/modules/copilot/test_chat_service.py` | (1) `stream_inline` 對 `vrl_fix` request 用 `_model_for("vrl_fix")` 拿 override；(2) anthropic 收到 system block 含 `_BLOCK1_VRL_FIX`（mock + capture system param）|
| `tests/unit/modules/copilot/test_inline_router.py` | (1) `vrl_fix` 合法 request → 200 SSE；(2) `vrl_fix` 無 `compile_error` → 422 |

### 7.2 Frontend tests

| 檔 | 重點 |
|---|---|
| `web/components/analyzer/__tests__/vrl-lint.test.ts`（新或擴充） | (1) `parseVrlDiagnostics` 結果每個 Diagnostic 有 `actions`，`actions[0].name === "✨ Fix with Copilot"`；(2) 呼叫 action.apply 時 `_fixDispatcher` 被呼到，傳入正確 view + diagnostic |
| `web/components/analyzer/__tests__/analyzer-view.fix.test.tsx`（新） | (1) mount 後 `setVrlFixDispatcher` 被呼到（注入 dispatcher）；(2) unmount 後被 `setVrlFixDispatcher(null)` 重置 |

### 7.3 Manual smoke

1. 寫一段會 compile error 的 VRL（`parts = split(.message, ",")` 在 0.32 engine）
2. 等 lint 顯紅波浪 underline
3. Hover → 看到 tooltip + "✨ Fix with Copilot" 按鈕
4. 點下 → ghost text streaming（取代該行半透明 strikethrough）+ hint bar
5. Tab → 該行被 fix 取代、ghost 消失
6. Lint 重 run → 無 error 或剩 next error
7. ⌘K 仍正常（D3 regression）
8. result-pane 的 「✦ 問 Copilot」 chip 仍正常（D2 regression）

---

## 8. 驗收標準

D4 是單一 milestone、單一 PR。

1. /analyzer 寫故意 broken VRL → lint 顯 diagnostic + tooltip 內含 "✨ Fix with Copilot" 按鈕
2. 點按鈕 → ghost text streaming 取代 error 行；原 error 行半透明 strikethrough（reuse D3 mark）
3. Hint bar 三狀態（streaming / ready / error）正常切換
4. Tab → 該行被 fix 替換；onChange 觸發；lint 重跑（diagnostic 消失或更新）
5. Esc → ghost 消失、編輯器無變化
6. 同時 ⌘K（D3）仍正常運作；先 ⌘K streaming 中再點 fix → 前一個 abort、新一個開始
7. Backend `/api/v1/copilot/inline/vrl` 422 路徑：`vrl_fix` 缺 `compile_error` / `mode != replace` / `compile_error` 全空白
8. `LLM_COPILOT_VRL_MODEL` 設 override → `vrl_fix` 也走 override
9. D1/D2/D3 行為不變（regression：panel chat / quick-buttons / Insert dialog / ⌘K）

---

## 9. Module 結構彙整

### 後端
```
app/modules/copilot/
├── constants.py                         ✎ +SKILL_VRL_FIX
├── schemas.py                            ✎ +InlineSkill, +skill/+compile_error +validators
└── services/
    ├── prompt_builder.py                 ✎ +_BLOCK1_VRL_FIX +dispatch in build_inline_system_blocks
    └── chat_service.py                   ✎ stream_inline 改 model dispatch by request.skill

app/modules/copilot/routers/chat_router.py ✎ DI 加 skill_models["vrl_fix"]

tests/unit/modules/copilot/
├── test_schemas.py                       ✎ +5 cases
├── test_prompt_builder.py                ✎ +4 cases
├── test_chat_service.py                  ✎ +2 cases
└── test_inline_router.py                 ✎ +2 cases
```

### 前端
```
web/lib/copilot/types.ts                  ✎ +InlineSkill +skill?+compile_error?
web/components/analyzer/
├── vrl-lint.ts                           ✎ +setVrlFixDispatcher +Diagnostic.actions
├── analyzer-view.tsx                     ✎ +useEffect register dispatcher
└── __tests__/
    ├── vrl-lint.test.ts                  ★ 新 (or 擴充)
    └── analyzer-view.fix.test.tsx        ★ 新
```

無新增依賴。

---

## 10. 風險與待確認

| 項目 | 處理 |
|---|---|
| `Diagnostic.actions` 在 CodeMirror 6 lint 的渲染樣式 | 內建支援，render 在 tooltip 底部為文字按鈕；無需自寫 popup |
| Lint debounce（既有 600ms）+ user 點 action 之間有 race | 接受。若 lint 重 run 把 diagnostic 換了，user 點下的 action 仍 reference 原 diagnostic（closure 拿到的是當下 message） |
| 多 diagnostic 同時存在（多個錯誤），user 點哪個先 fix？ | 一次只一個 InlineState；先點先做，第二次點會 abort 前一個（dispatcher 入口檢查 active 並 abort） |
| Diagnostic 訊息含 ANSI 顏色 / 控制字元 | 既有 `vrl-lint.parseVrlDiagnostics` 已過濾；`compile_error` 後端只當文字塞 CDATA |
| LLM fix 不 compile（產出新的 error） | 接受。user 看 lint 重跑就會看到下一個 error，可再點 fix。D4 不做 self-heal loop |
| 多行 Diagnostic（一個 error 涵蓋多行） | `lineAt(diag.from)` 只取第一行 selection 範圍。實務上 VRL diagnostic 大多單行，可 cover 90%+ 場景；剩餘 case user 仍可用 ⌘K replace 模式選整段 |
| `vrl_fix` skill 與 `vrl_inline` 共用 `LLM_COPILOT_VRL_MODEL` env var | 接受。需求類似（短輸出、嚴格規範） |
| Backwards-compat：D3 既有 client 沒 `skill` 欄位 | Schema default `skill="vrl_inline"`；既有 frontend 不需任何改動 |

---

## 11. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| D5（可能）| Runtime parse error inline rewrite | 點 result-pane 某 log 的 error → Copilot 給 VRL 重寫建議。需設計「VRL 中該由哪段處理該 log」的 anchor 偵測 |
| E | LLM Pipeline | 爬文件、草稿、Review diff |
