import { Annotation, StateEffect, StateField } from "@codemirror/state";

import type { InlineMode } from "@/lib/copilot/types";

export type InlineState =
  | { kind: "idle" }
  | {
      kind: "prompting";
      mode: InlineMode;
      anchor: number;
      selectionEnd: number | null;
      inputValue: string;
    }
  | {
      kind: "streaming";
      mode: InlineMode;
      anchor: number;
      selectionEnd: number | null;
      ghost: string;
      abort: AbortController;
    }
  | {
      kind: "ready";
      mode: InlineMode;
      anchor: number;
      selectionEnd: number | null;
      ghost: string;
    }
  | {
      kind: "error";
      mode: InlineMode;
      anchor: number;
      message: string;
    };

export const setInlineState = StateEffect.define<InlineState>();
export const internalGhostInsert = Annotation.define<true>();

const ACTIVE_KINDS: InlineState["kind"][] = ["prompting", "streaming", "ready"];

export const inlineField = StateField.define<InlineState>({
  create: () => ({ kind: "idle" }),
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setInlineState)) return effect.value;
    }
    if (tr.docChanged && ACTIVE_KINDS.includes(value.kind) && !tr.annotation(internalGhostInsert)) {
      if (value.kind === "streaming") value.abort.abort();
      return { kind: "idle" };
    }
    return value;
  },
});
