import type { EditorView } from "@codemirror/view";
import { useCallback } from "react";

import {
  inlineField,
  setInlineState,
} from "@/components/analyzer/cm6-inline/inline-state";
import { streamInlineVrl } from "@/lib/copilot/inline-vrl-client";
import type { InlineVrlRequest } from "@/lib/copilot/types";

export function useInlineVrl(view: EditorView | null) {
  const send = useCallback(
    async (req: InlineVrlRequest) => {
      if (!view) return;
      const cur = view.state.field(inlineField);
      // Allow send only if we're in prompting (the user just submitted) or
      // idle. Anything else means a stale call — bail.
      if (cur.kind !== "prompting" && cur.kind !== "idle") return;

      const anchor =
        req.mode === "insert"
          ? req.cursor_offset ?? 0
          : req.selection_start ?? 0;
      const selectionEnd =
        req.mode === "replace" ? req.selection_end ?? null : null;

      const controller = new AbortController();
      view.dispatch({
        effects: setInlineState.of({
          kind: "streaming",
          mode: req.mode,
          anchor,
          selectionEnd,
          ghost: "",
          abort: controller,
        }),
      });

      try {
        for await (const ev of streamInlineVrl(req, controller.signal)) {
          const inState = view.state.field(inlineField);
          if (inState.kind !== "streaming") return; // user-aborted via docChanged
          if (ev.type === "text_delta") {
            view.dispatch({
              effects: setInlineState.of({
                ...inState,
                ghost: inState.ghost + ev.text,
              }),
            });
          } else if (ev.type === "error") {
            view.dispatch({
              effects: setInlineState.of({
                kind: "error",
                mode: inState.mode,
                anchor: inState.anchor,
                message: ev.message,
              }),
            });
          } else if (ev.type === "done") {
            const final = view.state.field(inlineField);
            if (final.kind === "streaming") {
              view.dispatch({
                effects: setInlineState.of({
                  kind: "ready",
                  mode: final.mode,
                  anchor: final.anchor,
                  selectionEnd: final.selectionEnd,
                  ghost: final.ghost,
                }),
              });
            }
            return;
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const inState = view.state.field(inlineField);
        if (inState.kind === "streaming") {
          view.dispatch({
            effects: setInlineState.of({
              kind: "error",
              mode: inState.mode,
              anchor: inState.anchor,
              message: "連線中斷",
            }),
          });
        }
      }
    },
    [view],
  );

  return { send };
}
