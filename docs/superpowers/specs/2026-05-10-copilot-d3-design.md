# Copilot D3 — ⌘K Inline VRL（CodeMirror Ghost Text + Accept/Reject）

**Spec ID**: D3
**狀態**: Draft
**建立日期**: 2026-05-10
**前置 Spec**: D1（Chat infra + SSE）、D2（vrl_generate / vrl_optimize / page_context union / per-skill model override）

---

## 1. 範圍

### 1.1 進 D3

D3 是 Copilot 的第三個 vertical slice：在 Analyzer VRL 編輯器內加入 ⌘K inline 補完。沿用 D1/D2 的 Anthropic streaming + SSE 架構，但：
- 完全獨立於 panel chat（不共享 store / endpoint / conversation）
- 直接操作 CodeMirror 6 的 EditorView（不經 React state 走整段 VRL replace）
- 新增 `vrl_inline` skill，prompt 規範「只輸出 raw VRL」

| 項目 | 內容 |
|---|---|
| Trigger | ⌘K（cursor 模式 = 無 selection 時插入；selection 模式 = 取代選取範圍）|
| Streaming UX | 邊 stream 邊跟字顯 ghost text |
| Accept/Reject | Tab 接受 / Esc 拒絕，搭配 floating hint bar 顯狀態 |
| Skill | 新 `vrl_inline`（reuse `LLM_COPILOT_VRL_MODEL` 與 D2 vrl_generate / vrl_optimize 共用）|
| Endpoint | 新 `POST /api/v1/copilot/inline/vrl`（SSE）|
| Conversation | 完全獨立於 panel chat |
| CM6 整合 | 自寫 StateField + decoration（不依賴 @codemirror/autocomplete）|
| Prompt input | 浮動 input widget（inline，非 modal、非 panel）|
| Abort triggers | Esc 鍵、user 在編輯區打字（docChanged）、hint bar X 按鈕 |

D3 是單一 milestone（無 M1/M2/M3 拆分），一個 PR ship 完。

### 1.2 不進 D3（留 D4+）

| 留給 | 內容 |
|---|---|
| D4 | 點 parse error 行 → Copilot 修錯（D2 spec §11 原本與 ⌘K 合併寫，D3 拆出）|
| 未來 spec | Library / Versions 頁的 inline 補完；inline 操作進 panel chat 歷史；多 ghost 並存 |
| 不做 | 多語系 input placeholder；inline 操作的 undo 原子化；streaming 中換 cursor 就 abort（過於敏感）|

### 1.3 與 D2 spec §11 的偏離

| 偏離 | 理由 |
|---|---|
| D2 spec §11 寫 D3 包含「點 parse error 行 → Copilot 修錯」，本 spec 拆出到 D4 | ⌘K UX + 後端 + ghost text 已是一個 spec 的分量；parse error fix 的 entry-point 與 prompt 與 ⌘K 分歧夠大，合併會讓 spec / plan / PR 過肥 |

---

## 2. 架構總覽

```
┌── Backend ──────────────────────────────────────────────────┐
│  app/modules/copilot/                                        │
│    ├── routers/inline_router.py  ★新                          │
│    │     POST /api/v1/copilot/inline/vrl  (SSE)              │
│    ├── schemas.py  ✎+InlineVrlRequest +InlineMode             │
│    ├── services/                                              │
│    │   ├── prompt_builder.py  ✎+_BLOCK1_VRL_INLINE +          │
│    │   │                         build_inline_system_blocks() │
│    │   └── chat_service.py    ✎+stream_inline()               │
│    │                              (reuse SDK / SSE / cache)   │
│    └── constants.py           ✎+SKILL_VRL_INLINE              │
└──────────────────────────────────────────────────────────────┘
                           │  SSE text_delta / done / error
                           ▼
┌── Frontend ─────────────────────────────────────────────────┐
│  web/lib/copilot/                                             │
│    ├── inline-vrl-client.ts ★新   fetch+ReadableStream        │
│    └── hooks/use-inline-vrl.ts ★新                            │
│                                                                │
│  web/components/analyzer/cm6-inline/  ★新目錄                  │
│    ├── inline-extension.ts        CM6 plugin composer + facet │
│    ├── inline-state.ts            StateField + StateEffect     │
│    ├── inline-decorations.ts      EditorView.decorations       │
│    ├── inline-keymap.ts           Prec.highest keymap         │
│    ├── ghost-text-widget.ts       多行 ghost decoration        │
│    ├── hint-bar-widget.ts         streaming/ready/error 狀態  │
│    └── prompt-input-widget.tsx    React Portal widget          │
│                                                                │
│  web/components/analyzer/                                      │
│    ├── editor-pane.tsx        ✎+onViewReady +inlineEnabled    │
│    └── analyzer-view.tsx      ✎+view ref +useInlineVrl +facet │
└──────────────────────────────────────────────────────────────┘
```

**完全獨立於 panel chat**：不共享 store、不共享 endpoint、不共享 conversation。Editor bridge `setVrl`/`getVrl`（D2 既有，給 panel 整段 Insert 用）**不複用** —— ⌘K accept 直接呼 `view.dispatch(transaction)`，partial replace + state idle 在同一 transaction 內，避免 React state 重設造成光標跳。

**新依賴**：無。CM6 (`@codemirror/state`, `@codemirror/view`) 已在；React Portal 用 `react-dom` 既有。

---

## 3. 後端架構

### 3.1 Schemas（`app/modules/copilot/schemas.py`）

