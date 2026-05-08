import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import { ProductDetailView } from "@/components/library/product-detail-view";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type ProductDetail = components["schemas"]["ProductDetail"];

type PageProps = {
  params: Promise<{ vendor: string; product: string }>;
};

export default async function ProductDetailPage({ params }: PageProps) {
  const { vendor: vendorSlug, product: productSlug } = await params;

  const cookieStore = await cookies();
  const session = cookieStore.get("session")?.value;
  if (!session) notFound();

  let detail: ProductDetail;
  try {
    const r = await apiFetch<{ data: ProductDetail }>(
      `/api/v1/library/vendors/${vendorSlug}/products/${productSlug}`,
      { cookie: `session=${session}` },
    );
    detail = r.data;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  return (
    <div className="mx-auto max-w-screen-xl px-6 py-6">
      <ProductDetailView vendorSlug={vendorSlug} detail={detail} />
    </div>
  );
}
