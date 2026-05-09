import { RangeSetBuilder } from "@codemirror/state";
import { Decoration, EditorView } from "@codemirror/view";

import { GhostTextWidget } from "./ghost-text-widget";
import { HintBarWidget } from "./hint-bar-widget";
import { type InlineState, inlineField, setInlineState } from "./inline-state";
import { PromptInputWidget } from "./prompt-input-widget";

type InlineProviders = {
  sendInlineRequest: (instruction: string, state: InlineState) => void;
};

export function makeInlineDecorations(_providers: InlineProviders) {
  return EditorView.decorations.compute([inlineField], (state) => {
    const v = state.field(inlineField);
    if (v.kind === "idle") return Decoration.none;

    const builder = new RangeSetBuilder<Decoration>();

    if (v.kind === "prompting") {
      const input = new PromptInputWidget(
        v.inputValue,
        (text) => _providers.sendInlineRequest(text, v),
        () => {
          const view = (globalThis as { __cmInlineActiveView?: EditorView })
            .__cmInlineActiveView;
          view?.dispatch({ effects: setInlineState.of({ kind: "idle" }) });
        },
      );
      builder.add(v.anchor, v.anchor, Decoration.widget({ widget: input, side: 1 }));
    }

    if (v.kind === "streaming" || v.kind === "ready") {
      if (v.mode === "replace" && v.selectionEnd != null) {
        builder.add(
          v.anchor,
          v.selectionEnd,
          Decoration.mark({ class: "cm-inline-replace-original" }),
        );
      }
      const at =
        v.mode === "insert" ? v.anchor : v.selectionEnd ?? v.anchor;
      builder.add(
        at,
        at,
        Decoration.widget({
          widget: new GhostTextWidget(v.ghost, v.mode),
          side: 1,
        }),
      );
      builder.add(
        at,
        at,
        Decoration.widget({
          widget: new HintBarWidget(v.kind, v.mode, undefined, () => {
            const view = (globalThis as { __cmInlineActiveView?: EditorView })
              .__cmInlineActiveView;
            if (v.kind === "streaming") v.abort.abort();
            view?.dispatch({ effects: setInlineState.of({ kind: "idle" }) });
          }),
          side: 1,
        }),
      );
    }

    if (v.kind === "error") {
      builder.add(
        v.anchor,
        v.anchor,
        Decoration.widget({
          widget: new HintBarWidget("error", v.mode, v.message, () => {
            const view = (globalThis as { __cmInlineActiveView?: EditorView })
              .__cmInlineActiveView;
            view?.dispatch({ effects: setInlineState.of({ kind: "idle" }) });
          }),
          side: 1,
        }),
      );
    }

    return builder.finish();
  });
}
