# Copilot D5 — Runtime Parse-Error Inline Fix

**Spec ID**: D5
**狀態**: Draft
**建立日期**: 2026-05-10
**前置 Spec**: D2（vrl_generate / Insert dialog）、D3（inline endpoint / streaming infra）、D4（compile-error fix pattern）

---

## 1. 範圍

### 1.1 進 D5

D5 把既有 `AskCopilotChip`（D2 — runtime parse error → panel chat → vrl_generate → 等讀完 → 點 Insert chip → diff dialog → setVrl）升級為 inline 體驗：點 result-pane 上 error 行的 chip → 背後 streaming → 收到 vrl block 直接彈 D2 InsertVrlDialog → Confirm 套用。**完全跳過 panel chat 步驟**。

| 項目 | 內容 |
|---|---|
| Trigger | result-pane 內每個 error result card 的 chip |
| Streaming UX | Chip 原位變 spinner「⌛ 生成中… (點取消)」；再點 = abort |
| Skill | 新 `vrl_runtime_fix`（共用 `LLM_COPILOT_VRL_MODEL`）|
| Endpoint | **沿用** `POST /api/v1/copilot/inline/vrl`，透過 `skill` 欄位 dispatch |
| Mode | 強制 `replace` 涵蓋整段（selection 0..len(current_vrl)）|
| Done UX | 收到 done event → 把累積的 VRL 灌進 `store.requestInsert()` → D2 `InsertVrlDialog` 自動彈出（既有 layout-mounted 元件）|
| Cancel | 點 chip 第二次、或元件 unmount |
| 並發 | 一次只一個 in-flight；新 click 先 abort 既有 |

D5 是單一 milestone、單一 PR。

### 1.2 不進 D5

| 留給 | 內容 |
|---|---|
| 不做 | 多 in-flight 平行 runtime fix；保留既有 panel chat 路徑（明確刪除）|
| 未來 | 補一個「✦ 用 panel chat 細談」次按鈕（如果 production 觀察到 user 想看 LLM 解釋再決定）|

### 1.3 與既有 AskCopilotChip 的關係

D2 既有 `AskCopilotChip`（result-pane.tsx）會：
1. 開 panel
2. 構造 user message（含 1-based index、log snippet、error 訊息）
3. 走 `vrl_generate` skill streaming
4. assistant message done 後抽 ` ```vrl ` block 標 vrlBlock
5. user 看到 panel 內的 Insert chip → 點 → diff dialog 開 → Confirm → setVrl

D5 改造同個 chip 換新行為：
1. **不**開 panel
2. 直接 streaming `vrl_runtime_fix` skill 到 `/inline/vrl`
3. SSE done 累積完整 VRL → `store.requestInsert(...)`（D2 既有 store action）
4. `InsertVrlDialog` 自動彈
5. user Confirm → setVrl

明確：原有 panel chat 路徑**完全移除**（不再 `useStreamingChat.send` 或 `useCopilot.open()`）。InsertVrlDialog 已 mount 在 `<CopilotPanel/>` 旁同層、不依賴 panel open，可被任何路徑 trigger。

---

## 2. 架構總覽

```
┌── User journey ─────────────────────────────────────────────┐
│ 1. /analyzer 寫 VRL，某 log parse 失敗                       │
│ 2. ResultPane error card 內 chip「✨ 修復」                  │
│ 3. 點下 → chip 原位變 spinner「⌛ 生成中… (點取消)」          │
│ 4. 背後 stream POST /api/v1/copilot/inline/vrl               │
│    skill=vrl_runtime_fix, mode=replace, selection=0..end     │
│ 5. SSE text_delta 累積到 hook 內部 buffer                    │
│ 6. SSE done → store.requestInsert(buffer, syntheticId)       │
│ 7. InsertVrlDialog 自動彈 → diff (current vs proposed)       │
│ 8. Confirm → editorBridge.setVrl → 整段 VRL 換新             │
└──────────────────────────────────────────────────────────────┘

┌── Backend (small) ──────────────────────────────────────────┐
│  app/modules/copilot/                                        │
│    ├── constants.py             ✎+SKILL_VRL_RUNTIME_FIX      │
│    ├── schemas.py               ✎ extend InlineVrlRequest    │
│    │   +InlineSkill literal "vrl_runtime_fix"                │
│    │   +failing_log: str | None                              │
│    │   +runtime_error: str | None                            │
│    │   validator: vrl_runtime_fix → mode=replace             │
│    │     + selection 0..len(current_vrl)                     │
│    │     + failing_log/runtime_error 必填非空                │
│    ├── services/                                              │
│    │   ├── prompt_builder.py    ✎+_BLOCK1_VRL_RUNTIME_FIX    │
│    │   │     +dispatch +block2 加 <failing_log>/<runtime_error>│
│    │   └── chat_service.py      ✎ skill_models["vrl_runtime_fix"]│
│    │     (stream_inline 已 dispatch by request.skill — D4 完成)│
│    └── routers/chat_router.py   ✎ DI 加 vrl_runtime_fix      │
└──────────────────────────────────────────────────────────────┘

