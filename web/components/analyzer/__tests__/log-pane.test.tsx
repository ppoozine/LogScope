import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LogPane } from "@/components/analyzer/log-pane";

describe("LogPane", () => {
  it("renders line count", () => {
    render(<LogPane logs={"a\nb\nc"} onLogsChange={vi.fn()} />);
    expect(screen.getByText("3 行")).toBeInTheDocument();
  });

  it("calls onLogsChange when typing", () => {
    const onLogsChange = vi.fn();
    render(<LogPane logs="" onLogsChange={onLogsChange} />);
    fireEvent.change(screen.getByPlaceholderText(/最多 500 行/), {
      target: { value: "x" },
    });
    expect(onLogsChange).toHaveBeenCalledWith("x");
  });

  it("clear button disabled when empty", () => {
    render(<LogPane logs="" onLogsChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Clear/ })).toBeDisabled();
  });
});