```python
from typing import Literal
from pydantic import BaseModel, Field, model_validator

InlineMode = Literal["insert", "replace"]


class InlineVrlRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2_000)
    mode: InlineMode
    current_vrl: str = Field(default="", max_length=50_000)
    cursor_offset: int | None = Field(default=None, ge=0)        # mode=insert 必填
    selection_start: int | None = Field(default=None, ge=0)      # mode=replace 必填
    selection_end: int | None = Field(default=None, ge=0)        # mode=replace 必填
    vrl_engine: Literal["0.25", "0.32"] = "0.32"
    logs: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_offsets(self) -> "InlineVrlRequest":
        if self.mode == "insert":
            if self.cursor_offset is None or self.cursor_offset > len(self.current_vrl):
                raise ValueError("insert mode requires valid cursor_offset")
        else:  # replace
            if (self.selection_start is None or self.selection_end is None
                    or self.selection_start >= self.selection_end
                    or self.selection_end > len(self.current_vrl)):
                raise ValueError("replace mode requires valid selection range")
        return self
```

驗證：FastAPI 自動把 ValueError 轉 422 JSON。

### 3.2 Endpoint（`app/modules/copilot/routers/inline_router.py`）

```python
@router.post("/inline/vrl")
async def inline_vrl(
    request: InlineVrlRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    user: Annotated[User, Depends(current_user)],
) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream_inline(request=request),
        media_type="text/event-stream",
    )
```

`main.py` mount 同 prefix（`/api/v1/copilot`），完整 path = `/api/v1/copilot/inline/vrl`。

**Auth**：走既有 `current_user` dependency（與 D1 chat router 同款）。

**SSE event types**：與 D1 panel chat 完全相同（`text_delta` / `error` / `done`）。

### 3.3 ChatService.stream_inline（新方法，與 stream() 並列）

```python
async def stream_inline(self, *, request: InlineVrlRequest) -> AsyncIterator[bytes]:
    if not self._api_key:
        yield self._sse(SSE_EVENT_ERROR, {
            "code": ERROR_NO_API_KEY,
            "message": "Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY",
        })
        yield self._sse(SSE_EVENT_DONE, {})
        return

    system_blocks = build_inline_system_blocks(
        request,
        max_log_lines=self._max_log_lines,
        max_vrl_chars=self._max_vrl_chars,
    )
    user_message = {"role": "user", "content": request.instruction}

    try:
        async with self._client.messages.stream(
            model=self._model_for("vrl_inline"),
            max_tokens=1024,                          # inline 比 panel 短
            system=system_blocks,
            messages=[user_message],
        ) as stream:
            async for text in stream.text_stream:
                yield self._sse(SSE_EVENT_TEXT_DELTA, {"text": text})
    except Exception:
        logger.exception("anthropic_inline_failed")
        yield self._sse(SSE_EVENT_ERROR, {
            "code": ERROR_ANTHROPIC_FAILED,
            "message": "Copilot 暫時無法回應，請稍後再試",
        })
    finally:
        yield self._sse(SSE_EVENT_DONE, {})
```

**DI 改動**：`skill_models["vrl_inline"] = settings.llm_copilot_vrl_model`（與 vrl_generate / vrl_optimize 共用）。無新 settings。

### 3.4 PromptBuilder — `_BLOCK1_VRL_INLINE`（cached / ephemeral）

```
You are LogScope's inline VRL completer. The user will give a short
instruction (e.g., "加 dst_ip"). You output ONLY the VRL code that
goes into the editor — no prose, no fence, no explanation.

# Modes
You will receive ONE of:

  Mode A — INSERT
    <current_vrl> contains a marker `<|cursor|>`. Output the code
    that should be inserted at that position. Do NOT repeat any
    surrounding code.

  Mode B — REPLACE
    <current_vrl> wraps a `<|sel_start|>...<|sel_end|>` region.
    Output the code that REPLACES the region between those markers.
    Do NOT repeat any code outside the markers.

# Output rules (strict)
- Output ONLY raw VRL. No markdown fences (```), no comments
  explaining what you did, no leading/trailing prose.
- No trailing newline.
- The output should be syntactically valid VRL of the engine
  version specified in <facts><vrl_engine>.
- Use `??` fallback (not `!`) when extracting fields that may be
  absent across the <logs> sample.
- If the instruction is impossible from the data shown, output
  exactly: `// 無法生成：<原因>` (a single VRL comment).

# Don't
- Don't invent fields not visibly present in <logs>.
- Don't hard-code secrets (API keys, tokens, prod hostnames).
- Don't use VRL functions outside the standard set (parse_syslog,
  parse_json, parse_key_value/parse_kv, parse_regex, parse_csv,
  split, to_int/to_float/to_bool/to_string/to_timestamp, del,
  exists, string).

# Example A — INSERT
<facts><vrl_engine>0.32</vrl_engine></facts>
<current_vrl><![CDATA[
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.src_ip = parts[6]
<|cursor|>
]]></current_vrl>
<logs><log index="1"><![CDATA[<134>... 10.0.1.5,8.8.8.8 ...]]></log></logs>
INSTRUCTION: 加一個 dst_ip

OUTPUT:
.dst_ip = parts[7] ?? null

# Example B — REPLACE
<facts><vrl_engine>0.32</vrl_engine></facts>
<current_vrl><![CDATA[
. = parse_syslog!(.message)
<|sel_start|>parts = split(string!(.message), ",")
.src_ip = parts[6]<|sel_end|>
]]></current_vrl>
INSTRUCTION: 改用 parse_regex 命名群組