┌── Frontend (small) ─────────────────────────────────────────┐
│  web/lib/copilot/                                             │
│    ├── types.ts                ✎ InlineSkill +"vrl_runtime_fix"│
│    │                             +failing_log? +runtime_error?│
│    └── hooks/                                                 │
│        └── use-inline-runtime-fix.ts  ★新                     │
│            (idle/streaming/error state, abort, on-done →     │
│             store.requestInsert)                              │
│  web/components/analyzer/                                     │
│    └── result-pane.tsx         ✎ 改造 AskCopilotChip 用新 hook│
└──────────────────────────────────────────────────────────────┘
```

完全 reuse：D3 `/inline/vrl` endpoint、D3 `streamInlineVrl` SSE client、D2 `useCopilotStore.requestInsert`、D2 `InsertVrlDialog`、D2 editor bridge。

無新增 dependency。

---

## 3. 後端架構

### 3.1 Schemas — extend `InlineVrlRequest`

```python
InlineSkill = Literal["vrl_inline", "vrl_fix", "vrl_runtime_fix"]


class InlineVrlRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2_000)
    skill: InlineSkill = "vrl_inline"
    mode: InlineMode
    current_vrl: str = Field(default="", max_length=50_000)
    cursor_offset: int | None = Field(default=None, ge=0)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)
    vrl_engine: Literal["0.25", "0.32"] = "0.32"
    logs: list[str] = Field(default_factory=list, max_length=50)
    compile_error: str | None = Field(default=None, max_length=20_000)
    failing_log: str | None = Field(default=None, max_length=20_000)         # ★ 新
    runtime_error: str | None = Field(default=None, max_length=20_000)       # ★ 新

    # ... existing _check_offsets / _check_skill validators ...

    @model_validator(mode="after")
    def _check_runtime_fix(self) -> "InlineVrlRequest":
        if self.skill == "vrl_runtime_fix":
            if self.failing_log is None or not self.failing_log.strip():
                raise ValueError("vrl_runtime_fix skill requires non-empty failing_log")
            if self.runtime_error is None or not self.runtime_error.strip():
                raise ValueError("vrl_runtime_fix skill requires non-empty runtime_error")
            if self.mode != "replace":
                raise ValueError("vrl_runtime_fix skill requires mode=replace")
            if self.selection_start != 0 or self.selection_end != len(self.current_vrl):
                raise ValueError(
                    "vrl_runtime_fix skill requires selection to cover entire current_vrl "
                    "(selection_start=0, selection_end=len(current_vrl))"
                )
            if not self.current_vrl.strip():
                raise ValueError("vrl_runtime_fix skill requires non-empty current_vrl")
        return self
```

**Backwards-compat**：D3/D4 既有 client（不送 `failing_log`/`runtime_error`）行為不變；validator 只在 `skill="vrl_runtime_fix"` 時才嚴格。

### 3.2 Constants

```python
SKILL_VRL_RUNTIME_FIX = "vrl_runtime_fix"
```

### 3.3 PromptBuilder — `_BLOCK1_VRL_RUNTIME_FIX`

```
You are LogScope's runtime parse-error fixer. The user's VRL compiles
but fails to parse a specific log. You output ONLY a complete rewritten
VRL that handles the failing log — no prose, no fence, no explanation.

# Context
You receive:
- <current_vrl>: the user's current VRL (no markers; you replace it whole)
- <failing_log>: the specific log line that failed to parse
- <runtime_error>: the VRL runtime error message
- <logs>: a sample of all logs (for context — confirm fix doesn't break others)

# Process
1. Read <runtime_error>. Identify root cause:
   - missing field that current_vrl assumes exists
   - wrong type (e.g., field is array not string)
   - parse_* call failed on a structurally different log subtype
2. Read <failing_log> and <logs>. Confirm the field/structure that
   trips current_vrl.
3. Rewrite <current_vrl> minimally to handle the failing case:
   - prefer `??` fallback over removing logic
   - prefer `if exists()` over rewriting whole flow
   - DO NOT remove field extractions that work for other logs
4. Output the COMPLETE rewritten VRL. The output replaces all of
   <current_vrl>.

# Output rules (strict)
- Output ONLY raw VRL. No markdown fences, no prose, no comments.
- No leading/trailing newline.
- The output must be syntactically valid VRL of the engine version
  in <facts><vrl_engine>.
- If you cannot determine a fix from the data, output exactly:
  `// 無法修復：<原因>`

# Don't
- Don't invent fields not in <logs>.
- Don't hard-code values from <failing_log> as constants.
- Don't use VRL functions outside the standard set (parse_syslog,
  parse_json, parse_key_value/parse_kv, parse_regex, parse_csv,
  split, to_int/to_float/to_bool/to_string/to_timestamp, del,
  exists, string).

