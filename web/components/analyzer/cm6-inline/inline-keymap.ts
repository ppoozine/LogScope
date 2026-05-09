import { Prec } from "@codemirror/state";
import { type EditorView, type KeyBinding, keymap } from "@codemirror/view";

import {
  inlineField,
  internalGhostInsert,
  setInlineState,
} from "./inline-state";

export function handleCmdK(view: EditorView): boolean {
  const cur = view.state.field(inlineField);
  if (cur.kind === "streaming") cur.abort.abort();

  const sel = view.state.selection.main;
  const isRange = sel.from !== sel.to;
  view.dispatch({
    effects: setInlineState.of({
      kind: "prompting",
      mode: isRange ? "replace" : "insert",
      anchor: sel.from,
      selectionEnd: isRange ? sel.to : null,
      inputValue: "",
    }),
  });
  return true;
}

export function handleTabAccept(view: EditorView): boolean {
  const v = view.state.field(inlineField);
  if (v.kind !== "ready") return false;

  const from = v.anchor;
  const to = v.mode === "insert" ? v.anchor : v.selectionEnd ?? v.anchor;
  view.dispatch({
    changes: { from, to, insert: v.ghost },
    annotations: internalGhostInsert.of(true),
    effects: setInlineState.of({ kind: "idle" }),
  });
  return true;
}

export function handleEscReject(view: EditorView): boolean {
  const v = view.state.field(inlineField);
  if (v.kind === "idle") return false;
  if (v.kind === "streaming") v.abort.abort();
  view.dispatch({ effects: setInlineState.of({ kind: "idle" }) });
  return true;
}

export function inlineKeymap() {
  const bindings: KeyBinding[] = [
    { key: "Mod-k", run: handleCmdK, preventDefault: true },
    { key: "Tab", run: handleTabAccept },
    { key: "Escape", run: handleEscReject },
  ];
  return Prec.highest(keymap.of(bindings));
}
