import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProductCard } from "@/components/library/product-card";
import type { components } from "@/lib/api/types";

type OverviewProduct = components["schemas"]["OverviewProduct"];

function makeProduct(overrides: Partial<OverviewProduct> = {}): OverviewProduct {
  return {
    id: "p1",
    name: "PAN-OS",
    slug: "pan-os",
    status: "active",
    log_type_counts: { total: 3, published: 3, draft: 0 },
    is_empty: false,
    ...overrides,
  };
}

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("ProductCard", () => {
  it("renders name and log type count", () => {
    // Arrange / Act
    render(withQuery(<ProductCard vendorSlug="palo-alto" product={makeProduct()} />));

    // Assert
    expect(screen.getByText("PAN-OS")).toBeInTheDocument();
    expect(screen.getByText("3 log types")).toBeInTheDocument();
  });

  it("shows '未建庫' status when is_empty", () => {
    // Arrange / Act
    render(
      withQuery(
        <ProductCard
          vendorSlug="palo-alto"
          product={makeProduct({
            is_empty: true,
            log_type_counts: { total: 0, published: 0, draft: 0 },
          })}
        />,
      ),
    );

    // Assert
    expect(screen.getByText("未建庫")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows 'draft' when has draft log_types", () => {
    // Arrange / Act
    render(
      withQuery(
        <ProductCard
          vendorSlug="palo-alto"
          product={makeProduct({
            log_type_counts: { total: 2, published: 1, draft: 1 },
          })}
        />,
      ),
    );

    // Assert
    expect(screen.getByText("draft")).toBeInTheDocument();
  });

  it("links to detail page", () => {
    // Arrange / Act
    render(withQuery(<ProductCard vendorSlug="palo-alto" product={makeProduct()} />));

    // Assert
    expect(screen.getByRole("link")).toHaveAttribute("href", "/library/palo-alto/pan-os");
  });
});