# Example
<facts><vrl_engine>0.32</vrl_engine></facts>
<current_vrl><![CDATA[
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.src_ip = parts[6]
]]></current_vrl>
<failing_log><![CDATA[
<134>Jan 15 plain-syslog-no-csv-tail
]]></failing_log>
<runtime_error><![CDATA[
function call error for "split": index 6 out of bounds (length: 1)
]]></runtime_error>

OUTPUT:
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.src_ip = parts[6] ?? null
```

### 3.4 PromptBuilder dispatch + block 2

`build_inline_system_blocks` 加 dispatch：

```python
def build_inline_system_blocks(request, *, max_log_lines, max_vrl_chars):
    if request.skill == "vrl_fix":
        block1_text = _BLOCK1_VRL_FIX
    elif request.skill == "vrl_runtime_fix":
        block1_text = _BLOCK1_VRL_RUNTIME_FIX
    else:
        block1_text = _BLOCK1_VRL_INLINE
    blocks = [{"type": "text", "text": block1_text, "cache_control": {"type": "ephemeral"}}]

    # current_vrl: vrl_runtime_fix 不 inject markers（整段 replace），直接 raw
    if request.skill == "vrl_runtime_fix":
        # No marker injection; selection covers whole VRL
        kept = request.current_vrl
        truncated_attr = f' truncated_to="{max_vrl_chars}"' if len(kept) > max_vrl_chars else ""
        if len(kept) > max_vrl_chars:
            kept = kept[:max_vrl_chars]
        parts: list[str] = [f"<facts><vrl_engine>{request.vrl_engine}</vrl_engine></facts>"]
        parts.append(
            f"<current_vrl{truncated_attr}><![CDATA[{_safe_cdata(kept)}]]></current_vrl>"
        )
        parts.append(
            f"<failing_log><![CDATA[{_safe_cdata(request.failing_log or '')}]]></failing_log>"
        )
        parts.append(
            f"<runtime_error><![CDATA[{_safe_cdata(request.runtime_error or '')}]]></runtime_error>"
        )
    else:
        # existing vrl_inline / vrl_fix path with marker injection
        safe_vrl = _sanitize_markers(request.current_vrl)
        marked_vrl = _inject_marker(safe_vrl, request)
        kept, truncated = _truncate_keeping_marker(marked_vrl, max_vrl_chars, request)
        parts: list[str] = [f"<facts><vrl_engine>{request.vrl_engine}</vrl_engine></facts>"]
        if kept is not None:
            attr = f' truncated_to="{max_vrl_chars}"' if truncated else ""
            parts.append(
                f"<current_vrl{attr}><![CDATA[{_safe_cdata(kept)}]]></current_vrl>"
            )
        if request.skill == "vrl_fix" and request.compile_error:
            parts.append(
                f"<compile_error><![CDATA[{_safe_cdata(request.compile_error)}]]></compile_error>"
            )

    if request.logs:
        showing = min(len(request.logs), max_log_lines)
        parts.append(f'<logs count="{len(request.logs)}" showing="{showing}">')
        for i, raw in enumerate(request.logs[:max_log_lines]):
            parts.append(
                f'  <log index="{i + 1}"><![CDATA[{_safe_cdata(raw)}]]></log>'
            )
        parts.append("</logs>")

    blocks.append({"type": "text", "text": "\n".join(parts)})
    return blocks
```

### 3.5 ChatService

無改動 —— D4 已把 `stream_inline` 的 model 改用 `request.skill` dispatch（commit `5d064ee`）。新 skill 自動透過 `_model_for(request.skill)` 查 `skill_models` dict。

### 3.6 DI — chat_router

```python
skill_models: dict[str, str] = {}
if settings.llm_copilot_vrl_model:
    skill_models["vrl_generate"] = settings.llm_copilot_vrl_model
    skill_models["vrl_optimize"] = settings.llm_copilot_vrl_model
    skill_models["vrl_inline"] = settings.llm_copilot_vrl_model
    skill_models["vrl_fix"] = settings.llm_copilot_vrl_model
    skill_models["vrl_runtime_fix"] = settings.llm_copilot_vrl_model     # ★ 新
