import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { inlineField } from "@/components/analyzer/cm6-inline/inline-state";
import { useInlineVrl } from "@/lib/copilot/hooks/use-inline-vrl";
import type { InlineVrlRequest } from "@/lib/copilot/types";

function makeView(doc = "abc") {
  const state = EditorState.create({ doc, extensions: [inlineField] });
  return new EditorView({ state, parent: document.body });
}

const REQ: InlineVrlRequest = {
  instruction: "x",
  mode: "insert",
  current_vrl: "abc",
  cursor_offset: 0,
  vrl_engine: "0.32",
  logs: [],
};

describe("useInlineVrl", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("transitions streaming → ready on text_delta + done", async () => {
    const view = makeView();
    fetchSpy.mockResolvedValue(
      new Response(
        new ReadableStream({
          start(c) {
            const enc = new TextEncoder();
            c.enqueue(
              enc.encode('event: text_delta\ndata: {"text":"X"}\n\nevent: done\ndata: {}\n\n'),
            );
            c.close();
          },
        }),
        { status: 200 },
      ),
    );

    const { result } = renderHook(() => useInlineVrl(view));
    await act(async () => {
      await result.current.send(REQ);
    });

    const v = view.state.field(inlineField);
    expect(v.kind).toBe("ready");
    if (v.kind === "ready") expect(v.ghost).toBe("X");
    view.destroy();
  });

  it("transitions to error on SSE error event", async () => {
    const view = makeView();
    fetchSpy.mockResolvedValue(
      new Response(
        new ReadableStream({
          start(c) {
            const enc = new TextEncoder();
            c.enqueue(
              enc.encode(
                'event: error\ndata: {"code":"x","message":"boom"}\n\nevent: done\ndata: {}\n\n',
              ),
            );
            c.close();
          },
        }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => useInlineVrl(view));
    await act(async () => {
      await result.current.send(REQ);
    });
    const v = view.state.field(inlineField);
    expect(v.kind).toBe("error");
    if (v.kind === "error") expect(v.message).toBe("boom");
    view.destroy();
  });

  it("does nothing when view is null", async () => {
    const { result } = renderHook(() => useInlineVrl(null));
    await act(async () => {
      await result.current.send(REQ);
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