OUTPUT:
m = parse_regex!(string!(.message), r'(?P<src_ip>\d+\.\d+\.\d+\.\d+)')
.src_ip = m.src_ip
```

### 3.5 `build_inline_system_blocks()`

```python
def build_inline_system_blocks(
    req: InlineVrlRequest,
    *,
    max_log_lines: int,
    max_vrl_chars: int,
) -> list[dict]:
    """Block 1 cached (persona + skill); Block 2 facts + marked vrl + logs."""
    # Block 1
    block1 = {
        "type": "text",
        "text": _BLOCK1_VRL_INLINE,
        "cache_control": {"type": "ephemeral"},
    }

    # Marker injection — sanitize current_vrl first against accidental marker collision
    safe_vrl = _sanitize_markers(req.current_vrl)
    marked_vrl = _inject_marker(safe_vrl, req)

    # Truncation: if marker falls outside truncated window, fallback to no-vrl prompt
    if len(marked_vrl) > max_vrl_chars:
        truncated, marker_intact = _smart_truncate(marked_vrl, max_vrl_chars, req)
        if marker_intact:
            marked_vrl = truncated
            truncated_attr = f' truncated_to="{max_vrl_chars}"'
        else:
            marked_vrl = None       # fallback: omit <current_vrl> entirely
            truncated_attr = ""
    else:
        truncated_attr = ""

    # Block 2 XML
    parts = [f'<facts><vrl_engine>{req.vrl_engine}</vrl_engine></facts>']
    if marked_vrl is not None:
        parts.append(
            f'<current_vrl{truncated_attr}>'
            f'<![CDATA[{_safe_cdata(marked_vrl)}]]>'
            f'</current_vrl>'
        )
    if req.logs:
        showing = min(len(req.logs), max_log_lines)
        parts.append(f'<logs count="{len(req.logs)}" showing="{showing}">')
        for i, raw in enumerate(req.logs[:max_log_lines]):
            parts.append(f'  <log index="{i + 1}"><![CDATA[{_safe_cdata(raw)}]]></log>')
        parts.append('</logs>')

    block2 = {"type": "text", "text": "\n".join(parts)}

    return [block1, block2]


def _inject_marker(vrl: str, req: InlineVrlRequest) -> str:
    if req.mode == "insert":
        i = req.cursor_offset or 0
        return vrl[:i] + "<|cursor|>" + vrl[i:]
    # replace
    s, e = req.selection_start or 0, req.selection_end or 0
    return vrl[:s] + "<|sel_start|>" + vrl[s:e] + "<|sel_end|>" + vrl[e:]


def _sanitize_markers(vrl: str) -> str:
    """If user's VRL contains literal markers we use, swap to a fallback
    sentinel so prompt isn't ambiguous."""
    for marker in ("<|cursor|>", "<|sel_start|>", "<|sel_end|>"):
        if marker in vrl:
            vrl = vrl.replace(marker, marker.replace("|", "_"))
    return vrl
```

### 3.6 後端構件樹（追加）

```
app/modules/copilot/
├── routers/inline_router.py             ★ 新
├── schemas.py                            ✎ +InlineVrlRequest +InlineMode
├── services/
│   ├── prompt_builder.py                 ✎ +_BLOCK1_VRL_INLINE
│   │                                       +build_inline_system_blocks
│   └── chat_service.py                   ✎ +stream_inline
│                                            +skill_models["vrl_inline"]
└── constants.py                          ✎ +SKILL_VRL_INLINE
app/main.py                               ✎ mount inline_router
```

---

## 4. 前端架構

### 4.1 CM6 extension 結構（`web/components/analyzer/cm6-inline/`）

```
cm6-inline/
├── index.ts                  re-export inline-extension
├── inline-extension.ts       合成所有 plugin / facet（外部只 import 一個）
├── inline-state.ts           StateField + StateEffect + annotation
├── inline-decorations.ts     EditorView.decorations.compute
├── inline-keymap.ts          Prec.highest keymap（⌘K / Tab / Esc）
├── ghost-text-widget.ts      WidgetType（多行 ghost render）
├── hint-bar-widget.ts        WidgetType（streaming/ready/error 三態）
└── prompt-input-widget.tsx   React Portal widget
```

### 4.2 InlineState（核心 state machine）

```ts
type InlineState =
  | { kind: "idle" }
  | { kind: "prompting"; mode: "insert" | "replace";
       anchor: number;                         // insert: cursor offset; replace: selection.from
       selectionEnd: number | null;            // replace 時用
       inputValue: string }
  | { kind: "streaming"; mode; anchor; selectionEnd;
       ghost: string;
       abort: AbortController }
  | { kind: "ready"; mode; anchor; selectionEnd; ghost }
  | { kind: "error"; mode; anchor; message };

const setInlineState = StateEffect.define<InlineState>();
const internalGhostInsert = Annotation.define<true>();

