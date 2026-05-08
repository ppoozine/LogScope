"use client";

import { placeholder } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useMemo } from "react";

import { type CheckCaller, makeVrlLinter } from "@/components/analyzer/vrl-lint";
import { vrlLanguage } from "@/components/analyzer/vrl-syntax";
import { Label } from "@/components/ui/label";

type EngineVersion = "0.25" | "0.32";

type Props = {
  vrl: string;
  onVrlChange: (next: string) => void;
  engineVersion: EngineVersion;
  onEngineChange: (next: EngineVersion) => void;
  parseStatus?: { ok: boolean; errors: number; total: number };
  onCheck?: CheckCaller;
};

export function EditorPane({
  vrl,
  onVrlChange,
  engineVersion,
  onEngineChange,
  parseStatus,
  onCheck,
}: Props) {
  const extensions = useMemo(() => {
    const exts = [vrlLanguage, placeholder("paste VRL here, end with `.` to return the event")];
    if (onCheck) exts.push(makeVrlLinter(onCheck));
    return exts;
  }, [onCheck]);

  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          VRL
        </h3>
        <div className="flex items-center gap-2">
          <Label htmlFor="engine-select" className="text-xs">
            Engine
          </Label>
          <select
            id="engine-select"
            value={engineVersion}
            onChange={(e) => onEngineChange(e.target.value as EngineVersion)}
            className="h-7 rounded-md border bg-background px-2 text-xs"
          >
            <option value="0.32">0.32</option>
            <option value="0.25">0.25</option>
          </select>
        </div>
      </header>
      <div className="flex-1 overflow-hidden">
        <CodeMirror
          value={vrl}
          onChange={onVrlChange}
          extensions={extensions}
          theme="dark"
          basicSetup={{
            lineNumbers: true,
            highlightActiveLine: true,
            foldGutter: false,
            highlightActiveLineGutter: true,
          }}
          height="340px"
        />
      </div>
      <footer className="border-t px-3 py-1.5 text-xs">
        <ParseFooter parseStatus={parseStatus} />
      </footer>
    </section>
  );
}

function ParseFooter({
  parseStatus,
}: {
  parseStatus: { ok: boolean; errors: number; total: number } | undefined;
}) {
  if (!parseStatus) {
    return <span className="text-muted-foreground">輸入 VRL…</span>;
  }
  if (parseStatus.errors === 0) {
    return <span className="text-emerald-600">✓ {parseStatus.total} 行 parse ok</span>;
  }
  return (
    <span className="text-amber-700">
      ⚠ {parseStatus.errors}/{parseStatus.total} 行有錯
    </span>
  );
}
