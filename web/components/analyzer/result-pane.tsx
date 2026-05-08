"use client";

import { useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ParseResponse = components["schemas"]["ParseResponse"];
type ParseResultItem = components["schemas"]["ParseResultItem"];
type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];

type Props = {
  parseResult: ParseResponse | null;
  fields: FieldSchemaRead[];
  onSaveBackToLibrary?: () => void;
  onSaveAsSample?: () => void;
  hasLogTypeContext: boolean;
};

export function ResultPane({
  parseResult,
  fields,
  onSaveBackToLibrary,
  onSaveAsSample,
  hasLogTypeContext,
}: Props) {
  const [filter, setFilter] = useState("");

  return (
    <section className="flex flex-col rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Parse 結果
        </h3>
        <div className="flex items-center gap-2">
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="filter cards…"
            className="h-7 rounded-md border bg-background px-2 text-xs"
            disabled={parseResult?.kind !== "ok"}
          />
          <ExpandCollapseAll />
        </div>
      </header>

      <div className="min-h-[280px] overflow-auto p-3">
        <ResultBody parseResult={parseResult} filter={filter} fields={fields} />
      </div>

      <footer className="flex gap-2 border-t px-3 py-2">
        <Button
          size="sm"
          variant="outline"
          onClick={onSaveBackToLibrary}
          disabled={!hasLogTypeContext || !onSaveBackToLibrary}
          title={
            hasLogTypeContext ? "存回當前 log type 為新 draft" : "從 Library 詳情頁進入才能存回"
          }
          className="h-7 text-xs"
        >
          存回 Library
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onSaveAsSample}
          disabled={!hasLogTypeContext || !onSaveAsSample}
          title={hasLogTypeContext ? "存成 sample" : "從 Library 詳情頁進入才能存"}
          className="h-7 text-xs"
        >
          存為 sample
        </Button>
      </footer>
    </section>
  );
}

function ExpandCollapseAll() {
  const setAll = (open: boolean) => {
    document.querySelectorAll<HTMLDetailsElement>("[data-result-card]").forEach((d) => {
      d.open = open;
    });
  };
  return (
    <div className="flex gap-1">
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setAll(true)}
        className="h-7 text-xs"
        title="Expand all"
      >
        Expand
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setAll(false)}
        className="h-7 text-xs"
        title="Collapse all"
      >
        Collapse
      </Button>
    </div>
  );
}

function ResultBody({
  parseResult,
  filter,
  fields,
}: {
  parseResult: ParseResponse | null;
  filter: string;
  fields: FieldSchemaRead[];
}) {
  if (parseResult === null) {
    return <p className="text-xs text-muted-foreground">輸入 VRL 與 raw log 後自動 parse</p>;
  }
  if (parseResult.kind === "compile_error") {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-3 text-xs">
        <p className="mb-2 font-semibold text-red-700">
          VRL compile error（engine {parseResult.engine}）
        </p>
        <pre className="whitespace-pre-wrap text-red-800">{parseResult.compile_error}</pre>
      </div>
    );
  }
  if (parseResult.kind === "empty") {
    return <p className="text-xs italic text-muted-foreground">沒有 log 可解</p>;
  }

  const summary = parseResult.summary;
  const results = parseResult.results ?? [];

  return (
    <div className="flex flex-col gap-2">
      {summary && (
        <div className="sticky top-0 z-10 -mx-3 -mt-3 mb-1 flex gap-3 border-b bg-card px-3 py-2 text-xs">
          <span className="font-semibold text-emerald-700">✓ {summary.success}</span>
          <span className="font-semibold text-red-700">✗ {summary.error}</span>
          <span className="text-muted-foreground">total {summary.total}</span>
          <span className="ml-auto text-muted-foreground">engine {parseResult.engine}</span>
        </div>
      )}
      {results.map((r) => (
        <ResultCard key={r.index} result={r} filter={filter} fields={fields} />
      ))}
    </div>
  );
}

function ResultCard({
  result,
  filter,
  fields,
}: {
  result: ParseResultItem;
  filter: string;
  fields: FieldSchemaRead[];
}) {
  const ref = useRef<HTMLDetailsElement | null>(null);

  const matched = useMemo(() => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    const haystack = [result.input, result.error ?? "", JSON.stringify(result.output ?? {})]
      .join("\n")
      .toLowerCase();
    return haystack.includes(q);
  }, [filter, result]);

  if (!matched) return null;

  const isError = result.status === "error";

  return (
    <details
      ref={ref}
      data-result-card
      open={isError}
      className={cn(
        "rounded border-l-4 bg-white shadow-sm",
        isError ? "border-l-red-500" : "border-l-emerald-500",
      )}
    >
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs">
        <span className="text-muted-foreground">#{result.index}</span>
        <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-mono">
          {result.input}
        </span>
        <CopyButton
          getText={() =>
            isError ? (result.error ?? "") : JSON.stringify(result.output ?? {}, null, 2)
          }
        />
      </summary>
      <div className="border-t bg-zinc-50 px-3 py-2">
        {isError ? (
          <pre className="whitespace-pre-wrap text-[11px] text-red-700">{result.error}</pre>
        ) : (
          <GroupedFields output={result.output ?? {}} fields={fields} />
        )}
      </div>
    </details>
  );
}

function CopyButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        navigator.clipboard.writeText(getText()).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className="h-6 px-2 text-[11px]"
    >
      {copied ? "✓ Copied" : "Copy"}
    </Button>
  );
}

const NUMERIC_TYPES = new Set(["int", "float"]);

type Bucket = "identifier" | "numeric" | "event";

function bucketFor(value: unknown, fieldSchema: FieldSchemaRead | undefined): Bucket {
  if (fieldSchema?.is_identifier) return "identifier";
  if (fieldSchema && NUMERIC_TYPES.has(fieldSchema.field_type)) return "numeric";
  if (typeof value === "number") return "numeric";
  return "event";
}

function GroupedFields({
  output,
  fields,
}: {
  output: Record<string, unknown>;
  fields: FieldSchemaRead[];
}) {
  const fieldByName = new Map<string, FieldSchemaRead>();
  for (const f of fields) fieldByName.set(f.field_name, f);

  const groups: Record<Bucket, [string, unknown][]> = {
    identifier: [],
    event: [],
    numeric: [],
  };
  for (const [k, v] of Object.entries(output)) {
    if (k === "vendorRaw") continue;
    groups[bucketFor(v, fieldByName.get(k))].push([k, v]);
  }

  return (
    <div className="flex flex-col gap-2">
      {(["identifier", "event", "numeric"] as Bucket[]).map((b) => {
        if (groups[b].length === 0) return null;
        const heading = b === "identifier" ? "識別欄位" : b === "numeric" ? "數值欄位" : "事件欄位";
        return (
          <div key={b}>
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              {heading}
            </p>
            <ul className="flex flex-col gap-0.5">
              {groups[b].map(([k, v]) => (
                <li key={k} className="flex gap-2 text-[11px] font-mono">
                  <span
                    className={cn(
                      "min-w-[140px] flex-shrink-0",
                      b === "identifier" && "text-purple-700",
                    )}
                  >
                    {k}
                  </span>
                  <span
                    className={cn(
                      "break-all",
                      b === "numeric" ? "text-amber-700" : "text-emerald-700",
                    )}
                  >
                    {String(v)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
