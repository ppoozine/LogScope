import { Button } from "@/components/ui/button";
import type { OverviewFilters } from "@/lib/api/queries/library";
import { cn } from "@/lib/utils";

type Props = {
  filters: OverviewFilters;
  onChange: (next: OverviewFilters) => void;
};

const STATUSES: Array<{ key: string | undefined; label: string }> = [
  { key: undefined, label: "全部" },
  { key: "published", label: "Published" },
  { key: "draft", label: "Draft" },
];

export function FilterSidebar({ filters, onChange }: Props) {
  return (
    <aside className="flex flex-col gap-6 rounded-lg border bg-card p-4">
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
}: {
  label: string;
  items: Array<{ key: string | undefined; label: string }>;
  active: string | undefined;
  onSelect: (key: string | undefined) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <ul className="flex flex-col gap-1">
        {items.map((item) => {
          const isActive = active === item.key;
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
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
