"use client";

import { useState } from "react";

import { AddProductDialog } from "@/components/library/add-product-dialog";
import { AddVendorDialog } from "@/components/library/add-vendor-dialog";
import { EmptyState } from "@/components/library/empty-state";
import { FilterSidebar } from "@/components/library/filter-sidebar";
import { ProductCard } from "@/components/library/product-card";
import { VendorGroup } from "@/components/library/vendor-group";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { type OverviewFilters, useLibraryOverview } from "@/lib/api/queries/library";

type Props = { initialFilters: OverviewFilters };

export function LibraryOverviewView({ initialFilters }: Props) {
  const [filters, setFilters] = useState<OverviewFilters>(initialFilters);
  const [vendorOpen, setVendorOpen] = useState(false);
  const [productOpen, setProductOpen] = useState<string | null>(null); // vendor slug
  const {
    data: groups,
    isLoading,
    error,
  } = useLibraryOverview(filters) as {
    data: import("@/lib/api/types").components["schemas"]["OverviewVendorGroup"][] | undefined;
    isLoading: boolean;
    error: Error | null;
  };

  // Tasks 15-16 will add FilterSidebar + AddVendorDialog/AddProductDialog
  // For now: search box + new vendor button calls a stub; task 16 wires real dialog.

  const showEmpty = !isLoading && !error && (groups?.length ?? 0) === 0;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[200px_1fr]">
      <div className="hidden lg:block">
        <FilterSidebar filters={filters} onChange={setFilters} />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Input
            placeholder="搜尋 vendor 或 product…"
            value={filters.q ?? ""}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value || undefined }))}
            className="flex-1"
          />
          <Button onClick={() => setVendorOpen(true)}>新增 Vendor</Button>
          <Button variant="outline" disabled title="Coming in spec E">
            AI 建庫
          </Button>
        </div>

        {isLoading && (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}

        {error && <p className="text-sm text-red-600">載入失敗：{error.message}</p>}

        {showEmpty && <EmptyState onAddVendor={() => setVendorOpen(true)} />}

        {groups?.map((group) => (
          <VendorGroup
            key={group.vendor.id}
            group={group}
            onAddProduct={() => setProductOpen(group.vendor.slug)}
          >
            {group.products.map((product) => (
              <ProductCard key={product.id} vendorSlug={group.vendor.slug} product={product} />
            ))}
          </VendorGroup>
        ))}
      </div>

      <AddVendorDialog open={vendorOpen} onOpenChange={setVendorOpen} />
      <AddProductDialog
        vendorSlug={productOpen}
        onOpenChange={(open) => !open && setProductOpen(null)}
      />
    </div>
  );
}