```

無新 settings。

---

## 4. 前端架構

### 4.1 Frontend types — extend

```typescript
export type InlineSkill = "vrl_inline" | "vrl_fix" | "vrl_runtime_fix";

export type InlineVrlRequest = {
  instruction: string;
  skill?: InlineSkill;
  mode: InlineMode;
  current_vrl: string;
  cursor_offset?: number;
  selection_start?: number;
  selection_end?: number;
  vrl_engine: "0.25" | "0.32";
  logs: string[];
  compile_error?: string;
  failing_log?: string;          // ★ 新
  runtime_error?: string;        // ★ 新
};
```

### 4.2 useInlineRuntimeFix hook

```typescript
// web/lib/copilot/hooks/use-inline-runtime-fix.ts

type RuntimeFixState =
  | { kind: "idle" }
  | { kind: "streaming"; abort: AbortController; chipId: string }
  | { kind: "error"; message: string; chipId: string };

// Module-level singleton — at most one in-flight runtime fix per page.
let _state: RuntimeFixState = { kind: "idle" };
const _listeners = new Set<() => void>();

function setState(next: RuntimeFixState) {
  _state = next;
  for (const l of _listeners) l();
}

export function useInlineRuntimeFix() {
  const [, force] = useState(0);
  useEffect(() => {
    const l = () => force((n) => n + 1);
    _listeners.add(l);
    return () => { _listeners.delete(l); };
  }, []);

  const requestInsert = useCopilotStore((s) => s.requestInsert);

  const start = useCallback(async (args: {
    chipId: string;             // unique key per error result card
    currentVrl: string;
    failingLog: string;
    runtimeError: string;
    vrlEngine: "0.25" | "0.32";
    logs: string[];
  }) => {
    // Abort any in-flight before starting new
    if (_state.kind === "streaming") _state.abort.abort();

    if (!args.currentVrl.trim()) {
      setState({ kind: "error", message: "VRL 為空、無法修復", chipId: args.chipId });
      return;
    }

    const controller = new AbortController();
    setState({ kind: "streaming", abort: controller, chipId: args.chipId });

    let buffer = "";
    try {
      for await (const ev of streamInlineVrl({
        instruction: "Fix this runtime parse error",
        skill: "vrl_runtime_fix",
        mode: "replace",
        current_vrl: args.currentVrl,
        selection_start: 0,
        selection_end: args.currentVrl.length,
        vrl_engine: args.vrlEngine,
        logs: args.logs,
        failing_log: args.failingLog,
        runtime_error: args.runtimeError,
      }, controller.signal)) {
        if (ev.type === "text_delta") buffer += ev.text;
        else if (ev.type === "error") {
          setState({ kind: "error", message: ev.message, chipId: args.chipId });
          return;
        } else if (ev.type === "done") {
          if (buffer.trim()) {
            requestInsert(buffer, `runtime-fix-${args.chipId}-${Date.now()}`);
            setState({ kind: "idle" });
          } else {
            setState({ kind: "error", message: "回應為空", chipId: args.chipId });
          }
          return;
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setState({ kind: "idle" });
        return;
      }
      setState({ kind: "error", message: "連線中斷", chipId: args.chipId });
    }
  }, [requestInsert]);

  const cancel = useCallback(() => {
    if (_state.kind === "streaming") {
      _state.abort.abort();
      setState({ kind: "idle" });
    }
  }, []);

  return { state: _state, start, cancel };
}
```

### 4.3 result-pane.tsx 改造

舊 `AskCopilotChip` 整個替換為 `RuntimeFixChip`，使用新 hook：

```tsx
function RuntimeFixChip({
  index,
  input,
  error,
  currentVrl,
  vrlEngine,
  logs,
}: {
  index: number;          // 0-based ParseResultItem.index
  input: string;          // failing log line
  error: string;          // runtime error message
  currentVrl: string;
  vrlEngine: "0.25" | "0.32";
  logs: string[];
}) {
  const chipId = `${index}-${input.slice(0, 16)}`;
  const { state, start, cancel } = useInlineRuntimeFix();
  const isThis = (state.kind === "streaming" || state.kind === "error")
    && state.chipId === chipId;
  const isStreaming = isThis && state.kind === "streaming";
  const isError = isThis && state.kind === "error";

  const handle = () => {
    if (isStreaming) cancel();
    else start({
      chipId,
      currentVrl,
      failingLog: input,
      runtimeError: error,
      vrlEngine,
      logs,
    });
  };

  let label = "✨ 修復";
  let cls = "border-purple-300 bg-purple-50 text-purple-800 hover:bg-purple-100";
  if (isStreaming) {
    label = "⌛ 生成中… (點取消)";
    cls = "border-amber-300 bg-amber-50 text-amber-800";
  } else if (isError) {
    label = `⚠ ${state.message}（點重試）`;
    cls = "border-red-300 bg-red-50 text-red-800";
  }

  return (
    <button
      type="button"
      onClick={handle}
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px]",
        cls,
      )}
    >
      {label}
    </button>
  );
}
```

`ResultCard` 改為傳 `currentVrl` / `vrlEngine` / `logs` 進來（從 `ResultPane` 透過新 props 傳遞）。

`ResultPane` props 加：

```typescript
type Props = {
  parseResult: ParseResponse | null;
  fields: FieldSchemaRead[];
  onSaveBackToLibrary?: () => void;
  onSaveAsSample?: () => void;
  hasLogTypeContext: boolean;
  // ★ 新 — D5 runtime fix context
  currentVrl: string;
  vrlEngine: "0.25" | "0.32";
  logs: string[];
};
```

`analyzer-view.tsx` 在 render `<ResultPane>` 處加：

```tsx
<ResultPane
  // ... existing ...
  currentVrl={vrl}
  vrlEngine={engineVersion}
  logs={logs ? logs.split("\n").filter((l) => l.length > 0) : []}