const inlineField = StateField.define<InlineState>({
  create: () => ({ kind: "idle" }),
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setInlineState)) return effect.value;
    }
    // Auto abort: docChanged + state in active set + not our own change
    const active = ["prompting", "streaming", "ready"].includes(value.kind);
    if (tr.docChanged && active && !tr.annotation(internalGhostInsert)) {
      if ("abort" in value) value.abort?.abort();
      return { kind: "idle" };
    }
    return value;
  },
});
```

### 4.3 Decorations

```ts
EditorView.decorations.compute([inlineField], (state) => {
  const v = state.field(inlineField);
  if (v.kind === "idle") return Decoration.none;

  const builder = new RangeSetBuilder<Decoration>();

  if (v.kind === "prompting") {
    builder.add(v.anchor, v.anchor,
      Decoration.widget({ widget: new PromptInputWidget(v), side: 1 }));
  }

  if (v.kind === "streaming" || v.kind === "ready") {
    if (v.mode === "replace" && v.selectionEnd != null) {
      builder.add(v.anchor, v.selectionEnd,
        Decoration.mark({ class: "cm-inline-replace-original" }));
    }
    const at = v.mode === "insert" ? v.anchor : (v.selectionEnd ?? v.anchor);
    builder.add(at, at, Decoration.widget({
      widget: new GhostTextWidget(v.ghost, v.mode), side: 1,
    }));
    builder.add(at, at, Decoration.widget({
      widget: new HintBarWidget(v.kind, v.mode), side: 1,
    }));
  }

  if (v.kind === "error") {
    builder.add(v.anchor, v.anchor, Decoration.widget({
      widget: new HintBarWidget("error", v.mode, v.message), side: 1,
    }));
  }

  return builder.finish();
});
```

`Decoration.widget` `side: 1` = 游標排在 widget 之後。多行 ghost 的 `GhostTextWidget` 內部 `<div style="white-space: pre; pointer-events: none">`，line-wrap 不影響。

`cm-inline-replace-original` mark class CSS：半透明 + strikethrough，user 視覺上看到「這段會被換掉」。

### 4.4 Keymap（Prec.highest）

```ts
keymap.of([
  { key: "Mod-k", run: handleCmdK, preventDefault: true },
  { key: "Tab", run: handleTabAccept },         // 只在 ready 時 return true
  { key: "Escape", run: handleEscReject },      // 只在 active 時 return true
])
```

`handleCmdK(view)`：
1. 看 current state，若不在 idle → 先 abort + reset
2. 看 `view.state.selection.main`：empty → mode="insert", anchor=cursor offset；range → mode="replace", anchor=selection.from, selectionEnd=selection.to
3. dispatch `setInlineState.of({ kind: "prompting", mode, anchor, selectionEnd, inputValue: "" })`
4. return true

`handleTabAccept(view)`：
1. state 不是 ready → return false（讓 default Tab indent 跑）
2. dispatch transaction：
   - `changes: { from: anchor, to: (mode==="insert" ? anchor : selectionEnd), insert: ghost }`
   - `effects: setInlineState.of({ kind: "idle" })`
   - `annotations: internalGhostInsert.of(true)`
3. return true

`handleEscReject(view)`：
1. state is idle → return false（讓 default Esc 跑，例如關 popup）
2. abort if streaming
3. dispatch idle
4. return true

### 4.5 Prompt input widget（React Portal）

CM6 widget 不能直接 render React。在 `toDOM(view)` create native div、用 React Portal mount component 進去：

```tsx
class PromptInputWidget extends WidgetType {
  constructor(
    private state: PromptingState,
    private onSubmit: (text: string) => void,
    private onCancel: () => void,
  ) { super(); }

