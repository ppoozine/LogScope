import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EditorPane } from "@/components/analyzer/editor-pane";

describe("EditorPane inline integration", () => {
  it("calls onViewReady with EditorView instance", () => {
    const onViewReady = vi.fn();
    render(
      <EditorPane
        vrl=""
        onVrlChange={() => {}}
        engineVersion="0.32"
        onEngineChange={() => {}}
        onViewReady={onViewReady}
      />,
    );
    expect(onViewReady).toHaveBeenCalled();
    expect(onViewReady.mock.calls[0][0]?.dispatch).toBeTypeOf("function");
  });

  it("does not crash when inlineEnabled=true and providers given", () => {
    const onViewReady = vi.fn();
    const providers = {
      getEngineVersion: () => "0.32" as const,
      getLogs: () => [],
      sendInlineRequest: vi.fn(),
    };
    render(
      <EditorPane
        vrl=""
        onVrlChange={() => {}}
        engineVersion="0.32"
        onEngineChange={() => {}}
        onViewReady={onViewReady}
        inlineEnabled
        inlineProviders={providers}
      />,
    );
    expect(onViewReady).toHaveBeenCalled();
  });
});