/>
```

### 4.4 不動的東西

- D2 `InsertVrlDialog` 一行不改 —— 從 `requestInsert` action 觸發是 D2 既有路徑
- D2 editor bridge (`registerEditor` / `setVrl`) 一行不改
- D3 `streamInlineVrl` SSE client 一行不改
- D3/D4 inline state machine（CM6 ghost）一行不改
- D2 `useStreamingChat` panel chat 路徑一行不改
- `useCopilot` / panel open/close 一行不改

### 4.5 構件樹

```
app/modules/copilot/
├── constants.py                     ✎ +SKILL_VRL_RUNTIME_FIX
├── schemas.py                        ✎ +InlineSkill literal +failing_log/runtime_error
│                                       +_check_runtime_fix validator
└── services/
    └── prompt_builder.py             ✎ +_BLOCK1_VRL_RUNTIME_FIX +dispatch
                                         +block2 加 <failing_log>/<runtime_error>

app/modules/copilot/routers/chat_router.py  ✎ DI 加 vrl_runtime_fix

tests/unit/modules/copilot/
├── test_schemas.py                   ✎ +6 cases
├── test_prompt_builder.py            ✎ +4 cases
└── test_inline_router.py             ✎ +2 cases

web/lib/copilot/
├── types.ts                          ✎ InlineSkill +failing_log?/runtime_error?
└── hooks/
    └── use-inline-runtime-fix.ts     ★ 新

web/components/analyzer/
├── result-pane.tsx                   ✎ 替換 AskCopilotChip → RuntimeFixChip
│                                       +ResultPane props (currentVrl/vrlEngine/logs)
└── analyzer-view.tsx                 ✎ 傳 D5 context 進 ResultPane

web/components/analyzer/__tests__/
├── result-pane.runtime-fix.test.tsx  ★ 新
└── ...

web/lib/copilot/hooks/__tests__/
└── use-inline-runtime-fix.test.tsx   ★ 新
```

無新增依賴。

---

## 5. 資料流

### 5.1 完整 D5 流程

```
User /analyzer 寫 VRL，某 log parse 失敗
  ↓
ResultPane 渲 error result card，內含 RuntimeFixChip
  ↓
User 點 chip
  ↓
chipId = `${index}-${input.slice(0,16)}`
useInlineRuntimeFix.start({ chipId, currentVrl, failingLog, runtimeError, vrlEngine, logs })
  ↓
若已 in-flight: _state.abort.abort()
新 AbortController, setState({ kind: "streaming", abort, chipId })
  → chip 自動 re-render 為 spinner「⌛ 生成中… (點取消)」
  ↓
streamInlineVrl({
  instruction: "Fix this runtime parse error",
  skill: "vrl_runtime_fix",
  mode: "replace",
  current_vrl, selection_start: 0, selection_end: current_vrl.length,
  vrl_engine, logs,
  failing_log, runtime_error,
}, signal)
  → fetch POST /api/v1/copilot/inline/vrl
  ↓
Backend inline_router → chat_service.stream_inline:
  build_inline_system_blocks:
    block 1 = _BLOCK1_VRL_RUNTIME_FIX (cached)
    block 2 = <facts> + <current_vrl> (raw, 整段) + <failing_log> + <runtime_error> + <logs>
  model = self._model_for("vrl_runtime_fix") → settings.llm_copilot_vrl_model or default
  anthropic.messages.stream(...)
  async for text in stream.text_stream: yield SSE text_delta
  finally: yield SSE done
  ↓
Frontend hook for-await:
  text_delta → buffer += ev.text
  done → if buffer.trim():
            store.requestInsert(buffer, `runtime-fix-${chipId}-${Date.now()}`)
            setState({ kind: "idle" })  → chip 變回原狀
  ↓
