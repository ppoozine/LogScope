import { WidgetType } from "@codemirror/view";

import type { InlineMode } from "@/lib/copilot/types";

export class GhostTextWidget extends WidgetType {
  constructor(
    readonly text: string,
    readonly mode: InlineMode,
  ) {
    super();
  }

  toDOM(): HTMLElement {
    const wrap = document.createElement("span");
    wrap.className = "cm-inline-ghost";
    wrap.dataset.cmInlineGhost = this.mode;
    wrap.style.whiteSpace = "pre";
    wrap.style.pointerEvents = "none";
    wrap.style.opacity = "0.55";
    wrap.textContent = this.text;
    return wrap;
  }

  eq(other: GhostTextWidget): boolean {
    return other.text === this.text && other.mode === this.mode;
  }

  ignoreEvent(): boolean {
    return true;
  }
}
