"use client";

import { useMemo } from "react";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { diffMatches, diffPaths, stableStringify } from "@/lib/vrl/diff";

type ParseResponse = components["schemas"]["ParseResponse"];
type ParseResultItem = components["schemas"]["ParseResultItem"];

type Props = {
  v25: ParseResponse | null;
  v32: ParseResponse | null;
};

export function DiffPane({ v25, v32 }: Props) {
  if (!v25 || !v32) return null;

  // Compile-error fallback: render banner + (if any) single-engine view
  if (v25.kind === "compile_error" || v32.kind === "compile_error") {
    return (
      <section className="flex flex-col rounded-lg border bg-card">
        <header className="flex items-center justify-between border-b px-3 py-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Run both — engine 不一致
          </h3>
        </header>
        <div className="flex flex-col gap-3 p-3">
          {v25.kind === "compile_error" && (
            <CompileErrorBanner engine="0.25" message={v25.compile_error} />
          )}
          {v32.kind === "compile_error" && (
            <CompileErrorBanner engine="0.32" message={v32.compile_error} />
          )}
          {v25.kind === "ok" && <SingleEngineSection label="vrl 0.25 succeeded" response={v25} />}
          {v32.kind === "ok" && <SingleEngineSection label="vrl 0.32 succeeded" response={v32} />}
        </div>
      </section>
    );
  }

  if (v25.kind === "empty" || v32.kind === "empty") {
    return (
      <section className="rounded-lg border bg-card p-3 text-xs italic text-muted-foreground">
        沒有 log 可解
      </section>
    );
  }

  const total = v25.results?.length ?? 0;
  const rows: Array<{
    a: ParseResultItem;
    b: ParseResultItem;
    same: boolean;
  }> = [];
  let matches = 0;
  for (let i = 0; i < total; i++) {
    const a = v25.results![i];
    const b = v32.results![i];
    const same = diffMatches(a, b);
    if (same) matches++;
    rows.push({ a, b, same });
  }

  return (
    <section className="flex flex-col rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Run both — 0.25 vs 0.32
        </h3>
        <div className="flex gap-3 text-xs">
          <span className="text-emerald-700">
            match {matches}/{total}
          </span>
          <span className="text-muted-foreground">
            v25: ✓ {v25.summary?.success ?? 0} ✗ {v25.summary?.error ?? 0}
          </span>
          <span className="text-muted-foreground">
            v32: ✓ {v32.summary?.success ?? 0} ✗ {v32.summary?.error ?? 0}
          </span>
        </div>
      </header>
      <div className="flex flex-col gap-2 p-3">
        {rows.map(({ a, b, same }) => (
          <DiffRow key={a.index} a={a} b={b} same={same} />
        ))}
      </div>
    </section>
  );
}

function CompileErrorBanner({
  engine,
  message,
}: {
  engine: string;
  message: string | null | undefined;
}) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-3 text-xs">
      <p className="mb-1 font-semibold text-red-700">VRL compile error（engine {engine}）</p>
      <pre className="whitespace-pre-wrap text-red-800">{message}</pre>
    </div>
  );
}

function SingleEngineSection({ label, response }: { label: string; response: ParseResponse }) {
  if (response.kind !== "ok") return null;
  return (
    <div>
      <p className="mb-1 text-[11px] italic text-muted-foreground">{label}</p>
      <pre className="overflow-x-auto rounded bg-zinc-50 p-2 text-[11px]">
        {stableStringify(response.results)}
      </pre>
    </div>
  );
}

function DiffRow({ a, b, same }: { a: ParseResultItem; b: ParseResultItem; same: boolean }) {
  const paths = useMemo(() => {
    if (same) return new Set<string>();
    if (a.status === "success" && b.status === "success") {
      return diffPaths(a.output, b.output);
    }
    return new Set<string>();
  }, [a, b, same]);

  return (
    <details
      open={!same}
      data-result-card
      className={cn(
        "rounded border-l-4 bg-white shadow-sm",
        same ? "border-l-emerald-500" : "border-l-amber-500",
      )}
    >
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs">
        <span className="text-muted-foreground">#{a.index}</span>
        <Badge status={a.status} label="v25" />
        <Badge status={b.status} label="v32" />
        <span
          className={cn("text-[11px] font-semibold", same ? "text-emerald-700" : "text-amber-700")}
        >
          {same ? "match" : "differ"}
        </span>
        <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-mono">
          {a.input}
        </span>
      </summary>
      <div className="border-t bg-zinc-50 p-2">
        {same ? (
          <Pane label="v25 ≡ v32" item={a} highlightPaths={null} />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <Pane label="v25" item={a} highlightPaths={paths} />
            <Pane label="v32" item={b} highlightPaths={paths} />
          </div>
        )}
      </div>
    </details>
  );
}

function Badge({ status, label }: { status: string; label: string }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 text-[10px] font-bold",
        status === "success" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700",
      )}
    >
      {label}
    </span>
  );
}

function Pane({
  label,
  item,
  highlightPaths,
}: {
  label: string;
  item: ParseResultItem;
  highlightPaths: Set<string> | null;
}) {
  const body =
    item.status === "error"
      ? (item.error ?? "")
      : renderJsonHtml(item.output ?? {}, highlightPaths ?? new Set());

  return (
    <div className="rounded bg-white">
      <div className="border-b px-2 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      {item.status === "error" ? (
        <pre className="overflow-x-auto px-2 py-1 text-[11px] text-red-700">{body as string}</pre>
      ) : (
        <pre
          className="overflow-x-auto px-2 py-1 text-[11px]"
          // biome-ignore lint/security/noDangerouslySetInnerHtml: trusted rendered JSON
          dangerouslySetInnerHTML={{ __html: body as string }}
        />
      )}
    </div>
  );
}

function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
  );
}

function renderJsonHtml(value: unknown, diffs: Set<string>, path = "", indent = 0): string {
  const pad = "  ".repeat(indent);
  const padIn = "  ".repeat(indent + 1);

  if (value === null) return `<span class="text-muted-foreground italic">null</span>`;
  if (typeof value === "boolean")
    return `<span class="text-amber-700 font-semibold">${value}</span>`;
  if (typeof value === "number") return `<span class="text-pink-700">${value}</span>`;
  if (typeof value === "string")
    return `<span class="text-emerald-700">${escapeHtml(JSON.stringify(value))}</span>`;

  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    const items = value.map((v, i) => {
      const cp = `${path}[${i}]`;
      const inner = renderJsonHtml(v, diffs, cp, indent + 1);
      const wrapped = diffs.has(cp)
        ? `<span class="bg-amber-100 ring-1 ring-amber-400 rounded px-0.5">${inner}</span>`
        : inner;
      return `${padIn}${wrapped}`;
    });
    return `[\n${items.join(",\n")}\n${pad}]`;
  }

  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  if (keys.length === 0) return "{}";
  const items = keys.map((k) => {
    const cp = `${path}.${k}`;
    const valHtml = renderJsonHtml(obj[k], diffs, cp, indent + 1);
    const wrapped = diffs.has(cp)
      ? `<span class="bg-amber-100 ring-1 ring-amber-400 rounded px-0.5">${valHtml}</span>`
      : valHtml;
    return `${padIn}<span class="text-muted-foreground">${escapeHtml(JSON.stringify(k))}</span>: ${wrapped}`;
  });
  return `{\n${items.join(",\n")}\n${pad}}`;
}