store.pendingInsert = { proposedVrl: buffer, messageId: <synthetic> }
  ↓
InsertVrlDialog (D2 既有，layout-mounted)：偵測 pendingInsert !== null 時自動開
  - 顯示 diff: editorBridge.getVrl()  vs  buffer
  ↓
User Confirm:
  store.confirmInsert():
    editorBridge.setVrl(buffer)  → analyzer-view setVrl(buffer)
    pendingInsert = null
  ↓
analyzer-view 的 onChange / 自動 parse 鏈跑（D1/D2 既有）
  - parse 重跑 → result-pane 重 render → 新 errors 或無 errors
```

### 5.2 取消路徑

```
情境 A — User 在 streaming 中再點同一個 chip
  handle() 檢查 isStreaming → call cancel()
  cancel() → _state.abort.abort()，setState idle
  fetch reader 拋 AbortError → useInlineRuntimeFix catch → setState idle (idempotent)
  Chip 變回原狀

情境 B — User 在 streaming 中點另一個 error 的 chip
  start() 檢查 _state.kind === "streaming" → 先 _state.abort.abort()
  立即 setState 新 streaming（chipId 換新）
  舊 chip 失去 isThis 變回原狀；新 chip 變 spinner

情境 C — User 換頁離開 /analyzer
  ResultPane unmount → useInlineRuntimeFix 的 useEffect cleanup 移除 listener
  module-level singleton 仍持 streaming state，但無人聽 → leak protection
  → ResultPane re-mount 時讀到 stale state；改善：在 hook 外暴露 cleanup？
  簡化決策：useEffect cleanup 也呼 cancel() 強制 abort（每頁卸載就強斷）
```

修正：在 hook 內 `useEffect` cleanup 加 `cancel()`：

```typescript
useEffect(() => {
  const l = () => force((n) => n + 1);
  _listeners.add(l);
  return () => {
    _listeners.delete(l);
    if (_listeners.size === 0 && _state.kind === "streaming") {
      _state.abort.abort();
      setState({ kind: "idle" });
    }
  };
}, []);
```

——只有在最後一個 listener 卸載時才 abort（避免 chip A 用完 chip B 還在 listening 時誤殺）。

### 5.3 並發 / 多卡片

`_state` 是 module-level singleton。同時只有一個 streaming 實例。多個 `RuntimeFixChip` 都 read 同個 `_state`，但只有 `state.chipId === chipId` 的那個才顯示 streaming/error UI；其他都是 idle 樣。

當 user 點 chip B（A 已 streaming）：
1. `start()` 內偵測到 `_state.kind === "streaming"` → `_state.abort.abort()` → A 的 fetch 拋 AbortError，hook 內 catch 跳 idle 但...
2. 緊接 `setState({ kind: "streaming", abort: newController, chipId: B })`
3. 舊 A fetch 的 AbortError handler 跑時 `_state.kind === "streaming"` 已是 B、`chipId !== A`，所以不會誤改 state

——關鍵是 A 的 catch 裡只有「if AbortError → setState idle」會誤覆 B 的 streaming。修正：catch 內檢查 `chipId === args.chipId`：

```typescript
} catch (err) {
  if (_state.kind === "streaming" && _state.chipId !== args.chipId) {
    // We were superseded by a newer start(); don't touch state
    return;
  }
  if ((err as Error).name === "AbortError") {
    setState({ kind: "idle" });
    return;
  }
  setState({ kind: "error", message: "連線中斷", chipId: args.chipId });
}
```

同樣保護 done 與 error event 的 setState 路徑（在改 state 前確認還是自己的 chipId）。

---

## 6. 錯誤處理

| 情境 | 處理 |
|---|---|
| 無 API key | backend SSE error{no_api_key}+done → setState `{kind:"error", message:"Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY"}` → chip 顯紅，user 點 = 重試 |
| Anthropic 失敗 | SSE error{anthropic_failed}+done → chip 顯紅「Copilot 暫時無法回應」 |
| Network drop | reader 拋 → catch → setState error「連線中斷」 |
| current_vrl 為空 | hook 入口攔截，setState error 不發 request |
| LLM 輸出 empty buffer | done 時 `buffer.trim()` 為空 → setState error「回應為空」 |
| LLM 違反規則出 fence / prose | 不 strip；buffer 直接灌 InsertVrlDialog；user 看 diff 自決 |
| LLM 輸出 `// 無法修復：...` 註解 | 同上：user 看到一行 comment、可 Cancel |
| 用戶連點同一個 chip | handle() 內檢查 isStreaming → 第二次點是 cancel |
| 用戶點另一個 chip during streaming | start() abort 前者、立即開新；舊 chip 失去 isThis 變回原狀 |
| current_vrl 超 50KB | Pydantic 422 → fetch !ok → SSE http_error → setState error |
| failing_log/runtime_error 為空 | hook 入口由 args 帶入；result-pane 確保 error result card 才 render chip（input/error 都非空） |
| InsertVrlDialog 已開（pendingInsert 非空）user 點 chip | start() 仍會跑、stream 到底、再呼 requestInsert 覆寫 pendingInsert（舊的 dialog 內容換新）。可接受 |
| editor bridge 未 register（user 在非 /analyzer 頁）| chip 不會出現（result-pane 只在 /analyzer mount）；不需處理 |

