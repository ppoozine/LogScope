import { describe, expect, it, vi } from "vitest";

import { streamChat } from "@/lib/copilot/sse-client";

function makeResponse(body: string, init: ResponseInit = {}): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, init);
}

describe("streamChat", () => {
  it("parses text_delta + done frames", async () => {
    // Arrange
    const sse = [
      'event: text_delta\ndata: {"text":"hi"}\n\n',
      'event: text_delta\ndata: {"text":" there"}\n\n',
      "event: done\ndata: {}\n\n",
    ].join("");
    const fetchMock = vi.fn(async () => makeResponse(sse, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    // Act
    const events = [];
    for await (const ev of streamChat(
      {
        messages: [{ role: "user", content: "hi" }],
        skill: null,
        page_context: null,
      },
      new AbortController().signal,
    )) {
      events.push(ev);
    }

    // Assert
    expect(events).toEqual([
      { type: "text_delta", text: "hi" },
      { type: "text_delta", text: " there" },
      { type: "done" },
    ]);
  });

  it("yields error frame for HTTP non-200", async () => {
    // Arrange
    const fetchMock = vi.fn(async () => new Response("nope", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    // Act
    const events = [];
    for await (const ev of streamChat(
      { messages: [{ role: "user", content: "x" }], skill: null, page_context: null },
      new AbortController().signal,
    )) {
      events.push(ev);
    }

    // Assert
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({
      type: "error",
      code: "http_error",
      message: "伺服器回應 503",
    });
    expect(events[1]).toEqual({ type: "done" });
  });

  it("ignores malformed frames", async () => {
    // Arrange
    const sse = [
      "event: text_delta\ndata: not-json\n\n",
      'event: text_delta\ndata: {"text":"ok"}\n\n',
      "event: done\ndata: {}\n\n",
    ].join("");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => makeResponse(sse, { status: 200 })),
    );

    // Act
    const events = [];
    for await (const ev of streamChat(
      { messages: [{ role: "user", content: "x" }], skill: null, page_context: null },
      new AbortController().signal,
    )) {
      events.push(ev);
    }

    // Assert: malformed frame skipped, only ok + done
    expect(events).toEqual([{ type: "text_delta", text: "ok" }, { type: "done" }]);
  });
});
