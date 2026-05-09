# Copilot D1 — Chat Infra + SSE + Log 解釋技能

**Spec ID**: D1
**狀態**: Draft
**建立日期**: 2026-05-09
**前置 Spec**: A (Foundation), B (Library Min), C1 (Analyzer), C2 (Stats + Versions)

---

## 1. 範圍

### 1.1 進 v1（D1）

D1 是 Copilot 的第一個 vertical slice：跑通 SSE streaming + Anthropic 整合 + panel UI + 一個技能（Log 解釋）。

| 範疇 | 內容 |
|---|---|
| 後端 | 新增 `app/modules/copilot/`（router + service + prompt_builder + schemas）；新增 `POST /api/v1/copilot/chat`（SSE streaming） |
| Anthropic 整合 | 沿用 C1 的 `AsyncAnthropic` 模式；改用 `client.messages.stream()` async context manager 拿增量 chunk |
| 對話歷史 | Stateless backend，每次 request 帶完整 history；cap `MAX_HISTORY=20`；無 Redis session |
| Page context | Frontend 收集，隨 request body 一起送；D1 只實作 Analyzer page context |
| 技能 | Log 解釋（log_explain）一個技能 |
| 前端 panel | 沿用既有 scaffold（`copilot-panel.tsx` + `copilot-toggle.tsx`），fill in 真實 chat UI |
| 前端狀態 | 引入 Zustand store（`useCopilotStore`）取代既有 React Context；`useCopilot` hook 對外不變 |
| 前端 streaming | `fetch` + `ReadableStream` 自解 SSE frames（不用 `EventSource`，理由見 §10） |
| 持久化 | Zustand `persist` middleware 存 messages + isOpen 到 sessionStorage（換 tab 清空） |
| Prompt 結構 | 系統 prompt 用 XML tag 區分 facts vs hypotheses；明確 process steps + 「You must NOT」清單 + 1 則 few-shot example |

### 1.2 不進 D1（留給 D2 / D3）

| 留給 | 內容 |
|---|---|
| D2 | VRL 生成技能（panel mode）、`<比對 Library>` quick-button（reuse `/api/v1/analyzer/match`）、Library 列表頁 / Product 詳情頁 / Review 頁的 context injection |
| D3 | ⌘K inline VRL（CodeMirror ghost text + accept/reject） |
| 砍掉 | 「Library 比對 inline」獨立技能（與 C1 MatchBar 重疊；改用 quick-button + 既有 endpoint） |
| 不做 | Redis session 持久化、conversation summarization、tool_use、cross-device sync |

### 1.3 與 design doc v1.2 的偏離

兩處明確偏離（理由見 §10）：

1. **Streaming protocol**：design doc §8.6 寫 `EventSource`；本 spec 用 `fetch` + `ReadableStream`
2. **對話 session 儲存**：design doc §8.5 寫「Redis 對話 session TTL 1hr」；本 spec 用 client-side Zustand persist

---

## 2. 後端架構

### 2.1 模組樹

```
app/modules/copilot/
├── __init__.py
├── routers/
│   ├── __init__.py
│   └── chat_router.py            # POST /api/v1/copilot/chat
├── services/
│   ├── __init__.py
│   ├── chat_service.py           # 編排 prompt + 呼叫 Anthropic stream + yield SSE events
│   └── prompt_builder.py         # 純函式：建 system blocks + render <page_context> XML
├── schemas.py                    # Pydantic: ChatMessage, PageContext, ChatRequest, SSEEventModel
└── constants.py                  # SKILL_LOG_EXPLAIN, SSE event names, XML tag names
```

`main.py` 加掛：

```python
from app.modules.copilot.routers.chat_router import router as copilot_router
app.include_router(copilot_router, prefix="/api/v1/copilot", tags=["copilot"])
```

### 2.2 Schemas（`app/modules/copilot/schemas.py`）

```python
from typing import Literal
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)

class ParseResult(BaseModel):
    index: int
    status: Literal["ok", "error"]
    message: str | None = None  # error 時的 vrl runtime/compile error

class MatchHypothesis(BaseModel):
    vendor_slug: str
    product_slug: str
    log_type_name: str
    confidence: float

class PageContext(BaseModel):
    page: Literal["analyzer"]                  # D1 僅支援 analyzer；其他頁面前端不送 page_context
    vrl: str | None = None
    vrl_engine: str | None = None              # e.g. "v0.32"
    logs: list[str] = Field(default_factory=list)
    parse_results: list[ParseResult] = Field(default_factory=list)
    match_top_candidate: MatchHypothesis | None = None

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    skill: Literal["log_explain"] | None = None
    page_context: PageContext | None = None
```

驗證：
- 最後一則 `messages` 必須是 `role="user"`（router 入口檢查，回 422）
- `messages` body cap 是 40（defense in depth）；frontend store 已 cap 20、後端送 LLM 也 truncate 到 `MAX_HISTORY=20`。40 上限只攔意外狀況（直接打 API、frontend bug 等）

### 2.3 Endpoints

#### `POST /api/v1/copilot/chat`

