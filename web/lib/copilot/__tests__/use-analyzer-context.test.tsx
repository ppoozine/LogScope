import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useAnalyzerCopilotContext } from "@/lib/copilot/hooks/use-analyzer-context";
import { useCopilotStore } from "@/lib/copilot/store";

beforeEach(() => {
  useCopilotStore.setState({
    isOpen: false,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
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
        }),
      { initialProps: { logs: ["a"] } },
    );
    expect(useCopilotStore.getState().pageContext?.logs).toEqual(["a"]);
    rerender({ logs: ["a", "b"] });
    expect(useCopilotStore.getState().pageContext?.logs).toEqual(["a", "b"]);
  });
});
