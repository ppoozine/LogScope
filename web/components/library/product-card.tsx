"use client";

import Link from "next/link";

import { CoverageSparkline } from "@/components/library/coverage-sparkline";
import { useProductCoverage } from "@/lib/api/queries/library-stats";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type OverviewProduct = components["schemas"]["OverviewProduct"];

type Props = { vendorSlug: string; product: OverviewProduct };

export function ProductCard({ vendorSlug, product }: Props) {
  const isEmpty = product.is_empty;
  const status = isEmpty ? "未建庫" : product.log_type_counts.draft > 0 ? "draft" : "published";

  return (
    <Link
      href={`/library/${vendorSlug}/${product.slug}`}
      className={cn(
        "flex flex-col gap-2 rounded-lg border bg-card p-3 transition hover:border-purple-300",
        isEmpty && "border-dashed",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold">{product.name}</h3>
        <StatusBadge status={status} />
      </div>
      <p className="text-xs text-muted-foreground">
        {isEmpty ? "—" : `${product.log_type_counts.total} log types`}
      </p>
      {!isEmpty && <CoverageRow vendorSlug={vendorSlug} productSlug={product.slug} />}
    </Link>
  );
}

function CoverageRow({ vendorSlug, productSlug }: { vendorSlug: string; productSlug: string }) {
  const { data } = useProductCoverage(vendorSlug, productSlug, "7d");
  if (!data?.enabled) {
    return (
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>Coverage 7d</span>
        <span>—</span>
      </div>
    );
  }
  const first = data.log_types[0];
  if (!first) {
    return (
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>Coverage 7d</span>
        <span>—</span>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
      <span>Coverage 7d</span>
      <CoverageSparkline data={first.sparkline} />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const className = cn(
    "rounded px-2 py-0.5 text-[10px] font-medium",
    status === "published" && "bg-teal-50 text-teal-700",
    status === "draft" && "bg-amber-50 text-amber-700",
    status === "未建庫" && "border bg-muted text-muted-foreground",
  );
  return <span className={className}>{status}</span>;
}
