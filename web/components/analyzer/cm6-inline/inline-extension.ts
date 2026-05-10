import { Facet } from "@codemirror/state";
import { type EditorView, ViewPlugin } from "@codemirror/view";

import type { InlineVrlRequest } from "@/lib/copilot/types";

import { makeInlineDecorations } from "./inline-decorations";
import { inlineKeymap } from "./inline-keymap";
import { type InlineState, inlineField, setInlineState } from "./inline-state";

export type InlineProviders = {
  getEngineVersion: () => "0.25" | "0.32";
  getLogs: () => string[];
  sendInlineRequest: (req: InlineVrlRequest, view: EditorView) => void;
};

export const inlineProvidersFacet = Facet.define<InlineProviders, InlineProviders>({
  combine: (values) => values[0],
});

const activeViewPlugin = ViewPlugin.fromClass(
  class {
    constructor(view: EditorView) {
      (globalThis as { __cmInlineActiveView?: EditorView }).__cmInlineActiveView = view;
    }
    destroy() {
      const g = globalThis as { __cmInlineActiveView?: EditorView };
      if (g.__cmInlineActiveView) g.__cmInlineActiveView = undefined;
    }
  },
);

export function inlineExtension(providers: InlineProviders) {
  const decorations = makeInlineDecorations({
    sendInlineRequest: (instruction: string, state: InlineState) => {
      const view = (globalThis as { __cmInlineActiveView?: EditorView }).__cmInlineActiveView;
      if (!view || state.kind !== "prompting") return;
      const base = buildRequest(view, providers, state);
      const req: InlineVrlRequest = { ...base, instruction };
      providers.sendInlineRequest(req, view);
    },
  });

  return [
    inlineField,
    decorations,
    inlineKeymap(),
    activeViewPlugin,
    inlineProvidersFacet.of(providers),
  ];
}

function buildRequest(
  view: EditorView,
  providers: InlineProviders,
  s: Extract<InlineState, { kind: "prompting" }>,
): InlineVrlRequest {
  const doc = view.state.doc.toString();
  if (s.mode === "insert") {
    return {
      instruction: "<set-by-widget>",
      mode: "insert",
      current_vrl: doc,
      cursor_offset: s.anchor,
      vrl_engine: providers.getEngineVersion(),
      logs: providers.getLogs(),
    };
  }
  return {
    instruction: "<set-by-widget>",
    mode: "replace",
    current_vrl: doc,
    selection_start: s.anchor,
    selection_end: s.selectionEnd ?? s.anchor,
    vrl_engine: providers.getEngineVersion(),
    logs: providers.getLogs(),
  };
}

// Re-export effect helpers so consumers (use-inline-vrl) can dispatch directly.
export { inlineField, setInlineState };
