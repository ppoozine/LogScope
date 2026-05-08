import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultPane } from "@/components/analyzer/result-pane";

describe("ResultPane", () => {
  it("renders empty hint when no result", () => {
    render(<ResultPane result={null} fields={[]} hasLogTypeContext={false} />);
    expect(screen.getByText(/尚無結果/)).toBeInTheDocument();
  });

  it("renders identifier / event / numeric groups", () => {
    render(
      <ResultPane
        result={{
          index: 0,
          input: "x",
          status: "success",
          output: { src_ip: "1.1.1.1", action: "allow", bytes: 42 },
        }}
        fields={[
          {
            id: "1",
            log_type_id: "lt",
            field_name: "src_ip",
            field_type: "ip",
            description: null,
            is_required: false,
            is_identifier: true,
            example_value: null,
            sort_order: 0,
          },
        ]}
        hasLogTypeContext={true}
      />,
    );
    expect(screen.getByText("識別欄位")).toBeInTheDocument();
    expect(screen.getByText("事件欄位")).toBeInTheDocument();
    expect(screen.getByText("數值欄位")).toBeInTheDocument();
    expect(screen.getByText("src_ip")).toBeInTheDocument();
  });

  it("save buttons disabled without log_type context", () => {
    render(<ResultPane result={null} fields={[]} hasLogTypeContext={false} />);
    expect(screen.getByRole("button", { name: /存回 Library/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /存為 sample/ })).toBeDisabled();
  });
});
