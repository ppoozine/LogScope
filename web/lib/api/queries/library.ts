// web/lib/api/queries/library.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type OverviewVendorGroup = components["schemas"]["OverviewVendorGroup"];
type ProductDetail = components["schemas"]["ProductDetail"];
type VendorCreate = components["schemas"]["VendorCreate"];
type ProductCreate = components["schemas"]["ProductCreate"];
type VendorRead = components["schemas"]["VendorRead"];
type ProductRead = components["schemas"]["ProductRead"];

export type OverviewFilters = {
  category?: string;
  status?: string;
  q?: string;
};

export function useLibraryOverview(filters: OverviewFilters = {}) {
  return useQuery<OverviewVendorGroup[]>({
    queryKey: ["library", "overview", filters],
    queryFn: async () => {
      const r = await apiFetch<{ data: OverviewVendorGroup[] }>("/api/v1/library/overview", {
        searchParams: filters,
      });
      return r.data;
    },
    staleTime: 1000 * 30,
  });
}

export function useProductDetail(vendorSlug: string, productSlug: string) {
  return useQuery<ProductDetail>({
    queryKey: ["library", "product-detail", vendorSlug, productSlug],
    queryFn: async () => {
      const r = await apiFetch<{ data: ProductDetail }>(
        `/api/v1/library/vendors/${vendorSlug}/products/${productSlug}`,
      );
      return r.data;
    },
  });
}

export function useCreateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorCreate) =>
      apiFetch<{ data: VendorRead }>("/api/v1/library/vendors", {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library", "overview"] });
    },
  });
}

export function useCreateProduct(vendorSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProductCreate) =>
      apiFetch<{ data: ProductRead }>(`/api/v1/library/vendors/${vendorSlug}/products`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library", "overview"] });
    },
  });
}
