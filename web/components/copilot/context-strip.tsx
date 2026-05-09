"use client";

import { useCopilotStore } from "@/lib/copilot/store";
import type {
  AnalyzerPageContext,
  LibraryOverviewPageContext,
  LibraryProductPageContext,
  LibraryVersionsPageContext,
} from "@/lib/copilot/types";
import { cn } from "@/lib/utils";

export function ContextStrip() {
  const ctx = useCopilotStore((s) => s.pageContext);
  if (!ctx) return null;

  return (
    <div className="border-b border-border bg-muted/40 px-3 py-2">
      <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">目前脈絡</div>
      <div className="flex flex-wrap gap-1.5">
        {ctx.page === "analyzer" && <AnalyzerPills ctx={ctx} />}
        {ctx.page === "library_overview" && <OverviewPills ctx={ctx} />}
        {ctx.page === "library_product" && <ProductPills ctx={ctx} />}
        {ctx.page === "library_versions" && <VersionsPills ctx={ctx} />}
      </div>
    </div>
  );
}

function AnalyzerPills({ ctx }: { ctx: AnalyzerPageContext }) {
  const vrlLines = ctx.vrl ? ctx.vrl.split("\n").length : 0;
  const okCount = ctx.parseResults.filter((r) => r.status === "ok").length;
  const errCount = ctx.parseResults.filter((r) => r.status === "error").length;
  return (
    <>
      <Pill active={vrlLines > 0}>VRL {vrlLines} 行</Pill>
      <Pill active={ctx.logs.length > 0}>{ctx.logs.length} 筆 logs</Pill>
      <Pill active={ctx.parseResults.length > 0}>
        Parse {okCount} ok / {errCount} err
      </Pill>
      {ctx.matchTopCandidate && (
        <Pill active>
          {ctx.matchTopCandidate.vendorSlug}/{ctx.matchTopCandidate.productSlug} (
          {Math.round(ctx.matchTopCandidate.confidence * 100)}%)
        </Pill>
      )}
    </>
  );
}

function OverviewPills({ ctx }: { ctx: LibraryOverviewPageContext }) {
  return (
    <>
      <Pill active>{ctx.vendorCount} vendors</Pill>
      <Pill active>{ctx.productCount} products</Pill>
      {ctx.productsMissingParseRule.length > 0 && (
        <Pill active>{ctx.productsMissingParseRule.length} 個未建庫</Pill>
      )}
      {ctx.filters.status && <Pill active>status={ctx.filters.status}</Pill>}
      {ctx.filters.q && <Pill active>q="{ctx.filters.q}"</Pill>}
    </>
  );
}

function ProductPills({ ctx }: { ctx: LibraryProductPageContext }) {
  return (
    <>
      <Pill active>
        {ctx.vendorSlug}/{ctx.productSlug}
      </Pill>
      <Pill active={ctx.productStatus === "active"}>{ctx.productStatus}</Pill>
      {ctx.activeLogType && <Pill active>log_type: {ctx.activeLogType.name}</Pill>}
      {ctx.activeLogType && (
        <Pill active={ctx.activeLogType.fields.length > 0}>
          {ctx.activeLogType.fields.length} fields
        </Pill>
      )}
    </>
  );
}

function VersionsPills({ ctx }: { ctx: LibraryVersionsPageContext }) {
  return (
    <>
      <Pill active>
        {ctx.vendorSlug}/{ctx.productSlug}
      </Pill>
      <Pill active>{ctx.logTypeName}</Pill>
      {ctx.diff && (
        <Pill active>
          {ctx.diff.baseVersion} → {ctx.diff.headVersion}
        </Pill>
      )}
    </>
  );
}

function Pill({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px]",
        active ? "bg-purple-100 text-purple-900" : "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
