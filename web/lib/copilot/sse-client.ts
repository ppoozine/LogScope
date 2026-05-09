import type { ChatRequestBody, SSEEvent } from "./types";

export async function* streamChat(
  body: ChatRequestBody,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent> {
  let res: Response;
  try {
    res = await fetch("/api/v1/copilot/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
      credentials: "include",
    });
  } catch (err) {
    yield {
      type: "error",
      code: "fetch_failed",
      message: (err as Error).message || "連線失敗",
    };
    yield { type: "done" };
    return;
  }

  if (!res.ok) {
    yield {
      type: "error",
      code: "http_error",
      message: `伺服器回應 ${res.status}`,
    };
    yield { type: "done" };
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    yield { type: "error", code: "no_body", message: "回應無內容" };
    yield { type: "done" };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx = buffer.indexOf("\n\n");
    while (idx !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseFrame(frame);
      if (ev) yield ev;
      idx = buffer.indexOf("\n\n");
    }
  }
}

function parseFrame(frame: string): SSEEvent | null {
  let event = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) data += line.slice("data:".length).trim();
  }
  if (!event) return null;
  let parsed: { text?: string; code?: string; message?: string } = {};
  if (data) {
    try {
      parsed = JSON.parse(data);
    } catch {
      return null;
    }
  }
  if (event === "text_delta" && typeof parsed.text === "string") {
    return { type: "text_delta", text: parsed.text };
  }
  if (event === "error" && parsed.code && parsed.message) {
    return { type: "error", code: parsed.code, message: parsed.message };
  }
  if (event === "done") return { type: "done" };
  return null;
}
