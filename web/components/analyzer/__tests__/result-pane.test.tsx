import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResultPane } from "@/components/analyzer/result-pane";

vi.mock("@/lib/copilot/hooks/use-inline-runtime-fix", () => ({
  useInlineRuntimeFix: () => ({
    state: { kind: "idle" },
    start: vi.fn(),
    cancel: vi.fn(),
  }),
}));

const DEFAULT_D5_PROPS = {
  currentVrl: ". = parse_syslog!(.message)",
  vrlEngine: "0.32" as const,
  logs: [],
};

describe("ResultPane", () => {
  it("renders empty hint when parseResult is null", () => {
    render(<ResultPane parseResult={null} fields={[]} hasLogTypeContext={false} {...DEFAULT_D5_PROPS} />);
    expect(screen.getByText(/輸入 VRL/)).toBeInTheDocument();
  });

  it("renders compile_error banner", () => {
    render(
      <ResultPane
        parseResult={{
          kind: "compile_error",
          engine: "0.32",
          compile_error: "syntax oops",
          results: [],
        }}
        fields={[]}
        hasLogTypeContext={false}
        {...DEFAULT_D5_PROPS}
      />,
    );
    expect(screen.getByText("syntax oops")).toBeInTheDocument();
  });

  it("renders summary + per-line cards for kind=ok", () => {
    render(
      <ResultPane
        parseResult={{
          kind: "ok",
          engine: "0.32",
          summary: { total: 2, success: 2, error: 0 },
          results: [
            {
              index: 0,
              input: "log A",
              status: "success",
              output: { src_ip: "1.1.1.1", action: "allow" },
            },
            {
              index: 1,
              input: "log B",
              status: "success",
              output: { src_ip: "2.2.2.2", action: "deny" },
            },
          ],
        }}
        fields={[]}
        hasLogTypeContext={false}
        {...DEFAULT_D5_PROPS}
      />,
    );
    expect(screen.getByText(/✓ 2/)).toBeInTheDocument();
    expect(screen.getByText("log A")).toBeInTheDocument();
    expect(screen.getByText("log B")).toBeInTheDocument();
  });

  it("save buttons disabled without log_type context", () => {
    render(<ResultPane parseResult={null} fields={[]} hasLogTypeContext={false} {...DEFAULT_D5_PROPS} />);
    expect(screen.getByRole("button", { name: /存回 Library/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /存為 sample/ })).toBeDisabled();
  });

  it("renders RuntimeFixChip on error rows", () => {
    render(
      <ResultPane
        parseResult={{
          kind: "ok",
          engine: "0.32",
          summary: { total: 2, success: 1, error: 1 },
          results: [
            {
              index: 0,
              input: "log A",
              status: "success",
              output: { src_ip: "1.1.1.1" },
            },
            {
              index: 1,
              input: "broken csv ,,,",
              status: "error",
              error: "field 'timestamp' missing",
            },
          ],
        }}
        fields={[]}
        hasLogTypeContext={false}
        {...DEFAULT_D5_PROPS}
      />,
    );

    const chip = screen.getByRole("button", { name: /修復/ });
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).toContain("✨");
  });

  it("does not render RuntimeFixChip on success rows", () => {
    render(
      <ResultPane
        parseResult={{
          kind: "ok",
          engine: "0.32",
          summary: { total: 1, success: 1, error: 0 },
          results: [
            {
              index: 0,
              input: "log A",
              status: "success",
              output: { src_ip: "1.1.1.1" },
            },
          ],
        }}
        fields={[]}
        hasLogTypeContext={false}
        {...DEFAULT_D5_PROPS}
      />,
    );
    expect(screen.queryByRole("button", { name: /修復/ })).toBeNull();
  });
});
