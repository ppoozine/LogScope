import { type EditorView, WidgetType } from "@codemirror/view";
import { useEffect, useRef, useState } from "react";
import { type Root, createRoot } from "react-dom/client";

export type PromptInputProps = {
  initial: string;
  onSubmit: (text: string) => void;
  onCancel: () => void;
};

export function PromptInput({ initial, onSubmit, onCancel }: PromptInputProps) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed.length > 0) onSubmit(trimmed);
    }
  }

  return (
    <div
      className="cm-inline-prompt"
      style={{
        display: "inline-flex",
        flexDirection: "column",
        gap: 2,
        padding: "4px 6px",
        background: "rgba(255, 255, 255, 0.95)",
        border: "1px solid rgba(0, 0, 0, 0.2)",
        borderRadius: 4,
        boxShadow: "0 2px 6px rgba(0,0,0,0.12)",
        minWidth: 240,
      }}
    >
      <div style={{ fontSize: 10, opacity: 0.6 }}>✨ 說你要什麼… (Esc 取消)</div>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        rows={2}
        style={{
          fontFamily: "inherit",
          fontSize: 12,
          padding: 4,
          border: "1px solid rgba(0, 0, 0, 0.15)",
          borderRadius: 2,
          resize: "none",
          outline: "none",
        }}
      />
    </div>
  );
}

export class PromptInputWidget extends WidgetType {
  constructor(
    readonly initialValue: string,
    readonly onSubmit: (text: string) => void,
    readonly onCancel: () => void,
  ) {
    super();
  }

  toDOM(_view: EditorView): HTMLElement {
    const wrap = document.createElement("div");
    wrap.className = "cm-inline-prompt-host";
    wrap.style.display = "inline-block";
    const root = createRoot(wrap);
    root.render(
      <PromptInput
        initial={this.initialValue}
        onSubmit={this.onSubmit}
        onCancel={this.onCancel}
      />,
    );
    (wrap as HTMLElement & { __root?: Root }).__root = root;
    return wrap;
  }

  destroy(dom: HTMLElement): void {
    const host = dom as HTMLElement & { __root?: Root };
    queueMicrotask(() => host.__root?.unmount());
  }

  eq(other: PromptInputWidget): boolean {
    return other.initialValue === this.initialValue;
  }

  ignoreEvent(): boolean {
    return false; // input needs to receive events
  }
}
