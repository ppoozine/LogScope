import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "@/lib/api/types";
import { server } from "@/test/msw/server";
import { ProductDetailView } from "../product-detail-view";

type ProductDetail = components["schemas"]["ProductDetail"];

const DETAIL = {
  id: "p1",
  vendor_id: "v1",
  name: "Test",
  slug: "test",
  version: null,
  description: null,
  deploy_type: null,
  doc_url: null,
  status: "active" as const,
  created_at: "2026-05-08T00:00:00Z",
  updated_at: "2026-05-08T00:00:00Z",
  log_types: [
    {
      id: "lt1",
      product_id: "p1",
      name: "LT",
      slug: "lt",
      format: "csv" as const,
      transport: null,
      status: "draft" as const,
      source: "manual" as const,
      current_parse_rule_id: null,
      description: null,
      published_at: null,
      created_at: "2026-05-08T00:00:00Z",
      updated_at: "2026-05-08T00:00:00Z",
      fields: [],
      current_parse_rule: null,
      samples: [],
    },
  ],
};

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("ProductDetailView sub-tabs", () => {
  it("renders Overview / Stats / Versions tab buttons per log type", () => {
    render(
      withQuery(<ProductDetailView vendorSlug="v" detail={DETAIL as unknown as ProductDetail} />),
    );
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stats" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Versions" })).toBeInTheDocument();
  });

  it("clicking Stats fetches log type stats", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: false,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(
      withQuery(<ProductDetailView vendorSlug="v" detail={DETAIL as unknown as ProductDetail} />),
    );
    fireEvent.click(screen.getByRole("button", { name: "Stats" }));
    await waitFor(() => expect(screen.getByText(/啟用 ClickHouse/i)).toBeInTheDocument());
  });
});
