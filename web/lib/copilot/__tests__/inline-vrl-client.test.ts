import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamInlineVrl } from "@/lib/copilot/inline-vrl-client";
import type { InlineVrlRequest } from "@/lib/copilot/types";

const REQ: InlineVrlRequest = {
  instruction: "x",
  mode: "insert",
  current_vrl: "",
  cursor_offset: 0,
  vrl_engine: "0.32",
  logs: [],
};

function makeFetchResponse(body: string, status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body));
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("streamInlineVrl", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function collect(req: InlineVrlRequest, signal: AbortSignal) {
    const out: unknown[] = [];
    for await (const ev of streamInlineVrl(req, signal)) out.push(ev);
    return out;
  }

  it("yields text_delta then done", async () => {
    fetchSpy.mockResolvedValue(
      makeFetchResponse(
        'event: text_delta\ndata: {"text":".dst"}\n\nevent: done\ndata: {}\n\n',
      ),
    );
    const events = await collect(REQ, new AbortController().signal);
    expect(events).toEqual([
      { type: "text_delta", text: ".dst" },
      { type: "done" },
    ]);
  });

  it("yields error+done on http 5xx", async () => {
    fetchSpy.mockResolvedValue(makeFetchResponse("", 500));
    const events = await collect(REQ, new AbortController().signal);
    expect(events[0]).toMatchObject({ type: "error", code: "http_error" });
    expect(events[events.length - 1]).toEqual({ type: "done" });
  });

  it("yields error+done on fetch throw", async () => {
    fetchSpy.mockRejectedValue(new Error("offline"));
    const events = await collect(REQ, new AbortController().signal);
    expect(events[0]).toMatchObject({ type: "error", code: "fetch_failed" });
    expect(events[events.length - 1]).toEqual({ type: "done" });
  });

  it("ignores malformed frames", async () => {
    fetchSpy.mockResolvedValue(
      makeFetchResponse(
        "event: text_delta\ndata: {bad json}\n\nevent: done\ndata: {}\n\n",
      ),
    );
    const events = await collect(REQ, new AbortController().signal);
    // malformed text_delta dropped; done still emitted
    expect(events).toEqual([{ type: "done" }]);
  });

  it("posts to /api/v1/copilot/inline/vrl", async () => {
    fetchSpy.mockResolvedValue(makeFetchResponse("event: done\ndata: {}\n\n"));
    await collect(REQ, new AbortController().signal);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/copilot/inline/vrl",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });
});
