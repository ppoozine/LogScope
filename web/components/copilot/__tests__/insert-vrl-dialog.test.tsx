import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InsertVrlDialog } from "@/components/copilot/insert-vrl-dialog";
import { useCopilotStore } from "@/lib/copilot/store";

describe("<InsertVrlDialog>", () => {
  beforeEach(() =>
    useCopilotStore.setState({
      pendingInsert: null,
      editorBridge: { setVrl: null, getVrl: () => "old vrl" },
    }),
  );

  it("does not render when pendingInsert is null", () => {
    render(<InsertVrlDialog />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders current vs proposed when pendingInsert is set", () => {
    useCopilotStore.setState({
      pendingInsert: { proposedVrl: "new vrl", messageId: "m1" },
      editorBridge: { setVrl: vi.fn(), getVrl: () => "old vrl" },
    });
    render(<InsertVrlDialog />);
    expect(screen.getByText("old vrl")).toBeInTheDocument();
    expect(screen.getByText("new vrl")).toBeInTheDocument();
  });

  it("Confirm button calls confirmInsert", () => {
    const setVrl = vi.fn();
    useCopilotStore.setState({
      pendingInsert: { proposedVrl: "new vrl", messageId: "m1" },
      editorBridge: { setVrl, getVrl: () => "old" },
    });
    render(<InsertVrlDialog />);
    fireEvent.click(screen.getByRole("button", { name: /套用|insert|apply/i }));
    expect(setVrl).toHaveBeenCalledWith("new vrl");
    expect(useCopilotStore.getState().pendingInsert).toBeNull();
  });

  it("Cancel button clears pendingInsert without calling setVrl", () => {
    const setVrl = vi.fn();
    useCopilotStore.setState({
      pendingInsert: { proposedVrl: "new vrl", messageId: "m1" },
      editorBridge: { setVrl, getVrl: () => "old" },
    });
    render(<InsertVrlDialog />);
    fireEvent.click(screen.getByRole("button", { name: /取消|cancel/i }));
    expect(setVrl).not.toHaveBeenCalled();
    expect(useCopilotStore.getState().pendingInsert).toBeNull();
  });
});