---

## 7. 測試策略

### 7.1 Backend tests（擴充既有）

| 檔 | 重點 |
|---|---|
| `tests/unit/modules/copilot/test_schemas.py` | (1) `skill="vrl_runtime_fix"` 缺 failing_log → 422；(2) 缺 runtime_error → 422；(3) failing_log/runtime_error 全空白 → 422；(4) mode != replace → 422；(5) selection 不涵蓋整段 → 422；(6) current_vrl 為空 → 422；(7) 合法 request → ok |
| `tests/unit/modules/copilot/test_prompt_builder.py` | (1) `vrl_runtime_fix` block 1 含「runtime parse-error fixer」「Output ONLY raw VRL」「無法修復」；(2) block 2 不含 `<\|sel_start\|>`/`<\|sel_end\|>` markers（整段 replace 不需要）；(3) block 2 含 `<failing_log>` 與 `<runtime_error>`；(4) `vrl_inline` 與 `vrl_fix` 不含 `<failing_log>` |
| `tests/unit/modules/copilot/test_inline_router.py` | (1) vrl_runtime_fix 合法 request → 200 SSE；(2) vrl_runtime_fix 缺 failing_log → 422 |

### 7.2 Frontend tests

| 檔 | 重點 |
|---|---|
| `web/lib/copilot/hooks/__tests__/use-inline-runtime-fix.test.tsx` | (1) start → setState streaming，chipId 對；(2) text_delta 累積、done → store.requestInsert 被呼到含完整 buffer；(3) error event → setState error；(4) cancel → abort + idle；(5) 在 streaming 中 start 第二個 chip → 第一個 abort、第二個 streaming；(6) currentVrl 為空 → 立即 setState error 不發 request |
| `web/components/analyzer/__tests__/result-pane.runtime-fix.test.tsx` | (1) error card 內顯示 chip，預設「✨ 修復」；(2) 點下 chip → useInlineRuntimeFix.start 被呼、args 對；(3) hook state streaming + chipId 對 → chip 改文字「⌛ 生成中…」；(4) state error → chip 紅；(5) 多 error card 同時 render，只 streaming 那個變樣；(6) 點 chip 第二次 → cancel |

### 7.3 Manual smoke

1. /analyzer 寫 VRL，故意設 `parts[6]`（若 split 後不夠長就 runtime error）
2. 餵 logs：第一筆正常 syslog+CSV、第二筆 plain syslog 沒 CSV tail
3. result-pane 第二筆 error card 出現 chip「✨ 修復」
4. 點 chip → chip 變「⌛ 生成中… (點取消)」（panel **不**開）
5. 等 ~3-10 秒 → InsertVrlDialog 自動彈出，diff 顯示 current vs 新 VRL（新版含 `?? null`）
6. Confirm → editor 換新 VRL → 自動 parse 重跑 → 第二筆 result 變 success
7. 驗 cancel：再 trigger 一次，streaming 中點 chip → chip 變回原狀、無 dialog
8. Regression：D1 panel chat / D2 「✦ 解釋這幾筆 log」「✦ 生成 VRL」 / D3 ⌘K / D4 lint Fix-with-Copilot 仍正常

### 7.4 不寫的測試

- LLM 是否真的不出 fence/prose — flaky；觀察 production
- LLM 修法是否正確（會不會導致更多 errors）— 接受；user 看 diff 自決
- React StrictMode 雙 mount 是否誤建多 streaming — module-level singleton + listener Set 有處理；單元測 cover

---

## 8. 驗收標準

D5 是單一 milestone、單一 PR。

