import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResultPane } from "@/components/analyzer/result-pane";

const openSpy = vi.fn();
vi.mock("@/components/providers/copilot-context", () => ({
  useCopilot: () => ({ isOpen: false, toggle: vi.fn(), close: vi.fn(), open: openSpy }),
}));

const sendSpy = vi.fn();
vi.mock("@/lib/copilot/hooks/use-streaming-chat", () => ({
  useStreamingChat: () => ({ send: sendSpy, abort: vi.fn() }),
}));

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

  it("renders ✦ Ask Copilot chip on error rows; click opens panel + sends vrl_generate", () => {
    openSpy.mockReset();
    sendSpy.mockReset();

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
      />,
    );

    const chip = screen.getByRole("button", { name: /問 Copilot 怎麼修/ });
    expect(chip).toBeInTheDocument();

    fireEvent.click(chip);
    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(sendSpy).toHaveBeenCalledTimes(1);
    const [text, options] = sendSpy.mock.calls[0];
    expect(text).toContain("第 2 筆"); // 0-based 1 → 1-based 2
    expect(text).toContain("broken csv");
    expect(text).toContain("field 'timestamp' missing");
    expect(options).toEqual({ skill: "vrl_generate" });
  });

  it("does not render ✦ Ask Copilot chip on success rows", () => {
    sendSpy.mockReset();
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
      />,
    );
    expect(screen.queryByRole("button", { name: /問 Copilot 怎麼修/ })).toBeNull();
  });
});