  toDOM(view: EditorView): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "cm-inline-prompt-host";
    const root = createRoot(wrap);
    root.render(<PromptInput
      initial={this.state.inputValue}
      onSubmit={this.onSubmit}
      onCancel={this.onCancel}
    />);
    (wrap as { __root?: Root }).__root = root;
    return wrap;
  }

  destroy(dom: HTMLElement): void {
    queueMicrotask(() => (dom as { __root?: Root }).__root?.unmount());
  }

  eq(other: PromptInputWidget): boolean {
    return other.state.inputValue === this.state.inputValue;
  }
}
```

`queueMicrotask(unmount)` 避免 React 18 strict mode 重 mount 時的 race。

`PromptInput` React 元件：autoFocus textarea + Enter submit + Esc cancel + 空字串時 submit disabled。

### 4.6 `useInlineVrl` hook

```ts
export function useInlineVrl(view: EditorView | null) {
  const send = useCallback(async (req: InlineVrlRequest) => {
    if (!view) return;
    const controller = new AbortController();
    view.dispatch({ effects: setInlineState.of({
      kind: "streaming", mode: req.mode, anchor: ...,
      selectionEnd: ..., ghost: "", abort: controller,
    })});

    try {
      for await (const ev of streamInlineVrl(req, controller.signal)) {
        const cur = view.state.field(inlineField);
        if (cur.kind !== "streaming") return;        // 已被 user abort
        if (ev.type === "text_delta") {
          view.dispatch({ effects: setInlineState.of({
            ...cur, ghost: cur.ghost + ev.text,
          })});
        } else if (ev.type === "error") {
          view.dispatch({ effects: setInlineState.of({
            kind: "error", mode: cur.mode, anchor: cur.anchor, message: ev.message,
          })});
        } else if (ev.type === "done") {
          view.dispatch({ effects: setInlineState.of({
            kind: "ready", mode: cur.mode, anchor: cur.anchor,
            selectionEnd: cur.selectionEnd, ghost: cur.ghost,
          })});
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        view.dispatch({ effects: setInlineState.of({
          kind: "error", mode: req.mode, anchor: ..., message: "連線中斷",
        })});
      }
    }
  }, [view]);

  return { send };
}
```

`error` state 自動 5 秒後 idle（`useEffect` watcher：state.kind === "error" → setTimeout 5000 → dispatch idle）。

### 4.7 SSE client（`inline-vrl-client.ts`）

與 `web/lib/copilot/sse-client.ts`（D1）同型 fetch + ReadableStream + `event: / data:` 解析。獨立檔案，因 request body 型別不同；解析邏輯完全相同（可未來抽 shared frame parser，本 spec 不做）。

### 4.8 EditorView ref + facet 注入

`@uiw/react-codemirror` 提供 `onCreateEditor: (view, state) => void` callback。

`editor-pane.tsx` 改：

```tsx
type Props = {
  // ... existing ...
  onViewReady?: (view: EditorView) => void;
  inlineEnabled?: boolean;        // 預設 false
};

const extensions = useMemo(() => {
  const exts = [vrlLanguage, placeholder("...")];
  if (onCheck) exts.push(makeVrlLinter(onCheck));
  if (inlineEnabled) exts.push(inlineExtension({
    engineVersion, getLogs, sendInlineRequest,
  }));
  return exts;
}, [onCheck, inlineEnabled, engineVersion]);

<CodeMirror ... onCreateEditor={onViewReady} />
```

`inlineExtension({ engineVersion, getLogs, sendInlineRequest })` 接受 callbacks（不是 React state 直接 closure）；用 `Facet.define()` 注入 CM6 plugin。`PromptInput.onSubmit` 從 facet 拿 `sendInlineRequest` —— 避免 stale closure。

`analyzer-view.tsx` 改：

```tsx
const [view, setView] = useState<EditorView | null>(null);
const { send } = useInlineVrl(view);
const sendRef = useRef(send);
sendRef.current = send;

const inlineProviders = useMemo(() => ({
  getEngineVersion: () => engineVersion,
  getLogs: () => logs.split("\n").filter((l) => l.length > 0),
  sendInlineRequest: (req: InlineVrlRequest) => sendRef.current(req),
}), [engineVersion, logs]);

<EditorPane
  ...
  inlineEnabled
  onViewReady={setView}
  inlineProviders={inlineProviders}    // 透過 prop 進 inlineExtension
/>
```

### 4.9 前端構件樹（追加）

```
web/lib/copilot/
├── inline-vrl-client.ts                 ★ 新
└── hooks/use-inline-vrl.ts              ★ 新
web/lib/copilot/types.ts                 ✎ +InlineVrlRequest +InlineMode
web/components/analyzer/cm6-inline/      ★ 新目錄
├── index.ts
├── inline-extension.ts
├── inline-state.ts
├── inline-decorations.ts
├── inline-keymap.ts
├── ghost-text-widget.ts
├── hint-bar-widget.ts
└── prompt-input-widget.tsx
web/components/analyzer/
├── editor-pane.tsx                      ✎ +onViewReady +inlineEnabled
└── analyzer-view.tsx                    ✎ +view ref +useInlineVrl +facet provider
```

---

## 5. 資料流

### 5.1 完整 ⌘K 觸發流程（Insert mode）

```
User 在 /analyzer，cursor 停在某行尾，按 ⌘K
  ↓
inline-keymap.handleCmdK(view):
  selection.main empty → mode="insert", anchor=cursor offset
  dispatch setInlineState.of({ kind: "prompting", ... })
  ↓
StateField update → decorations 重算 → PromptInputWidget 在 anchor render
React Portal mount autoFocus 的 textarea
  ↓
User 輸入「加一個 dst_ip」按 Enter
  ↓
PromptInput.onSubmit(text):
  facet.sendInlineRequest({
    instruction: text, mode: "insert",
    current_vrl: view.state.doc.toString(),
    cursor_offset: anchor,
    vrl_engine: facet.getEngineVersion(),
    logs: facet.getLogs(),
  })
  ↓
useInlineVrl.send:
  new AbortController
  dispatch setInlineState.of({ kind: "streaming", ghost: "", abort })
  PromptInputWidget unmount; GhostTextWidget + HintBarWidget mount
  HintBar 顯「⌛ 生成中… Esc 取消」
  ↓
streamInlineVrl(req, signal)
  → fetch POST /api/v1/copilot/inline/vrl
  ↓
Backend inline_router → chat_service.stream_inline:
  build_inline_system_blocks: inject <|cursor|> at offset N of current_vrl
  anthropic.messages.stream(model=vrl_model, system=blocks,
                            messages=[{role:"user", content: instruction}])
  async for text in stream.text_stream:
    yield SSE text_delta { text: "..." }
  finally: yield SSE done
  ↓
Frontend for-await:
  text_delta → dispatch setInlineState.of({ ...cur, ghost: cur.ghost + delta })
                ↓ GhostTextWidget DOM 增量更新
  done → dispatch setInlineState.of({ kind: "ready", ... })
         HintBar 切「✓ Tab 接受 · Esc 拒絕」
  ↓
User 按 Tab:
  inline-keymap.handleTabAccept(view):
    state is ready, anchor=N, ghost=".dst_ip = parts[7] ?? null"
    dispatch ChangeSet.of({ from: N, to: N, insert: ghost })
              + setInlineState.of({ kind: "idle" })
              + annotations: internalGhostInsert.of(true)
    GhostTextWidget unmount, HintBar unmount
  ↓
analyzer-view 的 onChange 觸發 setVrl(view.state.doc.toString())
  ↓
useEffect debounced parse 自動跑（既有 D1 邏輯）
useAnalyzerCopilotContext 推新 vrl 到 panel store（既有 D1 邏輯）
```

### 5.2 Replace mode 差異

差異只有兩處：
- `handleCmdK`：`selection.main` 不 empty → `mode="replace"`, `anchor=selection.from`, `selectionEnd=selection.to`
- `handleTabAccept` transaction：`{ from: anchor, to: selectionEnd, insert: ghost }`（取代而非插入）
- Decoration：streaming/ready 階段 selection 範圍多一個 `cm-inline-replace-original` mark（半透明刪除線）

### 5.3 Abort 路徑

| 情境 | 觸發點 | 處理 |
|---|---|---|
| Esc 鍵 | inline-keymap.handleEscReject | state.abort?.abort() + dispatch idle |
| 編輯區打字 | StateField.update 偵測 docChanged + active state + 無 internalGhostInsert annotation | 自動 abort + idle |
| 點 hint bar X | HintBarWidget onClick | dispatch idle（無 abort 因無 streaming）|
| 換頁 unmount | CM6 plugin destroy | abort 任何 in-flight + cleanup |

### 5.4 Streaming 期間並發行為

| 情境 | 處理 |
|---|---|
| Stream 中 user 拖選 selection（不打字） | docChanged=false → 不 abort；anchor frozen，不影響 ghost 位置 |
| Stream 中 user 在 panel chat 也送 message | 兩個獨立 endpoint + controller，互不影響 |
| Stream 中 user 按 ⌘K | 先 abort 當前 + reset 至 idle，再開新 prompting |
| Replace mode：stream 中 user 改 selection 範圍 | selection 變不觸發 docChanged → 不 abort；接受時用 frozen 範圍（與目視 strikethrough 一致）|

### 5.5 Engine version / logs 注入

`analyzer-view.tsx` 經由 `inlineProviders` prop（callbacks）注入。callbacks 從 `useRef` mirror 最新值，`useMemo` deps 是 `[engineVersion, logs]`。CM6 facet 拿到的 `getLogs()` 永遠取最新值，避免 stale closure。

---

## 6. 錯誤處理

### 6.1 主要錯誤情境

| 情境 | 觸發點 | 行為 |
|---|---|---|
| `ANTHROPIC_API_KEY` 未設 | backend stream_inline | SSE error{no_api_key}+done → state error，HintBar 紅「Copilot 未啟用」+ 5s auto idle（無重試 chip）|
| Anthropic 503 / network | backend except | SSE error{anthropic_failed}+done → HintBar 紅「暫時無法回應，重新 ⌘K 試試」+ 5s auto idle |
| Network drop mid-stream | frontend reader.read() 拋 | catch → state error「連線中斷」+ 5s auto idle |
| HTTP 422（cursor_offset 超範圍） | FastAPI validator | response 不是 stream → fetch !ok → toast「請求格式錯誤」（前端應 clamp，不該發生）|
| LLM 輸出超 max_tokens（1024） | stream 自然結束但 ghost 不完整 | done 正常 → ready；ghost 顯實際拿到的；user 自決 Tab |
| LLM 輸出 fallback `// 無法生成：...` | stream 正常 | ready，ghost = comment；user 通常 Esc |
| LLM 違反規則出 fence ` ``` ` | stream 正常 | ghost 直接含 ```（不 strip；策略：信任 prompt + few-shot；觀察 production 後若頻繁則修 prompt v2）|
| User 在 prompting 中再按 ⌘K | keymap | 不 reset；input 仍 focus（已是 prompting）|
| User 在 streaming 中按 ⌘K | keymap | abort 當前 + reset，再開新 prompting |
| Streaming 中拉動其他 panel 打字 | docChanged 不在 editor 上 | stream 不中斷；ghost 持續 |
| Empty editor + insert mode | backend 接受 cursor_offset=0 | 正常 stream；Tab 寫入空編輯器 |
| Cursor offset 在 multi-byte char 中間 | JS string + Python str = UTF-16 code unit | 一致，相容 |
| `current_vrl` 超 50KB | Pydantic 422 | toast「VRL 太長無法 inline 編輯」|
| `instruction` 為空字串 | Pydantic 422 | input submit 時前端 trim 後檢查長度，disabled submit |

### 6.2 Stream 與 editor state 不一致

| 情境 | 處理 |
|---|---|
| Stream 中拖選 selection（不打字） | 不 abort（docChanged=false）；anchor frozen |
| Stream 中 ⌘+Z 讓 anchor 之前內容變了 | docChanged=true → 自動 abort |
| Streaming 結束後 user 改 doc 再按 Tab | docChanged → state idle → Tab 走 default indent |
| Replace mode：stream 中改 selection | selection 變不觸發 docChanged → 不 abort；接受時用 frozen 範圍 |

### 6.3 Resource leak 防護

| 風險 | 處理 |
|---|---|
| 多 in-flight fetch 並發（連按 ⌘K） | `useInlineVrl.send` 進入時若 active → 先 abort 再 trigger |
| AbortController 沒釋放 | StateField update 內離開 streaming 時 abort()；CM6 plugin destroy 時 abort |
| React Portal 沒 unmount | PromptInputWidget.destroy 內 queueMicrotask + root.unmount() |
| Backend stream_inline 在 client 斷時 | Anthropic SDK + httpx 自然 cleanup；async with 退出；無 retry/keep-alive |

---

## 7. 測試策略

### 7.1 Backend tests

| 檔 | 重點 |
|---|---|
| `tests/unit/modules/copilot/test_schemas.py`（擴充） | (1) insert 缺 cursor_offset → 422；(2) replace start>=end → 422；(3) cursor_offset > len(current_vrl) → 422；(4) selection_end > len(current_vrl) → 422；(5) 合法 insert / replace → ok；(6) instruction 空字串 → 422；(7) current_vrl="" + cursor_offset=0 + insert → ok |
| `tests/unit/modules/copilot/test_prompt_builder.py`（擴充） | (1) `build_inline_system_blocks` insert mode → block 1 含「Mode A」「Mode B」「ONLY raw VRL」；block 2 含 `<\|cursor\|>` 在 cursor_offset 位置；(2) replace mode → block 2 含 `<\|sel_start\|>` 與 `<\|sel_end\|>`；(3) `<facts><vrl_engine>` 正確；(4) logs cap max_log_lines；(5) current_vrl 超 max_vrl_chars + marker 在保留範圍 → truncate + truncated_to attr；(6) marker 落在被砍範圍 → fallback omit `<current_vrl>`；(7) user VRL 字面含 `<\|cursor\|>` → 被 sanitize |
| `tests/unit/modules/copilot/test_chat_service.py`（擴充） | (1) stream_inline 無 api_key → SSE error+done；(2) 正常路徑 mock anthropic stream → text_delta × N + done；(3) anthropic 拋 → SSE error+done；(4) `_model_for("vrl_inline")` 拿 override；(5) max_tokens=1024 |
| `tests/integration/modules/copilot/test_inline_router.py`（新） | httpx ASGI client：(1) 200 + text/event-stream；(2) body 含 expected events；(3) 無 auth → 401；(4) 422（缺欄位）；(5) current_vrl 超 50KB → 422 |

### 7.2 Frontend tests

| 檔 | 重點 |
|---|---|
| `web/lib/copilot/__tests__/inline-vrl-client.test.ts`（新） | mock fetch SSE frame → generator 預期 events；malformed frame ignore；HTTP 5xx 回 error+done；abort signal 觸發 AbortError |
| `web/lib/copilot/hooks/__tests__/use-inline-vrl.test.tsx`（新） | mock view.dispatch → assert state transitions；assert AbortController 在 unmount 後 abort |
| `web/components/analyzer/cm6-inline/__tests__/inline-state.test.ts`（新） | (1) StateField 對 setInlineState effect 反應；(2) docChanged + active state + 無 internalGhostInsert → 自動 idle；(3) docChanged + internalGhostInsert annotation → state 保留；(4) 多 effect 取最後 |
| `web/components/analyzer/cm6-inline/__tests__/inline-keymap.test.ts`（新） | EditorState.create 跑：(1) ⌘K 空 selection → prompting/insert；(2) ⌘K range selection → prompting/replace；(3) Tab 在 ready → 文字插入 + idle + true；(4) Tab 在 idle → false；(5) Esc 在 streaming → abort + idle + true；(6) Esc 在 idle → false |
| `web/components/analyzer/cm6-inline/__tests__/ghost-text-widget.test.tsx`（新） | toDOM 渲 ghost；ghost 改變時 eq() false → 重 render；多行 pre + white-space；replace mode strikethrough class |
| `web/components/analyzer/cm6-inline/__tests__/prompt-input-widget.test.tsx`（新） | toDOM 後 React mount；autoFocus；Enter onSubmit；Esc onCancel；destroy 後 unmount spy |
| `web/components/analyzer/__tests__/editor-pane.inline.test.tsx`（新） | inlineEnabled=false → extension 不被加；inlineEnabled=true → onCreateEditor 被呼、view 被傳；engineVersion 變化後 facet 拿到新值 |

### 7.3 Manual smoke（不上 CI）

PR 前要手動跑：

1. ⌘K cursor mode：cursor 在第 N 行尾、輸入「加 dst_ip」→ ghost 增量出現、Tab 接受寫入正確位置
2. ⌘K selection mode：選中 3 行、輸入「改用 parse_regex」→ ghost 在 selection 後、原 selection 半透明 strikethrough、Tab 取代正確
3. Esc 中斷 streaming → ghost 消失、editor 不變
4. Streaming 中在 editor 打字 → 自動 abort
5. ⌘K 後不打 instruction 直接 Esc → input 消失、無 stream
6. Empty editor + ⌘K +「寫一段 syslog parser」→ 正常生成
7. 連按 ⌘K 兩次 → 第二次 reset 第一次
8. Tab accept 後光標位置合理（在 ghost 結束處）
9. Ghost 多行時的視覺不破版
10. ⌘+Z undo accept 後的插入 → editor 還原

### 7.4 不寫的測試

- LLM 是否真的不出 fence、不出 prose — flaky；觀察 production sample
- LLM 對 ambiguous instruction 的處理品質
- React Portal 在 CM6 widget 內 lifecycle 所有邊角 → 用 manual smoke 代替
- 多 tab 同時 ⌘K → 完全獨立 endpoint，無 race

---

## 8. 驗收標準

D3 是單一 milestone，一個 PR ship 完。

1. /analyzer 頁，cursor 不選文字 + ⌘K → 浮動 input 在 cursor 上方、autofocus
2. Input「加一個 dst_ip」+ Enter → input 消失、ghost 增量出現在 cursor 後
3. Streaming 中 hint bar「⌛ 生成中… Esc 取消」；done 後切「✓ Tab 接受 · Esc 拒絕」
4. Tab → ghost 插入正確 cursor offset，editor 內容更新；onChange 觸發、parse 自動跑、CopilotPanel pageContext 更新
5. Esc → ghost 消失、editor 不變
6. 選中 3 行 + ⌘K → mode=replace；ghost 顯示在 selection 後、原 selection 半透明 strikethrough
7. Replace mode Tab → selection 範圍被 ghost 取代
8. Streaming 中在 editor 打字 → 立即 abort、ghost 消失
9. Streaming 中按 ⌘K → 先 reset 再開新 prompting
10. `ANTHROPIC_API_KEY` 未設 → hint bar 紅「Copilot 未啟用」，5s 後自動 idle
11. Anthropic 失敗 → hint bar 紅「暫時無法回應，重新 ⌘K 試試」
12. 換頁離開 /analyzer → fetch 自然 abort、無 console error
13. Backend `/api/v1/copilot/inline/vrl` 422 路徑（缺 cursor_offset / range 不合法 / current_vrl 超 50KB）
14. D1 / D2 行為不變（regression：panel chat / quick-buttons / Insert-from-panel-dialog 全部 OK）
15. `LLM_COPILOT_VRL_MODEL` 設 override 後，inline 與 panel vrl_generate 都走 override；未設則 fallback default

---

## 9. 風險與待確認

| 項目 | 處理 |
|---|---|
| LLM 不遵守「ONLY raw VRL，無 fence、無 prose」 | 接受 unknown。Few-shot 用 INPUT/OUTPUT 對放大規範。觀察 production sample；若頻繁出 fence/prose，prompt v2 加更強示警，不做 frontend strip（會誤砍合法 VRL `//` comment 起始行）|
| `<\|cursor\|>` marker 與 user VRL 內容衝突 | 極罕見。Backend `_sanitize_markers` 在 inject 前掃 marker 字串，命中時換 fallback 字串（`<_cursor_>` 等）|
| CM6 widget 內 React Portal lifecycle | 業界 pattern（prosemirror-view, tiptap）；風險主要在 destroy 時 race。實作用 `queueMicrotask(unmount)` 避免 React 18 strict mode 重 mount race |
| docChanged auto-abort 過敏 | replace mode 範圍變化看似敏感，但 CM6 區分 docChanged vs selectionSet 明確。Pure selection change 不 abort —— 預期行為 |
| `internalGhostInsert` annotation 漏 mark | Tab accept 是唯一 dispatch doc change + state idle 的路徑；單元測涵蓋；無漏 mark 風險 |
| Multi-byte chars 在 cursor offset / selection range | JS string + Python str index 都是 UTF-16 code unit；前後端一致 |
| `vrl_inline` 與 `vrl_generate` / `vrl_optimize` 共用 model env var | 接受。Inline 需求類似 generate（短輸出、嚴格規範），同模型合理 |
| Inline streaming 期間 panel 也 streaming | 後端兩獨立 endpoint、各自 SDK call；前端兩獨立 controller。已驗證 panel D1「streaming 中換頁」隔離 |
| Ghost text widget 在 line-wrap 編輯器寬度極窄時可能 overflow | 接受 v1。`overflow-x: auto` 內部捲軸 |
| ⌘K 與 OS / 瀏覽器快捷鍵衝突 | `Mod-k`（CM6 自動 mac=⌘ / win=Ctrl）+ `preventDefault: true`；只在 editor focus 生效 |
| Panel 與 inline 同時要不同 VRL model | YAGNI。短期共用 `LLM_COPILOT_VRL_MODEL`；未來分開時加 `LLM_COPILOT_INLINE_MODEL`（一行 settings + 一個 dict key）|
| Empty editor + insert mode 的 prompt 沒 `<current_vrl>` | 設計上 fallback：`<current_vrl><![CDATA[<\|cursor\|>]]></current_vrl>` —— LLM 看到空檔，依 instruction + logs 從零生成 |
| Library / 其他頁未來 reuse inline | `inlineEnabled=false` default；prompt 與 endpoint 是 VRL-specific（`vrl_inline` skill）。其他頁面屬新 spec |
| 跨 turn cache hit | block 1 ephemeral cache 有效（內容 stable）；block 2 每次 marker 位置不同 → 不 cache，OK |

---

## 10. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| D4 | Copilot — Parse error inline fix | 點 parse error 行 → Copilot 給修正建議。可複用 D3 ghost text infra；但 entry-point 與 prompt 分歧夠大，獨立 spec |
| E | LLM Pipeline | 爬文件、草稿、Review diff、source = `llm_generated`（與 Copilot 平行） |

---

## 附錄 A：完整 SSE event 範例（Insert mode 成功）

```
event: text_delta
data: {"text":"."}

event: text_delta
data: {"text":"dst_ip"}

event: text_delta
data: {"text":" = parts[7]"}

event: text_delta
data: {"text":" ?? null"}

event: done
data: {}
```

## 附錄 B：完整 Block 2 XML 範例（Replace mode）

```xml
<facts><vrl_engine>0.32</vrl_engine></facts>
<current_vrl>
<![CDATA[
. = parse_syslog!(.message)
<|sel_start|>parts = split(string!(.message), ",")
.src_ip = parts[6]<|sel_end|>
]]>
</current_vrl>
<logs count="3" showing="3">
  <log index="1"><![CDATA[<134>Jan 15 10:23:45 fw01 1,...,10.0.1.5,8.8.8.8,...]]></log>
  <log index="2"><![CDATA[<134>Jan 15 10:23:46 fw01 1,...,10.0.1.6,8.8.4.4,...]]></log>
  <log index="3"><![CDATA[<134>Jan 15 10:23:47 fw01 1,...,10.0.1.7,1.1.1.1,...]]></log>
</logs>
```
