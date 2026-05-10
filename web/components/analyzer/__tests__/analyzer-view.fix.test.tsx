import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/analyzer/vrl-lint", async () => {
  const actual = await vi.importActual<typeof import("@/components/analyzer/vrl-lint")>(
    "@/components/analyzer/vrl-lint",
  );
  return {
    ...actual,
    setVrlFixDispatcher: vi.fn(),
  };
});

// Mock heavy dependencies that AnalyzerView depends on
vi.mock("@/lib/api/queries/analyzer", () => ({
  useParse: () => ({ mutate: vi.fn(), data: null, isPending: false }),
  useMatch: () => ({ mutate: vi.fn(), data: null, isPending: false }),
}));

vi.mock("@/lib/copilot/hooks/use-analyzer-context", () => ({
  useAnalyzerCopilotContext: vi.fn(),
}));

vi.mock("@/lib/copilot/hooks/use-inline-vrl", () => ({
  useInlineVrl: () => ({ send: vi.fn() }),
}));

vi.mock("@/lib/storage/analyzer-state", () => ({
  loadAnalyzerState: () => null,
  saveAnalyzerState: vi.fn(),
}));

vi.mock("@/components/analyzer/editor-pane", () => ({
  EditorPane: () => null,
}));

vi.mock("@/components/analyzer/log-pane", () => ({
  LogPane: () => null,
}));

vi.mock("@/components/analyzer/match-bar", () => ({
  MatchBar: () => null,
}));

vi.mock("@/components/analyzer/result-pane", () => ({
  ResultPane: () => null,
}));

vi.mock("@/components/analyzer/snippets-bar", () => ({
  SnippetsBar: () => null,
}));

vi.mock("@/components/analyzer/diff-pane", () => ({
  DiffPane: () => null,
}));

vi.mock("@/components/analyzer/save-sample-dialog", () => ({
  SaveSampleDialog: () => null,
}));

import { AnalyzerView } from "@/components/analyzer/analyzer-view";
import { setVrlFixDispatcher } from "@/components/analyzer/vrl-lint";

afterEach(() => {
  vi.clearAllMocks();
});

describe("AnalyzerView fix dispatcher wiring", () => {
  it("registers a dispatcher on mount", () => {
    render(<AnalyzerView preload={null} noKey={false} />);
    expect(setVrlFixDispatcher).toHaveBeenCalled();
    const arg = (setVrlFixDispatcher as unknown as { mock: { calls: [unknown[]] } }).mock.calls.at(
      -1,
    )?.[0];
    expect(typeof arg).toBe("function");
  });

  it("clears dispatcher on unmount", () => {
    const { unmount } = render(<AnalyzerView preload={null} noKey={false} />);
    (setVrlFixDispatcher as unknown as { mock: { calls: unknown[][] } }).mock.calls.length = 0;
    unmount();
    expect(setVrlFixDispatcher).toHaveBeenCalledWith(null);
  });
});