**Auth**: 走既有 `current_user` dependency（與 `/api/v1/analyzer/match` 同款）

**Request body**: `ChatRequest`

**Response**: 一律 `200 OK` + `StreamingResponse(media_type="text/event-stream")`，**包含 API key 未設或 Anthropic 失敗的情境**——錯誤透過 SSE `error` event 回傳，不走 HTTP 5xx。理由：streaming endpoint 一旦 status code 寫進 response，前端就無法在同一條連線上再傳 typed error 給 UI；統一走 SSE event 讓前端處理路徑單一。422 validation 錯誤是例外（在 stream 開始之前，FastAPI 自動回 422 JSON）。

**SSE event types**（typed JSON payload）：

```
event: text_delta
data: {"text": "<chunk text>"}

event: error
data: {"code": "<machine_code>", "message": "<繁中說明>"}

event: done
data: {}
```

`code` 列舉：
- `no_api_key` — `ANTHROPIC_API_KEY` 未設
- `anthropic_failed` — SDK 拋 exception（rate limit / 5xx / network）
- `internal_error` — 任何其他未預期錯誤

**Sequence**:
1. Validate request（FastAPI 自動 + 「最後一則必須是 user」 manual check）
2. `chat_service.stream(request=request)` → async generator yield SSE event bytes（service 不需 user，auth 已在 router 層擋）
3. `StreamingResponse(generator, media_type="text/event-stream")`

### 2.4 ChatService（`app/modules/copilot/services/chat_service.py`）

```python
class ChatService:
    def __init__(
        self,
        *,
        anthropic_client: AsyncAnthropic,
        anthropic_api_key: str | None,
        model: str,
        max_history: int,
        max_log_lines_in_context: int,
        max_vrl_chars_in_context: int,
    ) -> None: ...

    async def stream(
        self, *, request: ChatRequest
    ) -> AsyncIterator[bytes]:
        """Yield SSE-formatted bytes."""
        if not self._api_key:
            yield self._sse("error", {"code": "no_api_key",
                                       "message": "Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY"})
            yield self._sse("done", {})
            return

        system_blocks = build_system_blocks(
            skill=request.skill,
            page_context=request.page_context,
            max_log_lines=self._max_log_lines_in_context,
            max_vrl_chars=self._max_vrl_chars_in_context,
        )
        anthropic_messages = _to_anthropic_messages(
            request.messages[-self._max_history:]
        )

        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=2048,
                system=system_blocks,
                messages=anthropic_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield self._sse("text_delta", {"text": text})
        except Exception:
            logger.exception("anthropic_stream_failed")
            yield self._sse("error", {"code": "anthropic_failed",
                                       "message": "Copilot 暫時無法回應，請稍後再試"})
        finally:
            yield self._sse("done", {})

    @staticmethod
    def _sse(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
```

**注意**：`stream.text_stream` 是 Anthropic SDK 抽象後的 async iterator，自動處理 `content_block_delta` 事件、合併 thinking blocks（如未來開）等。比手動處理 raw event 安全。

### 2.5 PromptBuilder（`app/modules/copilot/services/prompt_builder.py`）

純函式模組。對外暴露：

```python
def build_system_blocks(
    *,
    skill: Literal["log_explain"] | None,
    page_context: PageContext | None,
    max_log_lines: int,
    max_vrl_chars: int,
) -> list[dict]:
    """Returns Anthropic system parameter (list of TextBlockParam dicts).

    Block 1: persona + skill instruction (cache_control: ephemeral)
    Block 2: <page_context> XML (no cache, omitted if page_context is None)
    """
```

### 2.6 Prompt 內容

#### Block 1（cached，所有 log_explain 對話共用）

