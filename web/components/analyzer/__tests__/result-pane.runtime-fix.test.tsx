import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResultPane } from "@/components/analyzer/result-pane";
import { useCopilotStore } from "@/lib/copilot/store";

const startMock = vi.fn();
const cancelMock = vi.fn();
let mockState: { kind: "idle" } | { kind: "streaming"; chipId: string } | {
  kind: "error";
  message: string;
  chipId: string;
} = { kind: "idle" };

vi.mock("@/lib/copilot/hooks/use-inline-runtime-fix", () => ({
  useInlineRuntimeFix: () => ({
    state: mockState,
    start: startMock,
    cancel: cancelMock,
  }),
}));

const ERROR_RESULT = {
  index: 0,
  input: "<134>failing log line",
  status: "error" as const,
  output: null,
  error: "function call error: index out of bounds",
};

const PARSE_RESULT_ERROR = {
  kind: "ok" as const,
  engine: "0.32" as const,
  compile_error: null,
  summary: { total: 1, success: 0, error: 1 },
  results: [ERROR_RESULT],
};

const BASE_PROPS = {
  parseResult: PARSE_RESULT_ERROR,
  fields: [],
  hasLogTypeContext: false,
  currentVrl: ". = parse_syslog!(.message)",
  vrlEngine: "0.32" as const,
  logs: ["<134>failing log line", "<134>good log"],
};

beforeEach(() => {
  startMock.mockReset();
  cancelMock.mockReset();
  mockState = { kind: "idle" };
  useCopilotStore.setState({ pendingInsert: null });
});

afterEach(() => {
  // RTL auto-unmounts
});

describe("RuntimeFixChip in ResultPane", () => {
  it("renders 修復 chip in default state", () => {
    render(<ResultPane {...BASE_PROPS} />);
    const chip = screen.getByRole("button", { name: /修復/ });
    expect(chip.textContent).toContain("✨");
  });

  it("clicking chip calls start with full args", () => {
    render(<ResultPane {...BASE_PROPS} />);
    fireEvent.click(screen.getByRole("button", { name: /修復/ }));
    expect(startMock).toHaveBeenCalledTimes(1);
    const args = startMock.mock.calls[0][0];
    expect(args.failingLog).toBe(ERROR_RESULT.input);
    expect(args.runtimeError).toBe(ERROR_RESULT.error);
    expect(args.currentVrl).toBe(BASE_PROPS.currentVrl);
    expect(args.vrlEngine).toBe(BASE_PROPS.vrlEngine);
    expect(args.logs).toEqual(BASE_PROPS.logs);
    expect(typeof args.chipId).toBe("string");
    expect(args.chipId.length).toBeGreaterThan(0);
  });

  it("displays spinner when state is streaming for this chip", () => {
    const expectedChipId = `0-${ERROR_RESULT.input.slice(0, 16)}`;
    mockState = { kind: "streaming", chipId: expectedChipId };
    render(<ResultPane {...BASE_PROPS} />);
    const chip = screen.getByRole("button", { name: /生成中/ });
    expect(chip.textContent).toContain("生成中");
  });

  it("displays error label when state is error for this chip", () => {
    const expectedChipId = `0-${ERROR_RESULT.input.slice(0, 16)}`;
    mockState = { kind: "error", message: "boom", chipId: expectedChipId };
    render(<ResultPane {...BASE_PROPS} />);
    const chip = screen.getByRole("button", { name: /boom/ });
    expect(chip.textContent).toContain("boom");
  });

  it("clicking chip while streaming this chip calls cancel", () => {
    const expectedChipId = `0-${ERROR_RESULT.input.slice(0, 16)}`;
    mockState = { kind: "streaming", chipId: expectedChipId };
    render(<ResultPane {...BASE_PROPS} />);
    fireEvent.click(screen.getByRole("button", { name: /生成中/ }));
    expect(cancelMock).toHaveBeenCalledTimes(1);
  });

  it("does NOT show streaming label for a different chipId", () => {
    mockState = { kind: "streaming", chipId: "different-chip" };
    render(<ResultPane {...BASE_PROPS} />);
    const chip = screen.getByRole("button", { name: /修復/ });
    expect(chip.textContent).not.toContain("生成中");
    expect(chip.textContent).toContain("修復");
  });
});
