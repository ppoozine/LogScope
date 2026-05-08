import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";

type OverviewVendorGroup = components["schemas"]["OverviewVendorGroup"];

type Props = {
  group: OverviewVendorGroup;
  onAddProduct?: () => void;
  children: ReactNode;
};

export function VendorGroup({ group, onAddProduct, children }: Props) {
  const initials = group.vendor.name.slice(0, 2).toUpperCase();
  const productCount = group.products.length;

  return (
    <section className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-muted text-xs font-bold text-muted-foreground">
            {initials}
          </div>
          <div>
            <h2 className="text-sm font-semibold">{group.vendor.name}</h2>
            <p className="text-xs text-muted-foreground">{productCount} products</p>
          </div>
        </div>
        {onAddProduct && (
          <Button variant="ghost" size="sm" onClick={onAddProduct}>
            + Product
          </Button>
        )}
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
    </section>
  );
}
