"use client";

import type { Diagnostic } from "@codemirror/lint";
import { linter } from "@codemirror/lint";
import type { EditorView } from "@codemirror/view";

type FixDispatcher = (view: EditorView, diag: Diagnostic) => void;

let _fixDispatcher: FixDispatcher | null = null;

export function setVrlFixDispatcher(dispatcher: FixDispatcher | null): void {
  _fixDispatcher = dispatcher;
}

export type CheckCaller = (
  vrlSource: string,
) => Promise<{ kind: "ok" | "compile_error"; compile_error?: string | null }>;

/**
 * Build a CodeMirror lint extension that pings backend /analyzer/check
 * (debounced) and converts VRL ``error[Exxx]:`` blocks into per-line
 * Diagnostic[] decorations.
 *
 * VRL's diagnostic format embeds ``:<line>:<col>`` references inside
 * each error block. We collect every line referenced in a block and
 * attach the full block text as the message — same UX as the POC.
 */
export function makeVrlLinter(caller: CheckCaller) {
  return linter(
    async (view: EditorView): Promise<Diagnostic[]> => {
      const source = view.state.doc.toString();
      if (!source.trim()) return [];

      let response: Awaited<ReturnType<CheckCaller>>;
      try {
        response = await caller(source);
      } catch {
        return [];
      }

      if (response.kind !== "compile_error" || !response.compile_error) {
        return [];
      }

      return parseVrlDiagnostics(response.compile_error, view);
    },
    {
      // Lint extension's own debounce. Combined with our debounced editor
      // value (handled at AnalyzerView debounce level for parse/match), this
      // gives ~600-800ms idle before /check runs.
      delay: 600,
    },
  );
}

export function parseVrlDiagnostics(compileError: string, view: EditorView): Diagnostic[] {
  const blocks = compileError.split(/^(?=error\[)/m).filter((s) => s.trim().length > 0);
  const byLine = new Map<number, string>();
  for (const block of blocks) {
    const re = /:(\d+):(\d+)/g;
    const seen = new Set<number>();
    let match = re.exec(block);
    while (match !== null) {
      const line = parseInt(match[1], 10) - 1;
      if (!seen.has(line)) {
        seen.add(line);
        const existing = byLine.get(line);
        byLine.set(line, existing ? `${existing}\n\n${block.trim()}` : block.trim());
      }
      match = re.exec(block);
    }
  }

  const diagnostics: Diagnostic[] = [];
  const doc = view.state.doc;
  for (const [line, message] of byLine) {
    if (line < 0 || line >= doc.lines) continue;
    const lineObj = doc.line(line + 1); // CM doc.line is 1-based
    diagnostics.push({
      from: lineObj.from,
      to: lineObj.to,
      severity: "error",
      message,
    });
  }
  for (const d of diagnostics) {
    d.actions = [
      {
        name: "✨ Fix with Copilot",
        apply: (v, _from, _to) => {
          _fixDispatcher?.(v, d);
        },
      },
    ];
  }
  return diagnostics;
}
