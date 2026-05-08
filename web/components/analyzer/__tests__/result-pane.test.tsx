import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultPane } from "@/components/analyzer/result-pane";

describe("ResultPane", () => {
  it("renders empty hint when parseResult is null", () => {
    render(<ResultPane parseResult={null} fields={[]} hasLogTypeContext={false} />);
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
      />,
    );
    expect(screen.getByText(/✓ 2/)).toBeInTheDocument();
    expect(screen.getByText("log A")).toBeInTheDocument();
    expect(screen.getByText("log B")).toBeInTheDocument();
  });

  it("save buttons disabled without log_type context", () => {
    render(<ResultPane parseResult={null} fields={[]} hasLogTypeContext={false} />);
    expect(screen.getByRole("button", { name: /存回 Library/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /存為 sample/ })).toBeDisabled();
  });
});
