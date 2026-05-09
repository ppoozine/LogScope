import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { CopilotToggle } from "@/components/layout/copilot-toggle";
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

describe("CopilotToggle", () => {
  it("toggles via click", () => {
    render(<CopilotToggle />);
    const btn = screen.getByLabelText(/Open Copilot/);
    fireEvent.click(btn);
    expect(useCopilotStore.getState().isOpen).toBe(true);
  });

  it("toggles via ⌘\\ keymap", () => {
    render(<CopilotToggle />);
    fireEvent.keyDown(window, { key: "\\", metaKey: true });
    expect(useCopilotStore.getState().isOpen).toBe(true);
    fireEvent.keyDown(window, { key: "\\", metaKey: true });
    expect(useCopilotStore.getState().isOpen).toBe(false);
  });

  it("toggles via Ctrl+\\ on non-Mac", () => {
    render(<CopilotToggle />);
    fireEvent.keyDown(window, { key: "\\", ctrlKey: true });
    expect(useCopilotStore.getState().isOpen).toBe(true);
  });
});
