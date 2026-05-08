import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EditorPane } from "@/components/analyzer/editor-pane";

describe("EditorPane", () => {
  it("shows ok parse status when no errors", () => {
    render(
      <EditorPane
        vrl=".x = 1\n."
        onVrlChange={vi.fn()}
        engineVersion="0.32"
        onEngineChange={vi.fn()}
        parseStatus={{ ok: true, errors: 0, total: 5 }}
      />,
    );
    expect(screen.getByText(/5 行 parse ok/)).toBeInTheDocument();
  });

  it("calls onEngineChange when selector changes", () => {
    const onEngineChange = vi.fn();
    render(
      <EditorPane
        vrl=".x = 1\n."
        onVrlChange={vi.fn()}
        engineVersion="0.32"
        onEngineChange={onEngineChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Engine"), {
      target: { value: "0.25" },
    });
    expect(onEngineChange).toHaveBeenCalledWith("0.25");
  });
});
