import { EditorState } from "@codemirror/state";
import { describe, expect, it, vi } from "vitest";

import {
  inlineField,
  internalGhostInsert,
  setInlineState,
} from "@/components/analyzer/cm6-inline/inline-state";

function freshState(initialDoc = "") {
  return EditorState.create({ doc: initialDoc, extensions: [inlineField] });
}

describe("inlineField", () => {
  it("starts idle", () => {
    expect(freshState().field(inlineField)).toEqual({ kind: "idle" });
  });

  it("transitions via setInlineState effect", () => {
    const s = freshState();
    const next = s.update({
      effects: setInlineState.of({
        kind: "prompting",
        mode: "insert",
        anchor: 0,
        selectionEnd: null,
        inputValue: "",
      }),
    }).state;
    expect(next.field(inlineField).kind).toBe("prompting");
  });

  it("auto-aborts to idle when doc changes during streaming", () => {
    const abort = { abort: vi.fn() };
    const s0 = freshState("hello");
    const s1 = s0.update({
      effects: setInlineState.of({
        kind: "streaming",
        mode: "insert",
        anchor: 0,
        selectionEnd: null,
        ghost: "",
        abort: abort as unknown as AbortController,
      }),
    }).state;

    const s2 = s1.update({
      changes: { from: 0, to: 0, insert: "x" },
    }).state;

    expect(s2.field(inlineField)).toEqual({ kind: "idle" });
    expect(abort.abort).toHaveBeenCalled();
  });

  it("preserves state when doc change carries internalGhostInsert annotation", () => {
    const s0 = freshState("hello");
    // setInlineState effect short-circuits docChanged check; this test confirms
    // that even WITHOUT a setInlineState effect, the annotation prevents abort.
    const s1 = s0.update({
      effects: setInlineState.of({
        kind: "ready",
        mode: "insert",
        anchor: 0,
        selectionEnd: null,
        ghost: "abc",
      }),
    }).state;

    const s2 = s1.update({
      changes: { from: 0, to: 0, insert: "x" },
      annotations: internalGhostInsert.of(true),
    }).state;

    expect(s2.field(inlineField).kind).toBe("ready");
  });

  it("ignores docChanged when state is idle", () => {
    const s0 = freshState("hello");
    const s1 = s0.update({ changes: { from: 0, to: 0, insert: "x" } }).state;
    expect(s1.field(inlineField)).toEqual({ kind: "idle" });
  });
});
