import { WidgetType } from "@codemirror/view";

import type { InlineMode } from "@/lib/copilot/types";

export type HintBarPhase = "streaming" | "ready" | "error";

export class HintBarWidget extends WidgetType {
  constructor(
    readonly phase: HintBarPhase,
    readonly mode: InlineMode,
    readonly errorMessage?: string,
    readonly onCancel?: () => void,
  ) {
    super();
  }

  toDOM(): HTMLElement {
    const bar = document.createElement("div");
    bar.className = "cm-inline-hint-bar";
    bar.dataset.phase = this.phase;
    bar.dataset.mode = this.mode;
    bar.style.fontSize = "11px";
    bar.style.lineHeight = "16px";
    bar.style.padding = "1px 6px";
    bar.style.borderRadius = "2px";
    bar.style.display = "inline-flex";
    bar.style.gap = "8px";
    bar.style.alignItems = "center";
    bar.style.userSelect = "none";

    if (this.phase === "streaming") {
      bar.textContent = "⌛ 生成中… Esc 取消";
      bar.style.background = "rgba(59, 130, 246, 0.15)";
      bar.style.color = "rgb(37, 99, 235)";
    } else if (this.phase === "ready") {
      bar.textContent = "✓ Tab 接受 · Esc 拒絕";
      bar.style.background = "rgba(16, 185, 129, 0.15)";
      bar.style.color = "rgb(5, 150, 105)";
    } else {
      bar.textContent = `⚠ ${this.errorMessage ?? "錯誤"}`;
      bar.style.background = "rgba(239, 68, 68, 0.15)";
      bar.style.color = "rgb(220, 38, 38)";
    }

    if (this.onCancel) {
      const x = document.createElement("button");
      x.type = "button";
      x.textContent = "✖";
      x.style.border = "none";
      x.style.background = "transparent";
      x.style.cursor = "pointer";
      x.style.fontSize = "11px";
      x.style.padding = "0 2px";
      x.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.onCancel?.();
      });
      bar.appendChild(x);
    }

    return bar;
  }

  eq(other: HintBarWidget): boolean {
    return (
      other.phase === this.phase &&
      other.mode === this.mode &&
      other.errorMessage === this.errorMessage
    );
  }

  ignoreEvent(): boolean {
    // We need click events on the cancel button, so don't blanket ignore.
    return false;
  }
}