1. /analyzer 寫故意失敗的 VRL → result-pane 在 error card 顯示「✨ 修復」chip（取代既有 AskCopilotChip）
2. 點 chip → chip 原位變「⌛ 生成中… (點取消)」、panel **不**開
3. 收到 done → InsertVrlDialog 自動彈、diff 顯示 current vs proposed
4. Confirm → editor.setVrl 觸發、analyzer-view 自動 parse 重跑
5. Cancel（點 chip 第二次或 InsertVrlDialog 取消）→ editor 不變
6. 多 error card 同時存在，點 A 後再點 B → A abort、B 開始
7. Backend `/api/v1/copilot/inline/vrl` 422 路徑：vrl_runtime_fix 缺 failing_log / 缺 runtime_error / mode != replace / selection 不涵蓋整段 / current_vrl 為空
8. `LLM_COPILOT_VRL_MODEL` 設 override → vrl_runtime_fix 也走 override
9. D1/D2/D3/D4 行為不變（panel chat / quick-buttons / Insert dialog 從 panel 路徑 / ⌘K / Fix-with-Copilot lint action 全 OK）

---

## 9. Module 結構彙整

### 後端
```
app/modules/copilot/
├── constants.py                      ✎ +SKILL_VRL_RUNTIME_FIX
├── schemas.py                         ✎ +"vrl_runtime_fix" literal
│                                        +failing_log/runtime_error fields
│                                        +_check_runtime_fix validator
└── services/prompt_builder.py         ✎ +_BLOCK1_VRL_RUNTIME_FIX
                                          +dispatch in build_inline_system_blocks
                                          +block 2 加 <failing_log>/<runtime_error>

app/modules/copilot/routers/chat_router.py  ✎ DI skill_models["vrl_runtime_fix"]

tests/unit/modules/copilot/
├── test_schemas.py                    ✎ +7 cases
├── test_prompt_builder.py             ✎ +4 cases
└── test_inline_router.py              ✎ +2 cases
```

### 前端
```
web/lib/copilot/types.ts                ✎ InlineSkill +"vrl_runtime_fix"
                                           +failing_log? +runtime_error?

web/lib/copilot/hooks/use-inline-runtime-fix.ts                 ★ 新
web/lib/copilot/hooks/__tests__/use-inline-runtime-fix.test.tsx ★ 新

web/components/analyzer/result-pane.tsx       ✎ 替換 AskCopilotChip → RuntimeFixChip
                                                 +ResultPane props
web/components/analyzer/analyzer-view.tsx     ✎ 傳 D5 context 進 ResultPane
web/components/analyzer/__tests__/result-pane.runtime-fix.test.tsx  ★ 新
```

無新增依賴。

---

## 10. 風險與待確認

| 項目 | 處理 |
|---|---|
| Module-level singleton 與 React StrictMode 雙 mount | listener Set 有 idempotent add/remove；cleanup 只在最後一個 listener 走時 abort，避免 strict mode 重 mount 之間誤殺 |
| 同時點兩個 chip 的 race | start() 入口 abort；catch / done handler 用 chipId 比對避免誤覆 state（§5.3）|
| LLM 輸出整段 VRL 可能很長（接近 max_vrl_chars 50000） | InsertVrlDialog 已支援 max-h scroll；diff 演算法是 line-level、長 VRL 仍 OK |
| pendingInsert 被覆寫 | 接受。新 fix done 時直接覆寫舊 pendingInsert；舊的 dialog 內容會更新（user 看 dialog 顯示的是新 fix） |
| chip 改造刪除 vrl_generate panel chat 路徑 | 用戶接受（design Q1 確認）。若 production 觀察到 user 想看 LLM 解釋再 commit，可開 D6 加「✦ 細談」次按鈕 |
| failing_log 含 binary / control chars | _safe_cdata 處理 `]]>` 已足；其他控制字元 LLM 看到會自己處理 |
| current_vrl 與 selection_end 在前端構造時必須對齊 | hook 內 build request 用 `args.currentVrl.length`，確保 selection_end == len 不會差 |
| InsertVrlDialog mount 在 CopilotPanel 旁，但 CopilotPanel 只在 (authed) layout | result-pane 也在 (authed) → analyzer 路徑下；OK |
| 部分 logs 改善但其他 logs 退化 | LLM prompt 提醒「不要移除其他 logs 的處理」；user 看 diff 自決；parse 重跑也會立刻看到新 errors |
| 與 D2 Insert dialog 衝突（user 同時用 panel chat 觸發 vrl_generate） | 兩條都呼 requestInsert；後到的覆寫前面。可接受（罕見場景） |

---

## 11. 後續

- 若 production 觀察到 user 想看 LLM 解釋，可加「✦ 細談」次按鈕跳 panel chat（保留 D2 路徑可重生）
- 若 vrl_runtime_fix 與 vrl_inline/vrl_fix 想分開 model（runtime fix 通常更難、需 Sonnet），加 `LLM_COPILOT_RUNTIME_FIX_MODEL` env var（一行 settings + 一個 dict key）
- 「E — LLM Pipeline」與 Copilot 平行，獨立 track
