import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type OverviewProduct = components["schemas"]["OverviewProduct"];

const CATEGORY_LABEL: Record<string, string> = {
  network: "Network",
  endpoint: "Endpoint",
  auth: "Auth",
  other: "Other",
};

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
      {product.category && (
        <Badge variant="outline" className="w-fit">
          {CATEGORY_LABEL[product.category] ?? product.category}
        </Badge>
      )}
      <p className="text-xs text-muted-foreground">
        {isEmpty ? "—" : `${product.log_type_counts.total} log types`}
      </p>
    </Link>
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
