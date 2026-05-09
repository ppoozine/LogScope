"use client";

import { useEffect, useMemo, useRef } from "react";
import { useDebounce } from "use-debounce";

import { useCopilotStore } from "@/lib/copilot/store";

type ProductLite = {
  slug: string;
  isEmpty: boolean;
  logTypeCounts: { total: number; published: number; draft: number };
};

type GroupLite = {
  vendor: { slug: string };
  products: ProductLite[];
};

export type LibraryOverviewStateForCopilot = {
  filters: { status?: string | null; q?: string | null };
  groups: GroupLite[];
};

/**
 * Push the current /library overview state into the Copilot store as
 * `pageContext.page = "library_overview"`. Filters are debounced 200ms so
 * keystrokes in the search box don't spam the LLM context.
 *
 * On unmount the pageContext is cleared so navigating away from /library
 * doesn't leak overview ctx into other pages.
 */
export function useLibraryOverviewCopilotContext(state: LibraryOverviewStateForCopilot): void {
  const setPageContext = useCopilotStore((s) => s.setPageContext);

  const [debouncedFilters] = useDebounce(state.filters, 200);

  const summary = useMemo(() => {
    const vendorCount = state.groups.length;
    const productsByVendor = state.groups.map((g) => ({
      vendor: g.vendor.slug,
      products: g.products,
    }));
    const productCount = productsByVendor.reduce((sum, g) => sum + g.products.length, 0);
    const missing: string[] = [];
    for (const g of productsByVendor) {
      for (const p of g.products) {
        if (p.isEmpty || p.logTypeCounts.published === 0) {
          missing.push(`${g.vendor}/${p.slug}`);
        }
      }
    }
    return { vendorCount, productCount, missing };
  }, [state.groups]);

  const latestRef = useRef({ summary, filters: debouncedFilters });
  latestRef.current = { summary, filters: debouncedFilters };

  // biome-ignore lint/correctness/useExhaustiveDependencies: latestRef pattern + primitive dep keys intentionally bypass static exhaustive-deps; debouncedFilters primitives listed so effect re-fires when debounced value settles
  useEffect(() => {
    const { summary: s, filters } = latestRef.current;
    setPageContext({
      page: "library_overview",
      filters: {
        status: filters.status ?? null,
        q: filters.q ?? null,
      },
      vendorCount: s.vendorCount,
      productCount: s.productCount,
      productsMissingParseRule: s.missing,
    });
    return () => setPageContext(null);
  }, [
    setPageContext,
    debouncedFilters.status,
    debouncedFilters.q,
    summary.vendorCount,
    summary.productCount,
    summary.missing.length,
  ]);
}
