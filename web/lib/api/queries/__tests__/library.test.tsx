// web/lib/api/queries/__tests__/library.test.tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useCreateVendor, useLibraryOverview, useProductDetail } from "@/lib/api/queries/library";
import { server } from "@/test/msw/server";
import { makeQueryClient } from "@/test/utils";

const BASE = "/api/v1";

function withClient<T>(hook: () => T) {
  const client = makeQueryClient();
  return renderHook(hook, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}

describe("useLibraryOverview", () => {
  it("fetches default overview", async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/library/overview`, () =>
        HttpResponse.json({
          data: [
            {
              vendor: {
                id: "v1",
                name: "Acme",
                slug: "acme",
                logo_url: null,
              },
              products: [],
            },
          ],
        }),
      ),
    );
    const { result } = withClient(() => useLibraryOverview());

    // Act
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].vendor.slug).toBe("acme");
  });

  it("passes q query param", async () => {
    // Arrange
    let receivedQ: string | null = null;
    server.use(
      http.get(`${BASE}/library/overview`, ({ request }) => {
        receivedQ = new URL(request.url).searchParams.get("q");
        return HttpResponse.json({ data: [] });
      }),
    );
    const { result } = withClient(() => useLibraryOverview({ q: "palo" }));

    // Act
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedQ).toBe("palo");
  });
});

describe("useProductDetail", () => {
  it("fetches product detail", async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/library/vendors/acme/products/pan-os`, () =>
        HttpResponse.json({
          data: {
            id: "p1",
            vendor_id: "v1",
            name: "PAN-OS",
            slug: "pan-os",
            version: null,
            description: null,
            deploy_type: null,
            doc_url: null,
            status: "active",
            created_at: "2026-05-08T00:00:00Z",
            updated_at: "2026-05-08T00:00:00Z",
            log_types: [],
          },
        }),
      ),
    );
    const { result } = withClient(() => useProductDetail("acme", "pan-os"));

    // Act
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.data?.slug).toBe("pan-os");
  });
});

describe("useCreateVendor", () => {
  it("posts to /library/vendors", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/library/vendors`, () =>
        HttpResponse.json(
          {
            data: {
              id: "v-new",
              name: "Fortinet",
              slug: "fortinet",
              website_url: null,
              logo_url: null,
              status: "active",
              created_at: "2026-05-08T00:00:00Z",
              updated_at: "2026-05-08T00:00:00Z",
            },
          },
          { status: 201 },
        ),
      ),
    );
    const { result } = withClient(() => useCreateVendor());

    // Act
    result.current.mutate({ name: "Fortinet", status: "active" });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data.slug).toBe("fortinet");
  });
});
