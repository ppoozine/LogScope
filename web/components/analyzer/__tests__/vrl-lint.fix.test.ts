import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  parseVrlDiagnostics,
  setVrlFixDispatcher,
} from "@/components/analyzer/vrl-lint";

afterEach(() => {
  setVrlFixDispatcher(null);
  document.body.innerHTML = "";
});

const SAMPLE_ERROR = `error[E110]: function "split" expected \`string\`, got \`bytes\`
  ┌─ :2:9
  │
2 │ parts = split(.message, ",")
  │         ^^^^^^^^^^^^^^^^^^^^
`;

function makeView(doc: string) {
  const state = EditorState.create({ doc });
  return new EditorView({ state, parent: document.body });
}

describe("parseVrlDiagnostics + Diagnostic.actions", () => {
  it("each diagnostic carries a Fix-with-Copilot action", () => {
    const view = makeView(". = parse_syslog!(.message)\nparts = split(.message, \",\")");
    const diags = parseVrlDiagnostics(SAMPLE_ERROR, view);
    expect(diags.length).toBeGreaterThan(0);
    for (const d of diags) {
      expect(d.actions).toBeDefined();
      expect(d.actions?.[0].name).toBe("✨ Fix with Copilot");
    }
    view.destroy();
  });

  it("action.apply calls the registered dispatcher", () => {
    const view = makeView(". = parse_syslog!(.message)\nparts = split(.message, \",\")");
    const dispatcher = vi.fn();
    setVrlFixDispatcher(dispatcher);

    const diags = parseVrlDiagnostics(SAMPLE_ERROR, view);
    const action = diags[0].actions?.[0];
    action?.apply(view, diags[0].from, diags[0].to);

    expect(dispatcher).toHaveBeenCalledTimes(1);
    expect(dispatcher).toHaveBeenCalledWith(view, expect.objectContaining({
      message: expect.stringContaining("E110"),
    }));
    view.destroy();
  });

  it("action.apply with no dispatcher registered is a no-op", () => {
    const view = makeView(". = parse_syslog!(.message)\nparts = split(.message, \",\")");
    setVrlFixDispatcher(null);

    const diags = parseVrlDiagnostics(SAMPLE_ERROR, view);
    const action = diags[0].actions?.[0];
    expect(() => action?.apply(view, diags[0].from, diags[0].to)).not.toThrow();
    view.destroy();
  });
});
