import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProductDetailView } from "@/components/library/product-detail-view";
import type { components } from "@/lib/api/types";

type ProductDetail = components["schemas"]["ProductDetail"];

const detail: ProductDetail = {
  id: "p1",
  vendor_id: "v1",
  name: "PAN-OS",
  slug: "pan-os",
  version: "11.2",
  description: null,
  deploy_type: null,
  doc_url: null,
  status: "active",
  created_at: "2026-05-08T00:00:00Z",
  updated_at: "2026-05-08T00:00:00Z",
  log_types: [
    {
      id: "lt1",
      product_id: "p1",
      name: "Traffic",
      slug: "traffic",
      format: "csv",
      transport: null,
      status: "published",
      source: "manual",
      current_parse_rule_id: "r1",
      description: null,
      published_at: "2026-05-08T00:00:00Z",
      created_at: "2026-05-08T00:00:00Z",
      updated_at: "2026-05-08T00:00:00Z",
      fields: [
        {
          id: "f1",
          log_type_id: "lt1",
          field_name: "src_ip",
          field_type: "ip",
          description: null,
          is_required: false,
          is_identifier: true,
          example_value: null,
          sort_order: 0,
        },
      ],
      current_parse_rule: {
        id: "r1",
        log_type_id: "lt1",
        version: 1,
        vrl_code: ". = parse_csv!(.message)",
        engine_version: "0.32",
        status: "published",
        notes: null,
        created_at: "2026-05-08T00:00:00Z",
        updated_at: "2026-05-08T00:00:00Z",
      },
      samples: [],
    },
  ],
};

describe("ProductDetailView", () => {
  it("renders hero, stats, tab, and field row", () => {
    // Arrange / Act
    render(<ProductDetailView vendorSlug="palo-alto" detail={detail} />);

    // Assert
    expect(screen.getByText("PAN-OS")).toBeInTheDocument();
    expect(screen.getByText(/11\.2/)).toBeInTheDocument();
    expect(screen.getByText("Traffic")).toBeInTheDocument();
    expect(screen.getByText("src_ip")).toBeInTheDocument();
    expect(screen.getByText(". = parse_csv!(.message)")).toBeInTheDocument();
  });

  it("renders empty hint when no log types", () => {
    // Arrange / Act
    render(<ProductDetailView vendorSlug="x" detail={{ ...detail, log_types: [] }} />);

    // Assert
    expect(screen.getByText(/還沒有 log type/)).toBeInTheDocument();
  });
});
