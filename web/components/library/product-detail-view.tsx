"use client";

import { useState } from "react";

import { FieldTable } from "@/components/library/field-table";
import { LogTypeTabs } from "@/components/library/log-type-tabs";
import { SampleList } from "@/components/library/sample-list";
import { VrlDisplay } from "@/components/library/vrl-display";
import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/types";

type ProductDetail = components["schemas"]["ProductDetail"];

type Props = { vendorSlug: string; detail: ProductDetail };

export function ProductDetailView({ vendorSlug, detail }: Props) {
  const [activeIdx, setActiveIdx] = useState(0);
  const activeLogType = detail.log_types[activeIdx];

  const initials = vendorSlug.slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 rounded-lg border bg-card p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded bg-muted text-sm font-bold text-muted-foreground">
            {initials}
          </div>
          <div className="flex flex-1 flex-col">
            <h1 className="text-xl font-semibold tracking-tight">{detail.name}</h1>
            <p className="text-sm text-muted-foreground">
              {detail.version ?? "—"} · {vendorSlug}
            </p>
          </div>
          <Badge variant={detail.status === "active" ? "default" : "secondary"}>
            {detail.status}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-4">
          <Stat label="Log types" value={detail.log_types.length} />
          <Stat
            label="Fields"
            value={detail.log_types.reduce((s, lt) => s + lt.fields.length, 0)}
          />
          <Stat
            label="Samples"
            value={detail.log_types.reduce((s, lt) => s + lt.samples.length, 0)}
          />
          <Stat label="Category" value={detail.category ?? "—"} />
        </div>
      </header>

      {detail.log_types.length === 0 ? (
        <p className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">
          這個 product 還沒有 log type — 用 API 或之後從 Analyzer 建立
        </p>
      ) : (
        <>
          <LogTypeTabs logTypes={detail.log_types} activeIdx={activeIdx} onChange={setActiveIdx} />
          {activeLogType && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <FieldTable fields={activeLogType.fields} />
              <SampleList samples={activeLogType.samples} />
              <div className="lg:col-span-2">
                <VrlDisplay rule={activeLogType.current_parse_rule} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  );
}
