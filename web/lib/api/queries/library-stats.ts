// web/lib/api/queries/library-stats.ts
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type LogTypeStats = components["schemas"]["LogTypeStats"];
type ProductCoverage = components["schemas"]["ProductCoverage"];
type StatsRange = "7d" | "14d" | "30d" | "90d";

export function useLogTypeStats(logTypeId: string, range: StatsRange = "7d") {
  return useQuery<LogTypeStats>({
    queryKey: ["library", "log-type-stats", logTypeId, range],
    queryFn: async () => {
      const r = await apiFetch<{ data: LogTypeStats }>(
        `/api/v1/library/log_types/${logTypeId}/stats`,
        { searchParams: { range } },
      );
      return r.data;
    },
    staleTime: 1000 * 30,
  });
}

export function useProductCoverage(
  vendorSlug: string,
  productSlug: string,
  range: StatsRange = "7d",
) {
  return useQuery<ProductCoverage>({
    queryKey: ["library", "product-coverage", vendorSlug, productSlug, range],
    queryFn: async () => {
      const r = await apiFetch<{ data: ProductCoverage }>(
        `/api/v1/library/products/${vendorSlug}/${productSlug}/coverage`,
        { searchParams: { range } },
      );
      return r.data;
    },
    staleTime: 1000 * 30,
  });
}
