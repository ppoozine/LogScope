"use client";

import { EditorView, placeholder } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";

type Props = {
  logs: string;
  onLogsChange: (next: string) => void;
};

export function LogPane({ logs, onLogsChange }: Props) {
  const lineCount = logs ? logs.split("\n").filter((l) => l.trim()).length : 0;

  const extensions = useMemo(
    () => [placeholder("一行一筆 log，最多 500 行…"), EditorView.lineWrapping],
    [],
  );

  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Raw Log
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onLogsChange("")}
          disabled={!logs}
          className="h-6 text-xs"
        >
          Clear
        </Button>
      </header>
      <div className="flex-1 overflow-hidden">
        <CodeMirror
          value={logs}
          onChange={onLogsChange}
          extensions={extensions}
          theme="dark"
          basicSetup={{
            lineNumbers: true,
            highlightActiveLine: true,
            foldGutter: false,
            highlightActiveLineGutter: false,
          }}
          height="340px"
        />
      </div>
      <footer className="border-t px-3 py-1.5 text-xs text-muted-foreground">{lineCount} 行</footer>
    </section>
  );
}
