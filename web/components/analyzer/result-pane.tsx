"use client";

import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ParseResultItem = components["schemas"]["ParseResultItem"];
type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];

type Props = {
  result: ParseResultItem | null;
  fields: FieldSchemaRead[];
  onSaveBackToLibrary?: () => void;
  onSaveAsSample?: () => void;
  hasLogTypeContext: boolean;
};

const NUMERIC_TYPES = new Set(["int", "float"]);

type Bucket = "identifier" | "numeric" | "event";

export function ResultPane({
  result,
  fields,
  onSaveBackToLibrary,
  onSaveAsSample,
  hasLogTypeContext,
}: Props) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Parse 結果
        </h3>
      </header>
      <div className="min-h-[400px] flex-1 overflow-auto p-3">
        <ResultBody result={result} fields={fields} />
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

function ResultBody({
  result,
  fields,
}: {
  result: ParseResultItem | null;
  fields: FieldSchemaRead[];
}) {
  if (result === null) {
    return <p className="text-xs text-muted-foreground">尚無結果</p>;
  }
  if (result.status === "error") {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700">
        {result.error}
      </div>
    );
  }
  return <GroupedFields output={result.output ?? {}} fields={fields} />;
}

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
    const bucket = bucketFor(v, fieldByName.get(k));
    groups[bucket].push([k, v]);
  }

  return (
    <div className="flex flex-col gap-3">
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
                <li key={k} className="flex gap-2 text-xs">
                  <span
                    className={cn(
                      "min-w-[100px] flex-shrink-0",
                      b === "identifier" && "text-purple-700",
                    )}
                  >
                    {k}
                  </span>
                  <span className={cn(b === "numeric" ? "text-amber-700" : "text-emerald-700")}>
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
