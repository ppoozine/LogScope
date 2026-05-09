import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useAnalyzerCopilotContext } from "@/lib/copilot/hooks/use-analyzer-context";
import { useCopilotStore } from "@/lib/copilot/store";

import { vi } from "vitest";

beforeEach(() => {
  useCopilotStore.setState({
    isOpen: false,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
    editorBridge: { setVrl: null, getVrl: () => "" },
  });
});

describe("useAnalyzerCopilotContext", () => {
  it("dispatches pageContext on mount", () => {
    renderHook(() =>
      useAnalyzerCopilotContext({
        vrl: ". = .x",
        vrlEngine: "v0.32",
        logs: ["log a"],
        parseResults: [{ index: 1, status: "ok" }],
        matchTopCandidate: null,
        setVrl: vi.fn(),
        getVrl: vi.fn(() => ""),
      }),
    );
    const ctx = useCopilotStore.getState().pageContext;
    expect(ctx?.page).toBe("analyzer");
    expect(ctx?.vrl).toBe(". = .x");
    expect(ctx?.logs).toEqual(["log a"]);
  });

  it("clears pageContext on unmount", () => {
    const { unmount } = renderHook(() =>
      useAnalyzerCopilotContext({
        vrl: null,
        vrlEngine: null,
        logs: [],
        parseResults: [],
        matchTopCandidate: null,
        setVrl: vi.fn(),
        getVrl: vi.fn(() => ""),
      }),
    );
    expect(useCopilotStore.getState().pageContext).not.toBeNull();
    unmount();
    expect(useCopilotStore.getState().pageContext).toBeNull();
  });

  it("updates when state changes", () => {
    const { rerender } = renderHook(
      (props: { logs: string[] }) =>
        useAnalyzerCopilotContext({
          vrl: null,
          vrlEngine: null,
          logs: props.logs,
          parseResults: [],
          matchTopCandidate: null,
          setVrl: vi.fn(),
          getVrl: vi.fn(() => ""),
        }),
      { initialProps: { logs: ["a"] } },
    );
    expect(useCopilotStore.getState().pageContext?.logs).toEqual(["a"]);
    rerender({ logs: ["a", "b"] });
    expect(useCopilotStore.getState().pageContext?.logs).toEqual(["a", "b"]);
  });

  it("registers and unregisters editor bridge", () => {
    const setVrl = vi.fn();
    const getVrl = vi.fn(() => "current vrl");
    const { unmount } = renderHook(() =>
      useAnalyzerCopilotContext({
        vrl: "x", vrlEngine: null, logs: [], parseResults: [],
        matchTopCandidate: null,
        setVrl, getVrl,
      }),
    );
    const b1 = useCopilotStore.getState().editorBridge;
    expect(b1.setVrl).toBe(setVrl);
    expect(b1.getVrl()).toBe("current vrl");

    unmount();
    expect(useCopilotStore.getState().editorBridge.setVrl).toBeNull();
  });
});