```
You are LogScope Copilot. The user is a security engineer.

Respond in 繁體中文. Engineers want answers, not paragraphs.

# Output rules
- Cite data by tag: "在 <logs> 的第 3 筆…"、"<current_vrl> 第 18 行…"
- Code in fenced blocks with language hint.
- For each claim about a field's MEANING (not just its position), end with
  one of: 〔依據：明確〕〔依據：推測〕〔依據：未知〕

# Skill: log_explain

## Process (follow in order)
1. For each log line, identify its FORMAT (syslog / json / cef / leef / kv /
   plain). Cite the structural cue (e.g., "JSON: 以 `{` 開頭").
2. Locate candidate fields by category: timestamp, source/destination IP,
   user/account, host, action/event, status code. State the literal value
   and its position in the line. Do NOT invent a field that is not visibly
   present.
3. Flag unusual values: malformed timestamps, private/public IP mix-ups,
   unusually long opaque strings, base64-looking blobs. State why it looks
   unusual; do NOT speculate on attack scenarios unless asked.
4. If multiple logs: add a "差異" section listing what changes line-by-line.
5. If <hypotheses> contains a match candidate: you may USE it as a hint for
   field naming conventions, but do NOT assert "this is X product" — say
   "符合 <hypotheses> 中的 X 候選" if the structure agrees, or "與 <hypotheses>
   候選不符" if it doesn't.

## You must NOT
- Invent fields, IPs, usernames, or values that are not literally in <logs>.
- Claim a vendor/product as fact. <hypotheses> entries are guesses from
  another LLM call, not ground truth.
- Generate VRL code in this skill. If asked, say: "VRL 生成是另一個技能，
  目前還沒開放。可在 Analyzer 編輯器自己寫，或之後等 Copilot D2。"
- Reference earlier turns that did not happen.
- Translate vendor-specific opcodes / hex codes you don't recognise — say
  〔依據：未知〕.

## Uncertainty rule
If you cannot determine something with the data shown, write
"無法判斷：<原因>" — never guess to fill space.

## Example (one log)

INPUT <logs>:
  <log index="1"><![CDATA[<134>Jan 15 10:23:45 fw01 PAN-OS 1,2024/01/15 10:23:45,007901000123,TRAFFIC,end,2049,2024/01/15 10:23:40,10.0.1.5,8.8.8.8,...]]></log>

GOOD OUTPUT:
這條看起來是 **syslog 格式**，內含 PAN-OS 結構化欄位（CSV 段）。
〔依據：明確〕`<134>` 是 syslog priority、`fw01` 是 hostname。

| 欄位 | 值 | 依據 |
|---|---|---|
| timestamp | `Jan 15 10:23:45` | 明確（syslog header）|
| host | `fw01` | 明確 |
| product 標識 | `PAN-OS` | 明確（出現在 message body）|
| serial number | `007901000123` | 推測（PAN-OS CSV 第 3 欄通常是 SN）|
| action | `TRAFFIC end` | 推測（PAN-OS CSV 慣例）|
| src_ip | `10.0.1.5` | 推測（無 header 標籤，依位置）|
| dst_ip | `8.8.8.8` | 推測（同上）|

異常：無。`8.8.8.8` 是 Google DNS、`10.0.1.5` 是私網，方向合理。
```

當 `skill is None` 且無 page_context（user 直接打開 panel 對話）：保留前段 persona + output rules，刪除 `# Skill: log_explain` 整段，改加一段「目前沒有 active skill。回答 user 一般 log/VRL/security 問題，簡短。」

#### Block 2（不 cache，每次重算）— page_context XML

當 `page_context is not None`：

```xml
<page_context page="analyzer">
  <facts>
    <vrl_lines>{n}</vrl_lines>
    <vrl_engine>{engine_or_unknown}</vrl_engine>
    <log_count>{n}</log_count>
    <parse_summary ok="{n}" error="{n}"/>
  </facts>

  <hypotheses>
    {if match_top_candidate:}
    <match_candidate source="MatchBar" vendor="{slug}" product="{slug}"
                     log_type="{name}" confidence="{0.94}"/>
  </hypotheses>

  <logs count="{total}" showing="{capped}">
    <log index="1"><![CDATA[{raw}]]></log>
    ...
  </logs>

  {if vrl:}
  <current_vrl truncated_to="{cap}">
    <![CDATA[{vrl content, possibly truncated}]]>
  </current_vrl>

  <parse_results>
    <result index="1" status="ok"/>
    <result index="2" status="error" message="{escaped}"/>
    ...
  </parse_results>
</page_context>
```

**XML escape 細節**：
- `<log>` 與 `<current_vrl>` 內容用 CDATA wrap，避免 escaping `<`、`>`、`&`
- CDATA 內若出現 `]]>`（極罕見）用 `]]]]><![CDATA[>` 拆分
- `<result message="...">` 是 attribute 不能用 CDATA，用 `xml.sax.saxutils.quoteattr`（自動 escape）
- Truncate 後的 `<current_vrl truncated_to="N">` 顯示 N，無 truncate 時 attribute 省略

#### prompt_builder 介面

```python
def build_system_blocks(
    *,
    skill: Literal["log_explain"] | None,
    page_context: PageContext | None,
    max_log_lines: int,
    max_vrl_chars: int,
) -> list[dict]:
    blocks = [
        {
            "type": "text",
            "text": _build_block1(skill),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if page_context is not None:
        blocks.append({
            "type": "text",
            "text": _render_page_context_xml(
                page_context,
                max_log_lines=max_log_lines,
                max_vrl_chars=max_vrl_chars,
            ),
        })
    return blocks


def _build_block1(skill: Literal["log_explain"] | None) -> str: ...
def _render_page_context_xml(ctx: PageContext, *, max_log_lines: int, max_vrl_chars: int) -> str: ...
```

### 2.7 Dependencies

DI 結構（chat_router）：

```python
async def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatService:
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key or "placeholder"
    )
    return ChatService(
        anthropic_client=client,
        anthropic_api_key=settings.anthropic_api_key,
        model=settings.llm_copilot_model,
        max_history=settings.llm_copilot_max_history,
        max_log_lines_in_context=settings.llm_copilot_max_log_lines_in_context,
        max_vrl_chars_in_context=settings.llm_copilot_max_vrl_chars_in_context,
    )
```

無 DB session 注入（D1 stateless，不查任何表）。

### 2.8 Settings 新增（`app/core/config.py`）

```python
class Settings(BaseSettings):
    # ... existing ...
    llm_copilot_model: str = "claude-haiku-4-5-20251001"
    llm_copilot_max_history: int = 20
    llm_copilot_max_log_lines_in_context: int = 20
    llm_copilot_max_vrl_chars_in_context: int = 4000
```

`.env.example` 同步加四行（沿用既有 `ANTHROPIC_API_KEY`）。

---

## 3. 前端架構

### 3.1 既有 scaffold（已存在，本 spec 改寫內容）

| 檔案 | 既有狀態 | D1 改動 |
|---|---|---|
| `web/components/providers/copilot-context.tsx` | React Context（`isOpen` / `toggle` / `close`） | **重構為 thin wrapper around Zustand store**；`useCopilot` hook 簽章不變、行為不變 |
| `web/components/layout/copilot-panel.tsx` | Sheet placeholder（顯示「即將開放」） | 改為真 chat UI（context strip + message list + input） |
| `web/components/layout/copilot-toggle.tsx` | 浮動 ✦ button（右下） | 加 ⌘\\ keymap；其餘外觀不變 |
| `web/app/(authed)/copilot/page.tsx` | 靜態說明頁 | D1 不動（D2 再做標準 standalone 頁） |
| `web/app/layout.tsx`（root） | 已 mount `CopilotProvider` | 不動（Zustand 不需要 Provider，但保留 hook 簽章相容） |
| `web/app/(authed)/layout.tsx` | 已 mount `<CopilotPanel/>` + `<CopilotToggle/>` | 不動 |

### 3.2 新增模組

```
web/lib/copilot/
├── store.ts                      # Zustand store: messages, isOpen, pageContext, isStreaming
├── sse-client.ts                 # streamChat() async generator (fetch + ReadableStream)
├── types.ts                      # ChatMessage / PageContext / SSEEvent / ChatRequestBody
│                                 #   (single source of truth, store + sse-client 都從這裡 import)
└── hooks/
    ├── use-streaming-chat.ts     # 主 hook: send / abort / streaming state selectors
    └── use-analyzer-context.ts   # /analyzer 頁專用：把 analyzer state 注入 store

web/components/copilot/
├── context-strip.tsx             # 脈絡 pill bar（顯示 page=analyzer 時的 facts）
├── message-list.tsx              # bubble list + auto-scroll-to-bottom
├── message-bubble.tsx            # user / assistant / error 三種樣式 + markdown render
├── chat-input.tsx                # textarea + send/stop button
├── streaming-indicator.tsx       # 串流中 dot animation
└── quick-buttons.tsx             # D1 只放「解釋這幾筆 log」一顆
```

### 3.3 Zustand store

```ts
// web/lib/copilot/store.ts
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type ChatMessage = {
  id: string;          // ulid 或 nanoid，便於 React key
  role: "user" | "assistant";
  content: string;
  error?: string;      // 只 assistant 可能有，bubble 顯示紅框
};

export type PageContext = {
  page: "analyzer";
  vrl: string | null;
  vrlEngine: string | null;
  logs: string[];
  parseResults: { index: number; status: "ok" | "error"; message?: string }[];
  matchTopCandidate: { vendorSlug: string; productSlug: string; logTypeName: string; confidence: number } | null;
};

type CopilotState = {
  isOpen: boolean;
  messages: ChatMessage[];
  pageContext: PageContext | null;
  isStreaming: boolean;
  abortController: AbortController | null;

  // actions
  toggle: () => void;
  open: () => void;
  close: () => void;
  setPageContext: (ctx: PageContext | null) => void;
  appendUserMessage: (content: string) => void;
  appendAssistantPlaceholder: () => string;            // returns the new assistant message id
  appendDelta: (id: string, delta: string) => void;
  finalizeMessage: (id: string) => void;
  setMessageError: (id: string, error: string) => void;
  setAbortController: (c: AbortController | null) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
};

export const useCopilotStore = create<CopilotState>()(
  persist(
    (set, get) => ({
      isOpen: false,
      messages: [],
      pageContext: null,        // 不 persist（見 partialize）
      isStreaming: false,
      abortController: null,

      toggle: () => set((s) => ({ isOpen: !s.isOpen })),
      open: () => set({ isOpen: true }),
      close: () => set({ isOpen: false }),
      // ... 其餘 actions
    }),
    {
      name: "logscope.copilot",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({ isOpen: s.isOpen, messages: s.messages }),  // 不存 pageContext / isStreaming / abortController
    },
  ),
);
```

**`useCopilot` hook 相容層**（`copilot-context.tsx`）：

```tsx
export function CopilotProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;          // no-op；保留以避免改動 root layout
}

export function useCopilot() {
  const isOpen = useCopilotStore((s) => s.isOpen);
  const toggle = useCopilotStore((s) => s.toggle);
  const close = useCopilotStore((s) => s.close);
  return { isOpen, toggle, close };
}
```

既有 `<CopilotPanel/>` 和 `<CopilotToggle/>` 不需改 import 即可運作。

### 3.4 SSE client（`web/lib/copilot/sse-client.ts`）

```ts
export type SSEEvent =
  | { type: "text_delta"; text: string }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

export async function* streamChat(
  body: ChatRequestBody,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch("/api/v1/copilot/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
    credentials: "include",
  });

  if (!res.ok) {
    yield {
      type: "error",
      code: "http_error",
      message: `伺服器回應 ${res.status}`,
    };
    yield { type: "done" };
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // 以 "\n\n" 分割 frame
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseFrame(frame);
      if (ev) yield ev;
    }
  }
}

function parseFrame(frame: string): SSEEvent | null {
  const lines = frame.split("\n");
  let event = "";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!event) return null;
  try {
    const parsed = data ? JSON.parse(data) : {};
    if (event === "text_delta") return { type: "text_delta", text: parsed.text };
    if (event === "error") return { type: "error", code: parsed.code, message: parsed.message };
    if (event === "done") return { type: "done" };
  } catch {
    /* ignore malformed */
  }
  return null;
}
```

### 3.5 useStreamingChat hook

```ts
export function useStreamingChat() {
  const store = useCopilotStore;

  const send = useCallback(async (text: string) => {
    const s = store.getState();
    if (s.isStreaming) return;                     // 防重入
    s.setStreaming(true);                          // 立刻 set，避免雙擊 race

    s.appendUserMessage(text);
    const assistantId = s.appendAssistantPlaceholder();
    const controller = new AbortController();
    s.setAbortController(controller);

    try {
      const messages = store.getState().messages.map((m) => ({ role: m.role, content: m.content }));
      // 移除剛塞的空 assistant placeholder
      const messagesForRequest = messages.slice(0, -1);

      for await (const ev of streamChat(
        {
          messages: messagesForRequest,
          skill: s.pageContext ? "log_explain" : null,
          page_context: s.pageContext ? toBackendShape(s.pageContext) : null,
        },
        controller.signal,
      )) {
        if (ev.type === "text_delta") store.getState().appendDelta(assistantId, ev.text);
        else if (ev.type === "error") store.getState().setMessageError(assistantId, ev.message);
        else if (ev.type === "done") {
          store.getState().finalizeMessage(assistantId);
          break;
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        store.getState().finalizeMessage(assistantId);
      } else {
        store.getState().setMessageError(assistantId, "連線中斷");
      }
    } finally {
      store.getState().setStreaming(false);
      store.getState().setAbortController(null);
    }
  }, [store]);

  const abort = useCallback(() => {
    const c = store.getState().abortController;
    c?.abort();
  }, [store]);

  return { send, abort };
}
```

### 3.6 Analyzer page context 注入

`web/components/analyzer/analyzer-view.tsx` 加：

```tsx
useAnalyzerCopilotContext({
  vrl,
  vrlEngine,
  logs,
  parseResults,
  matchTopCandidate,
});
```

Hook 實作：

```ts
// web/lib/copilot/hooks/use-analyzer-context.ts
export function useAnalyzerCopilotContext(state: AnalyzerStateForCopilot) {
  const setPageContext = useCopilotStore((s) => s.setPageContext);

  useEffect(() => {
    setPageContext({
      page: "analyzer",
      vrl: state.vrl || null,
      vrlEngine: state.vrlEngine || null,
      logs: state.logs,
      parseResults: state.parseResults,
      matchTopCandidate: state.matchTopCandidate,
    });
    return () => setPageContext(null);
  }, [
    setPageContext,
    state.vrl, state.vrlEngine,
    // logs / parseResults / matchTopCandidate 引用比較會抖；
    // 在 caller 側先 useMemo 穩定化，或在這裡用 JSON.stringify 當 dep key
    JSON.stringify(state.logs),
    JSON.stringify(state.parseResults),
    JSON.stringify(state.matchTopCandidate),
  ]);
}
```

換頁離開 `/analyzer` 時 cleanup 自動把 pageContext 設 null。

### 3.7 Panel 互動細節

| 互動 | 行為 |
|---|---|
| 浮動 ✦ button | 沿用既有 `copilot-toggle.tsx`（右下浮動圓鈕） |
| ⌘\\ keymap | **D1 新增** — global keydown listener 在 `copilot-toggle.tsx` 或 layout 層註冊 |
| Panel 打開 | Sheet 從右側滑入，width 380px |
| Context strip | Panel 頂部，顯示 pageContext 的 facts pill；無 pageContext 時隱藏整條 |
| Quick button | 「解釋這幾筆 log」— 點下去自動 send 預定 prompt：「請解釋 `<logs>` 中的這幾筆」（後端會看到 page_context.logs）。無 pageContext 時整列隱藏 |
| Send | 串流中 disabled |
| Stop button | 串流中替換 send button；點下 abort |
| Streaming indicator | 最後一則 assistant bubble 右下三點 animation |
| 重試 chip | error bubble 右下；點下重新呼叫 `send(同一段最後 user content)` |
| 訊息超過 20 則 | 前端 `appendUserMessage` 內部先 truncate 最早訊息 |

### 3.8 Markdown render

`message-bubble.tsx` 用 `react-markdown` + `remark-gfm`（只 assistant 訊息開 markdown）。Code block 不引入 syntax highlighter，用 monospace + 淺底色即可（避免 D1 多帶 highlight.js / shiki bundle）。

User 訊息純文字 `whitespace-pre-wrap`。

### 3.9 Dependencies（前端 package.json）

新增：

```json
{
  "dependencies": {
    "zustand": "^5.0.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0"
  }
}
```

`nanoid` 若已在則 reuse；無則加。

---

## 4. 資料流

### 4.1 完整 send 流程

```
User types in <ChatInput> → Enter / 點 Send
  ↓
useStreamingChat.send(text)
  ↓
store.setStreaming(true)                   # 立刻 set，防雙擊 race
store.appendUserMessage(text)              # UI 立刻顯示 user bubble
store.appendAssistantPlaceholder()         # UI 立刻顯示空 assistant bubble，回傳 assistantId
store.setAbortController(new AbortController())
  ↓
streamChat({ messages, skill, page_context }, signal)
  → fetch POST /api/v1/copilot/chat
  ↓
Backend chat_router.chat()
  → validate (last message must be user) → 422 if not
  → chat_service.stream(request=request)
    → no api_key? yield error+done; return
    → build_system_blocks(skill, page_context)
    → truncate messages[-MAX_HISTORY:]
    → async with anthropic.messages.stream(...) as stream:
        async for text in stream.text_stream:
          yield SSE "text_delta"
    → except: yield SSE "error"
    → finally: yield SSE "done"
  ↓
Frontend sse-client async generator
  → for each event:
      "text_delta" → store.appendDelta(assistantId, text)
                   → UI 自動 re-render（Zustand selector）
      "error"     → store.setMessageError(assistantId, msg)
      "done"      → store.finalizeMessage(assistantId); break loop
  ↓
finally: store.setStreaming(false); setAbortController(null)
```

### 4.2 Abort 流程

User 點 Stop:
1. `useStreamingChat.abort()` → controller.abort()
2. fetch reader 拋 AbortError
3. for-await-of 在 sse-client 內 throw → useStreamingChat catch AbortError → finalizeMessage with current partial text（無 error 標示）
4. Backend 的 stream context manager 在 client 斷線時也會 exit；Anthropic SDK 自行終止 stream（不會繼續計費）

### 4.3 換頁流程

1. User 在 `/analyzer` 開了 panel、發了訊息
2. 換到 `/library/cisco/asa` — analyzer-view unmount
3. `useAnalyzerCopilotContext` cleanup → `setPageContext(null)`
4. Library 頁不註冊 context（D1 不支援），pageContext 維持 null
5. Panel 仍持有 messages（Zustand 跨頁不變），context strip 自動隱藏，quick-button 自動隱藏
6. User 仍可繼續對話，但 backend 收到的 page_context 是 null

### 4.4 Streaming 中換頁

1. User 在 `/analyzer` 發訊息，正在 streaming
2. User 點選 nav 換到 `/library`
3. analyzer-view unmount → setPageContext(null)（**不影響當前 in-flight stream**，因為 request body 是發出當下 snapshot 的）
4. Panel 不 unmount（layout-level）→ stream 繼續累積到 store
5. User 切回 `/analyzer` → 看到完整訊息

---

## 5. 錯誤處理

| 情境 | Backend | Frontend |
|---|---|---|
| `ANTHROPIC_API_KEY` 未設 | service yield `error{code:"no_api_key"}` + `done` | bubble 紅框、訊息「Copilot 未啟用…」、不顯示重試 chip |
| Anthropic 503 / timeout / network | catch → `error{code:"anthropic_failed"}` + `done` | bubble 紅框 + 重試 chip |
| Anthropic content policy refusal | 視為正常 stream（LLM 自己回拒絕訊息） | 正常顯示 |
| Request 422（last message not user / messages 空） | FastAPI 標準 JSON | toast 顯示，不開始 streaming |
| Network drop mid-stream | reader.read() 拋 | catch → `setMessageError(id, "連線中斷")` + 重試 chip |
| User abort | AbortController.abort() | finalizeMessage with partial text；無 error 標示 |
| Frontend 同一 user 同時發兩則 | 第二次 send 立刻 return（`isStreaming=true` 防重入） | UI 上 send button 已 disable，理論上不發生 |
| MAX_HISTORY=20 溢出 | service silently slice `[-20:]` | 前端 store 也 cap 20，超過自動 shift 最早 |
| sessionStorage quota exceeded | n/a | Zustand persist 失敗會 console.warn；行為退化為純 in-memory |

---

## 6. 測試策略

### 6.1 Backend

| 測試檔 | 重點 |
|---|---|
| `tests/modules/copilot/test_prompt_builder.py` | (1) Block 1 字串含「log_explain」「You must NOT」「example」「〔依據：明確/推測/未知〕」段落；(2) Block 2 XML 結構：CDATA wrap、attribute escape、無 page_context 時不出現；(3) `match_top_candidate=None` 時 `<hypotheses>` 為空 element；(4) VRL 超過 max_vrl_chars 時 truncate 且 attribute `truncated_to=N`；(5) skill=None 時 block 1 沒有「Skill: log_explain」段 |
| `tests/modules/copilot/test_chat_service.py` | mock `AsyncAnthropic.messages.stream` 回 fake async iter（含 `__aenter__/__aexit__/text_stream`）；assert SSE bytes 序列為 `text_delta × N + done`；mock raise 後序列為 `error + done`；無 API key 序列為 `error{no_api_key} + done`；assert SSE frame 格式 `event: X\ndata: {...}\n\n` |
| `tests/modules/copilot/test_chat_router.py` | httpx ASGI client POST：(1) 200 + `text/event-stream` content-type；(2) body 含 expected event lines；(3) 無 auth → 401；(4) 422 (空 messages、最後不是 user)；(5) 422 (messages 超過 40) |

### 6.2 Frontend

| 測試檔 | 重點 |
|---|---|
| `web/lib/copilot/__tests__/sse-client.test.ts` | mock fetch 回固定 frame string（split into chunks）→ generator yield 預期 typed events；malformed frame 被忽略；HTTP 5xx 回 error+done |
| `web/lib/copilot/__tests__/store.test.ts` | actions 狀態轉移（appendUserMessage / appendDelta / finalizeMessage / setMessageError / cap MAX_HISTORY）；persist partialize 不存 pageContext |
| `web/lib/copilot/__tests__/use-streaming-chat.test.tsx` | MSW 模擬 SSE response；assert UI 增量更新；abort 行為 |
| `web/components/copilot/__tests__/copilot-panel.test.tsx` | open / close、send disabled when streaming、error bubble 顯示重試 chip、context strip pageContext=null 時隱藏 |
| `web/components/layout/__tests__/copilot-toggle.test.tsx` | 點擊 toggle、⌘\\ keymap、aria-label |
| `web/lib/copilot/__tests__/use-analyzer-context.test.ts` | mount 後 store.pageContext 正確；unmount 後 null |

### 6.3 不寫的測試（明確）

- LLM 輸出格式（如「assistant 是否真的用 〔依據：明確〕」）不寫硬性 unit test — flaky，靠 production sample 後續觀察
- E2E 跑真 Anthropic API — 不在 CI；改用 manual smoke test

---

## 7. 本地開發

### 7.1 docker-compose

無變更（D1 沒新 service）。

### 7.2 Makefile

無變更。

### 7.3 .env.example 新增

```
# Copilot
LLM_COPILOT_MODEL=claude-haiku-4-5-20251001
LLM_COPILOT_MAX_HISTORY=20
LLM_COPILOT_MAX_LOG_LINES_IN_CONTEXT=20
LLM_COPILOT_MAX_VRL_CHARS_IN_CONTEXT=4000
# 沿用 ANTHROPIC_API_KEY (C1 已有)
```

### 7.4 Migration

無（D1 不動 schema）。

---

## 8. 驗收標準

1. 登入後，每頁右下可看到 ✦ Copilot 浮動按鈕；點擊 / ⌘\\ 開啟 Sheet panel
2. Panel `isOpen` + `messages` persist 到 sessionStorage（F5 保留、關 tab 清空）
3. 在 `/analyzer` 頁：context strip 顯示 VRL/Logs/Parse pill；點「解釋這幾筆 log」quick-button 自動 send
4. 對話訊息逐字 streaming，不需等全部生成
5. 串流中 Send 變 Stop，可中斷；中斷後 partial text 保留
6. 串流錯誤（如 API key 未設、Anthropic 5xx）→ assistant bubble 紅框 + 錯誤訊息（API key 無重試 chip、5xx 有重試 chip）
7. 對話歷史超過 20 則時最早訊息被自動 shift（前後端各自 cap）
8. 切換到 `/library` / `/library/<v>/<p>`：context strip + quick-button 隱藏，對話歷史保留可繼續對話
9. 換頁 streaming 中：stream 不中斷，切回原頁可看到完整訊息
10. 後端 `prompt_builder` + `chat_service` + `chat_router` 三層測試通過；前端 `sse-client` + `store` + `use-streaming-chat` + `copilot-panel` 五層測試通過
11. C1 MatchBar / `/api/v1/analyzer/match` 行為不變（regression check）

---

## 9. Module 結構彙整

```
app/modules/copilot/                       # 後端新模組
├── routers/chat_router.py
├── services/chat_service.py
├── services/prompt_builder.py
├── schemas.py
└── constants.py

web/lib/copilot/                           # 前端新模組
├── store.ts
├── sse-client.ts
├── types.ts
└── hooks/{use-streaming-chat,use-analyzer-context}.ts

web/components/copilot/                    # 前端新元件
├── context-strip.tsx
├── message-list.tsx
├── message-bubble.tsx
├── chat-input.tsx
├── streaming-indicator.tsx
└── quick-buttons.tsx

web/components/providers/copilot-context.tsx     # 重構：thin Zustand wrapper
web/components/layout/copilot-panel.tsx          # 改寫：真 chat UI
web/components/layout/copilot-toggle.tsx         # 加 ⌘\ keymap
web/components/analyzer/analyzer-view.tsx        # 加 useAnalyzerCopilotContext()
app/core/config.py                               # 加 4 個 settings
app/main.py                                      # mount copilot router
```

---

## 10. 風險與待確認

| 項目 | 處理 |
|---|---|
| **Design doc §8.6 寫 `EventSource` 但實作用 fetch + ReadableStream** | 偏離。理由：`EventSource` 不支援 POST 與 custom body / Authorization；業界實踐（Vercel AI SDK、OpenAI 官方前端庫、Anthropic Workbench）皆走 fetch + ReadableStream。建議 design doc v1.3 修訂此條 |
| **Design doc §8.5 寫 Redis session TTL 1hr，本 spec 改 client-side Zustand** | 偏離。理由：D1 三技能多 single-shot，Redis schema/TTL race/per-tab key 是過早抽象。Zustand persist 已涵蓋「F5 保留、關 tab 清空」需求。Redis 留給未來若真有跨 device sync 需求再做。建議 design doc v1.3 將「對話 session」標為 optional/future |
| Anthropic SDK streaming 與 C1 既有 pin（`>=0.40,<1.0`）相容性 | 用同 pin；CI 跑時 lock `uv.lock`。實作前先確認 `messages.stream()` async context manager 在當前版本可用 |
| Few-shot example overfit PAN-OS 格式 | 接受。D1 example 校正 tone/answer structure，不 ground 在特定 vendor。D2 視 production samples 補 example pool |
| `〔依據：明確/推測/未知〕` LLM 是否穩定遵守 | 接受 unknown。D1 不寫硬性 unit test 驗 LLM 輸出格式（會 flaky）。後續看 production samples 再決定要不要 strict prompting 或 structured output |
| Page context 把 raw VRL 送進 LLM | 接受。VRL 是 user 自訂規則，無 PII。spec 寫進 user-facing 提示「不要在 VRL hard-code secret」（D2 補一個 banner） |
| Layout-level panel 在登出頁也可能被 mount | 不會 — `<CopilotPanel/>` + `<CopilotToggle/>` 已只 mount 在 `app/(authed)/layout.tsx`；`<CopilotProvider/>`（將 no-op 化）雖在 root 但無實際渲染 |
| Streaming response 與 FastAPI middleware（logging / metrics）相容 | C1 既有 middleware 對 streaming response 透明；實作時 smoke test 一次（看 access log 是否會等到 stream end 才寫） |
| Sheet 元件（shadcn）與 streaming 重 render 性能 | Sheet 是 Radix dialog；scroll 內容是獨立 div。Streaming 增量 render 只重 message-list，不重 Sheet shell。預期無 perf 問題 |
| `react-markdown` bundle size 增加 | 接受。約 +30KB gzip；換取 markdown render 質量。D1 接受 |
| 浮動 ✦ button 與 page 內容遮擋（如 analyzer 結果區） | 既有 placement 為右下 fixed；若實測有遮擋再調；spec 不預先處理 |

---

## 11. 後續 spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| D2 | Copilot — VRL 生成技能 + 三頁 context + quick-buttons | 加 VRL 生成（panel 模式，「Insert into editor」按鈕回寫 CodeMirror）、Library 列表 / Product 詳情 / Review 三頁 context、`<比對 Library>` quick-button（reuse `/api/v1/analyzer/match`）。可能引入 per-skill model override (`LLM_COPILOT_VRL_MODEL`) |
| D3 | Copilot — ⌘K inline VRL | CodeMirror 內嵌 ghost text + accept/reject。獨立 spec，因 UX 工程量遠大於 panel chat |
| E | LLM Pipeline | 爬文件、草稿、Review diff、source = `llm_generated`（與 Copilot 平行） |

---

## 附錄 A：SSE event 字串範例

```
event: text_delta
data: {"text":"這條"}

event: text_delta
data: {"text":"log 看起來是 syslog 格式。"}

event: done
data: {}
```

錯誤情境：

```
event: error
data: {"code":"no_api_key","message":"Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY"}

event: done
data: {}
```

## 附錄 B：Block 2 XML 範例（完整 Analyzer page）

```xml
<page_context page="analyzer">
  <facts>
    <vrl_lines>197</vrl_lines>
    <vrl_engine>v0.32</vrl_engine>
    <log_count>10</log_count>
    <parse_summary ok="7" error="3"/>
  </facts>

  <hypotheses>
    <match_candidate source="MatchBar" vendor="paloalto" product="pan-os"
                     log_type="traffic" confidence="0.94"/>
  </hypotheses>

  <logs count="10" showing="10">
    <log index="1"><![CDATA[<134>Jan 15 10:23:45 fw01 PAN-OS 1,2024/01/15 10:23:45,...]]></log>
    <log index="2"><![CDATA[<134>Jan 15 10:23:46 fw01 PAN-OS 1,2024/01/15 10:23:46,...]]></log>
  </logs>

  <current_vrl>
    <![CDATA[
. = parse_syslog!(.message)
.timestamp = to_timestamp!(.timestamp, "UTC")
    ]]>
  </current_vrl>

  <parse_results>
    <result index="1" status="ok"/>
    <result index="2" status="error" message="field 'timestamp' missing"/>
  </parse_results>
</page_context>
```
