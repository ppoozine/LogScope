import { EditorState, EditorSelection } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  handleCmdK,
  handleEscReject,
  handleTabAccept,
} from "@/components/analyzer/cm6-inline/inline-keymap";
import {
  inlineField,
  setInlineState,
} from "@/components/analyzer/cm6-inline/inline-state";

function makeView(doc: string, selection?: { from: number; to: number }) {
  const state = EditorState.create({
    doc,
    selection: selection
      ? EditorSelection.single(selection.from, selection.to)
      : undefined,
    extensions: [inlineField],
  });
  return new EditorView({ state, parent: document.body });
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("handleCmdK", () => {
  it("opens prompting/insert on empty selection", () => {
    const view = makeView("hello world", { from: 5, to: 5 });
    const r = handleCmdK(view);
    expect(r).toBe(true);
    const v = view.state.field(inlineField);
    expect(v.kind).toBe("prompting");
    if (v.kind === "prompting") {
      expect(v.mode).toBe("insert");
      expect(v.anchor).toBe(5);
      expect(v.selectionEnd).toBe(null);
    }
    view.destroy();
  });

  it("opens prompting/replace on range selection", () => {
    const view = makeView("hello world", { from: 2, to: 5 });
    handleCmdK(view);
    const v = view.state.field(inlineField);
    if (v.kind === "prompting") {
      expect(v.mode).toBe("replace");
      expect(v.anchor).toBe(2);
      expect(v.selectionEnd).toBe(5);
    } else {
      throw new Error(`expected prompting, got ${v.kind}`);
    }
    view.destroy();
  });

  it("aborts current streaming and re-prompts", () => {
    const abort = { abort: vi.fn() };
    const view = makeView("hello", { from: 0, to: 0 });
    view.dispatch({
      effects: setInlineState.of({
        kind: "streaming",
        mode: "insert",
        anchor: 0,
        selectionEnd: null,
        ghost: "",
        abort: abort as unknown as AbortController,
      }),
    });
    handleCmdK(view);
    expect(abort.abort).toHaveBeenCalled();
    expect(view.state.field(inlineField).kind).toBe("prompting");
    view.destroy();
  });
});

describe("handleTabAccept", () => {
  it("returns false (passthrough) when state is idle", () => {
    const view = makeView("hello");
    expect(handleTabAccept(view)).toBe(false);
    view.destroy();
  });

  it("inserts ghost and goes idle on ready (insert mode)", () => {
    const view = makeView("abc", { from: 1, to: 1 });
    view.dispatch({
      effects: setInlineState.of({
        kind: "ready",
        mode: "insert",
        anchor: 1,
        selectionEnd: null,
        ghost: "X",
      }),
    });
    const r = handleTabAccept(view);
    expect(r).toBe(true);
    expect(view.state.doc.toString()).toBe("aXbc");
    expect(view.state.field(inlineField).kind).toBe("idle");
    view.destroy();
  });

  it("replaces selection with ghost on ready (replace mode)", () => {
    const view = makeView("abcdef", { from: 1, to: 4 });
    view.dispatch({
      effects: setInlineState.of({
        kind: "ready",
        mode: "replace",
        anchor: 1,
        selectionEnd: 4,
        ghost: "ZZZ",
      }),
    });
    const r = handleTabAccept(view);
    expect(r).toBe(true);
    expect(view.state.doc.toString()).toBe("aZZZef");
    expect(view.state.field(inlineField).kind).toBe("idle");
    view.destroy();
  });
});

describe("handleEscReject", () => {
  it("returns false (passthrough) on idle", () => {
    const view = makeView("hello");
    expect(handleEscReject(view)).toBe(false);
    view.destroy();
  });

  it("aborts streaming and clears state", () => {
    const abort = { abort: vi.fn() };
    const view = makeView("hello");
    view.dispatch({
      effects: setInlineState.of({
        kind: "streaming",
        mode: "insert",
        anchor: 0,
        selectionEnd: null,
        ghost: "",
        abort: abort as unknown as AbortController,
      }),
    });
    expect(handleEscReject(view)).toBe(true);
    expect(abort.abort).toHaveBeenCalled();
    expect(view.state.field(inlineField).kind).toBe("idle");
    view.destroy();
  });
});
