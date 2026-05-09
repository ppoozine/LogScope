"use client";

import { useState } from "react";

import { FieldTable } from "@/components/library/field-table";
import { LogTypeStatsTab } from "@/components/library/log-type-stats-tab";
import { LogTypeTabs } from "@/components/library/log-type-tabs";
import { SampleList } from "@/components/library/sample-list";
import { VersionsTab } from "@/components/library/versions-tab";
import { VrlDisplay } from "@/components/library/vrl-display";
import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/types";
import { useProductDetailCopilotContext } from "@/lib/copilot/hooks/use-product-detail-context";
import { cn } from "@/lib/utils";

type ProductDetail = components["schemas"]["ProductDetail"];

type SubTab = "overview" | "stats" | "versions";
const SUB_TABS: { id: SubTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "stats", label: "Stats" },
  { id: "versions", label: "Versions" },
];

type Props = { vendorSlug: string; detail: ProductDetail };

export function ProductDetailView({ vendorSlug, detail }: Props) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [subTab, setSubTab] = useState<SubTab>("overview");
  const activeLogType = detail.log_types[activeIdx];

  useProductDetailCopilotContext({
    vendorSlug,
    productSlug: detail.slug,
    productStatus: detail.status,
    activeLogType: activeLogType
      ? {
          name: activeLogType.name,
          fields: activeLogType.fields.map((f) => ({
            name: f.field_name,
            type: f.field_type,
            required: f.is_required,
          })),
          samplesCount: activeLogType.samples.length,
          // VersionDiffModal isn't wired into VersionsTab in production yet,
          // and ParseRule head text isn't surfaced on ProductDetail; pass null
          // here. When the diff modal is connected, replace with the real value.
          parseRuleHead: null,
        }
      : null,
    subTab,
    openDiff: null,
  });

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
        <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-3">
          <Stat label="Log types" value={detail.log_types.length} />
          <Stat
            label="Fields"
            value={detail.log_types.reduce((s, lt) => s + lt.fields.length, 0)}
          />
          <Stat
            label="Samples"
            value={detail.log_types.reduce((s, lt) => s + lt.samples.length, 0)}
          />
        </div>
      </header>

      {detail.log_types.length === 0 ? (
        <p className="rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">
          這個 product 還沒有 log type — 用 API 或之後從 Analyzer 建立
        </p>
      ) : (
        <>
          <LogTypeTabs
            logTypes={detail.log_types}
            activeIdx={activeIdx}
            onChange={(i) => {
              setActiveIdx(i);
              setSubTab("overview");
            }}
          />
          {activeLogType && (
            <div className="rounded-lg border bg-card">
              <div className="flex gap-1 border-b px-3">
                {SUB_TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSubTab(t.id)}
                    className={cn(
                      "border-b-2 px-3 py-2 text-sm",
                      subTab === t.id
                        ? "border-purple-600 font-semibold"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              {subTab === "overview" && (
                <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-2">
                  <FieldTable fields={activeLogType.fields} />
                  <SampleList samples={activeLogType.samples} logTypeId={activeLogType.id} />
                  <div className="lg:col-span-2">
                    <VrlDisplay
                      rule={activeLogType.current_parse_rule}
                      logTypeId={activeLogType.id}
                    />
                  </div>
                </div>
              )}
              {subTab === "stats" && <LogTypeStatsTab logTypeId={activeLogType.id} />}
              {subTab === "versions" && <VersionsTab logTypeId={activeLogType.id} />}
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
