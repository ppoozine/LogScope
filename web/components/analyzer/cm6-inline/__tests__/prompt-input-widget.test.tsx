import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PromptInput } from "@/components/analyzer/cm6-inline/prompt-input-widget";

describe("PromptInput (React component used inside widget)", () => {
  it("autoFocuses textarea on mount", () => {
    const { getByRole } = render(
      <PromptInput initial="" onSubmit={() => {}} onCancel={() => {}} />,
    );
    const ta = getByRole("textbox");
    expect(document.activeElement).toBe(ta);
  });

  it("submits on Enter (no shift)", () => {
    const onSubmit = vi.fn();
    const { getByRole } = render(
      <PromptInput initial="" onSubmit={onSubmit} onCancel={() => {}} />,
    );
    const ta = getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "加 dst_ip" } });
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: false });
    expect(onSubmit).toHaveBeenCalledWith("加 dst_ip");
  });

  it("does not submit empty / whitespace", () => {
    const onSubmit = vi.fn();
    const { getByRole } = render(
      <PromptInput initial="" onSubmit={onSubmit} onCancel={() => {}} />,
    );
    const ta = getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "   " } });
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: false });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("inserts newline on shift+Enter (no submit)", () => {
    const onSubmit = vi.fn();
    const { getByRole } = render(
      <PromptInput initial="abc" onSubmit={onSubmit} onCancel={() => {}} />,
    );
    const ta = getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("cancels on Escape", () => {
    const onCancel = vi.fn();
    const { getByRole } = render(
      <PromptInput initial="" onSubmit={() => {}} onCancel={onCancel} />,
    );
    const ta = getByRole("textbox");
    fireEvent.keyDown(ta, { key: "Escape" });
    expect(onCancel).toHaveBeenCalled();
  });
});
