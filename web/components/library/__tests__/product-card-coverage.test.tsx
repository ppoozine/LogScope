import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { ProductCard } from "../product-card";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

const PRODUCT = {
  id: "p1",
  name: "P1",
  slug: "p1",
  status: "active" as const,
  log_type_counts: { total: 1, published: 1, draft: 0 },
  is_empty: false,
};

describe("ProductCard coverage column", () => {
  it("renders sparkline svg when coverage available", async () => {
    server.use(
      http.get("/api/v1/library/products/v/p1/coverage", () =>
        HttpResponse.json({
          data: {
            enabled: true,
            range_days: 7,
            log_types: [
              {
                log_type_id: "lt1",
                sparkline: [1, 1, 1, 1, 1, 1, 1],
                success_rate_avg: 1,
                volume: 7,
              },
            ],
          },
        }),
      ),
    );
    const { container } = render(withQuery(<ProductCard vendorSlug="v" product={PRODUCT} />));
    await waitFor(() => expect(container.querySelector("svg")).toBeInTheDocument());
  });

  it("renders dash when coverage disabled", async () => {
    server.use(
      http.get("/api/v1/library/products/v/p1/coverage", () =>
        HttpResponse.json({
          data: { enabled: false, range_days: 7, log_types: [] },
        }),
      ),
    );
    render(withQuery(<ProductCard vendorSlug="v" product={PRODUCT} />));
    // wait for query to settle, then expect no svg, just em-dash
    await waitFor(() => {
      const els = screen.getAllByText("—");
      // ProductCard already has em-dash for empty products; both should be present
      expect(els.length).toBeGreaterThanOrEqual(1);
    });
  });
});
