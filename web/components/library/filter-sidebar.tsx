import { Button } from "@/components/ui/button";
import type { OverviewFilters } from "@/lib/api/queries/library";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type OverviewVendorGroup = components["schemas"]["OverviewVendorGroup"];

type Props = {
  filters: OverviewFilters;
  onChange: (next: OverviewFilters) => void;
  groups: OverviewVendorGroup[];
};

const CATEGORIES: Array<{ key: string | undefined; label: string }> = [
  { key: undefined, label: "全部" },
  { key: "network", label: "Network" },
  { key: "endpoint", label: "Endpoint" },
  { key: "auth", label: "Auth" },
  { key: "other", label: "Other" },
];

const STATUSES: Array<{ key: string | undefined; label: string }> = [
  { key: undefined, label: "全部" },
  { key: "published", label: "Published" },
  { key: "draft", label: "Draft" },
];

export function FilterSidebar({ filters, onChange, groups }: Props) {
  const counts = computeCategoryCounts(groups);

  return (
    <aside className="flex flex-col gap-6 rounded-lg border bg-card p-4">
      <FilterSection
        label="Log 類型"
        items={CATEGORIES}
        active={filters.category}
        onSelect={(key) => onChange({ ...filters, category: key })}
        counts={counts}
      />
      <FilterSection
        label="狀態"
        items={STATUSES}
        active={filters.status}
        onSelect={(key) => onChange({ ...filters, status: key })}
      />
    </aside>
  );
}

function FilterSection({
  label,
  items,
  active,
  onSelect,
  counts,
}: {
  label: string;
  items: Array<{ key: string | undefined; label: string }>;
  active: string | undefined;
  onSelect: (key: string | undefined) => void;
  counts?: Record<string, number>;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <ul className="flex flex-col gap-1">
        {items.map((item) => {
          const isActive = active === item.key;
          const count = item.key ? counts?.[item.key] : undefined;
          return (
            <li key={item.label}>
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "h-7 w-full justify-between px-2 text-xs",
                  isActive && "bg-muted text-foreground",
                )}
                onClick={() => onSelect(item.key)}
              >
                <span>{item.label}</span>
                {count !== undefined && (
                  <span className="rounded bg-muted px-1.5 text-[10px] text-muted-foreground">
                    {count}
                  </span>
                )}
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function computeCategoryCounts(groups: OverviewVendorGroup[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const group of groups) {
    for (const product of group.products) {
      if (product.category) {
        counts[product.category] = (counts[product.category] ?? 0) + 1;
      }
    }
  }
  return counts;
}
