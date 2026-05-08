import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it } from "vitest";

import { parseVrlDiagnostics } from "@/components/analyzer/vrl-lint";

function makeView(source: string): EditorView {
  return new EditorView({
    state: EditorState.create({ doc: source }),
  });
}

describe("parseVrlDiagnostics", () => {
  it("returns empty for no error markers", () => {
    const view = makeView("foo");
    expect(parseVrlDiagnostics("just some text", view)).toEqual([]);
  });

  it("extracts a single-line diagnostic", () => {
    const view = makeView("line 1\nline 2 broken\nline 3");
    const compileError =
      "error[E000]: something is wrong\n  ┌─ :2:1\n  │\n2 │ line 2 broken\n  │ ^^^";
    const diags = parseVrlDiagnostics(compileError, view);
    expect(diags).toHaveLength(1);
    expect(diags[0].severity).toBe("error");
    expect(diags[0].message).toContain("E000");
    // line 2 → 0-based 1; doc.line(2) covers offsets of "line 2 broken"
    expect(diags[0].from).toBe(7); // start of line 2
  });

  it("merges multiple diagnostics on same line", () => {
    const view = makeView("a\nb");
    const compileError = "error[E001]: first\n  ┌─ :2:1\n\nerror[E002]: second\n  ┌─ :2:5";
    const diags = parseVrlDiagnostics(compileError, view);
    expect(diags).toHaveLength(1);
    expect(diags[0].message).toContain("E001");
    expect(diags[0].message).toContain("E002");
  });

  it("ignores out-of-range line numbers", () => {
    const view = makeView("only one line");
    const compileError = "error[E000]: oops\n  ┌─ :99:1";
    expect(parseVrlDiagnostics(compileError, view)).toEqual([]);
  });
});
