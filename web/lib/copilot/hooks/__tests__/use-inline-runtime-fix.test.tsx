import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useInlineRuntimeFix } from "@/lib/copilot/hooks/use-inline-runtime-fix";
import { useCopilotStore } from "@/lib/copilot/store";

const BASE_ARGS = {
  chipId: "chip-A",
  currentVrl: ". = parse_syslog!(.message)",
  failingLog: "<134>plain",
  runtimeError: "function call error",
  vrlEngine: "0.32" as const,
  logs: ["<134>plain", "<134>another"],
};

function makeFetchResponse(body: string, status = 200): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(c) {
        c.enqueue(encoder.encode(body));
        c.close();
      },
    }),
    { status, headers: { "content-type": "text/event-stream" } },
  );
}

describe("useInlineRuntimeFix", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    useCopilotStore.setState({ pendingInsert: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("transitions streaming → idle and calls requestInsert on done", async () => {
    fetchSpy.mockResolvedValue(
      makeFetchResponse(
        'event: text_delta\ndata: {"text":"FIXED_VRL"}\n\nevent: done\ndata: {}\n\n',
      ),
    );
    const { result } = renderHook(() => useInlineRuntimeFix());

    await act(async () => {
      await result.current.start(BASE_ARGS);
    });

    expect(result.current.state.kind).toBe("idle");
    const pending = useCopilotStore.getState().pendingInsert;
    expect(pending?.proposedVrl).toBe("FIXED_VRL");
  });

  it("transitions to error on SSE error event", async () => {
    fetchSpy.mockResolvedValue(
      makeFetchResponse(
        'event: error\ndata: {"code":"x","message":"boom"}\n\nevent: done\ndata: {}\n\n',
      ),
    );
    const { result } = renderHook(() => useInlineRuntimeFix());

    await act(async () => {
      await result.current.start(BASE_ARGS);
    });

    expect(result.current.state.kind).toBe("error");
    if (result.current.state.kind === "error") {
      expect(result.current.state.message).toBe("boom");
      expect(result.current.state.chipId).toBe("chip-A");
    }
  });

  it("error state when current_vrl is blank — does not call fetch", async () => {
    const { result } = renderHook(() => useInlineRuntimeFix());

    await act(async () => {
      await result.current.start({ ...BASE_ARGS, currentVrl: "   " });
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.current.state.kind).toBe("error");
  });

  it("cancel aborts streaming and goes idle", async () => {
    let release: (() => void) | undefined;
    fetchSpy.mockImplementation(
      () =>
        new Promise<Response>((_resolve, reject) => {
          release = () => reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        }),
    );
    const { result } = renderHook(() => useInlineRuntimeFix());

    const startPromise = act(async () => {
      await result.current.start(BASE_ARGS);
    });
    await Promise.resolve();
    expect(result.current.state.kind).toBe("streaming");

    act(() => {
      result.current.cancel();
    });
    release?.();
    await startPromise;

    expect(result.current.state.kind).toBe("idle");
  });

  it("starting a second chip aborts the first and switches state to second", async () => {
    let releaseA: (() => void) | undefined;
    fetchSpy.mockImplementationOnce(
      () =>
        new Promise<Response>((_resolve, reject) => {
          releaseA = () => reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        }),
    );
    fetchSpy.mockImplementationOnce(() =>
      Promise.resolve(makeFetchResponse("event: done\ndata: {}\n\n")),
    );
    const { result } = renderHook(() => useInlineRuntimeFix());

    const a = act(async () => {
      await result.current.start({ ...BASE_ARGS, chipId: "chip-A" });
    });
    await Promise.resolve();

    const b = act(async () => {
      await result.current.start({ ...BASE_ARGS, chipId: "chip-B" });
    });
    // Release chip-A before settling b so chip-B's SSE (which is faster) can
    // complete first. That keeps actScopeDepth restore order correct: b's
    // popActScope runs before a's (2→1→0) rather than the reverse (which
    // would leave depth at 1 after a's then fires, corrupting the next test).
    releaseA?.();
    await b;
    await a;
    // Drain any remaining React scheduler work and macrotask-deferred passive
    // effect cleanups that React 19 schedules via enqueueTask(setTimeout 0).
    await act(async () => {});
    await new Promise<void>((r) => setTimeout(r, 0));

    expect(["idle", "error"]).toContain(result.current.state.kind);
    if (result.current.state.kind === "error") {
      expect(result.current.state.chipId).toBe("chip-B");
    }
  });

  it("empty buffer at done yields error '回應為空'", async () => {
    fetchSpy.mockResolvedValue(makeFetchResponse("event: done\ndata: {}\n\n"));
    const { result } = renderHook(() => useInlineRuntimeFix());

    await act(async () => {
      await result.current.start(BASE_ARGS);
    });

    expect(result.current.state.kind).toBe("error");
    if (result.current.state.kind === "error") {
      expect(result.current.state.message).toBe("回應為空");
    }
  });
});
