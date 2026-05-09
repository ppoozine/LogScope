import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessageBubble } from "@/components/copilot/message-bubble";
import { useCopilotStore } from "@/lib/copilot/store";

const baseProps = { isLastAssistant: false } as const;

describe("<MessageBubble> Insert chip", () => {
  beforeEach(() =>
    useCopilotStore.setState({
      pendingInsert: null,
      editorBridge: { setVrl: vi.fn(), getVrl: () => "" },
    }),
  );

  it("renders Insert chip when assistant message has vrlBlock and editor is registered", () => {
    render(
      <MessageBubble
        {...baseProps}
        message={{
          id: "m1",
          role: "assistant",
          content: "see ```vrl\nfoo\n```",
          vrlBlock: "foo",
        }}
      />,
    );
    expect(screen.getByRole("button", { name: /insert/i })).toBeInTheDocument();
  });

  it("does not render Insert chip when no vrlBlock", () => {
    render(
      <MessageBubble {...baseProps} message={{ id: "m1", role: "assistant", content: "純文字" }} />,
    );
    expect(screen.queryByRole("button", { name: /insert/i })).toBeNull();
  });

  it("clicking Insert chip calls store.requestInsert with vrlBlock", () => {
    render(
      <MessageBubble
        {...baseProps}
        message={{
          id: "m1",
          role: "assistant",
          content: "x",
          vrlBlock: "vrl content",
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /insert/i }));
    expect(useCopilotStore.getState().pendingInsert).toEqual({
      proposedVrl: "vrl content",
      messageId: "m1",
    });
  });

  it("Insert chip is disabled when editorBridge.setVrl is null", () => {
    useCopilotStore.setState({ editorBridge: { setVrl: null, getVrl: () => "" } });
    render(
      <MessageBubble
        {...baseProps}
        message={{
          id: "m1",
          role: "assistant",
          content: "x",
          vrlBlock: "vrl content",
        }}
      />,
    );
    const btn = screen.getByRole("button", { name: /insert/i });
    expect(btn).toBeDisabled();
  });
});
