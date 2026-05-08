"use client";

import { Button } from "@/components/ui/button";

type Props = {
  logs: string;
  onLogsChange: (next: string) => void;
};

export function LogPane({ logs, onLogsChange }: Props) {
  const lineCount = logs ? logs.split("\n").filter((l) => l.trim()).length : 0;

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
      <textarea
        value={logs}
        onChange={(e) => onLogsChange(e.target.value)}
        placeholder="一行一筆 log，最多 500 行…"
        className="h-[400px] flex-1 resize-none border-0 bg-zinc-50 p-3 font-mono text-xs outline-none"
      />
      <footer className="border-t px-3 py-1.5 text-xs text-muted-foreground">{lineCount} 行</footer>
    </section>
  );
}
