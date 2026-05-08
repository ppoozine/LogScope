import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LogTypeTabs } from "@/components/library/log-type-tabs";
import type { components } from "@/lib/api/types";

type LogTypeDetail = components["schemas"]["LogTypeDetail"];

function makeLT(name: string, status: "draft" | "published"): LogTypeDetail {
  return {
    id: name,
    product_id: "p1",
    name,
    slug: name,
    format: "csv",
    transport: null,
    status,
    source: "manual",
    current_parse_rule_id: null,
    description: null,
    published_at: null,
    created_at: "2026-05-08T00:00:00Z",
    updated_at: "2026-05-08T00:00:00Z",
    fields: [],
    current_parse_rule: null,
    samples: [],
  };
}

describe("LogTypeTabs", () => {
  it("renders one tab per log type", () => {
    // Arrange / Act
    render(
      <LogTypeTabs
        logTypes={[makeLT("Traffic", "published"), makeLT("Threat", "draft")]}
        activeIdx={0}
        onChange={vi.fn()}
      />,
    );

    // Assert
    expect(screen.getByText("Traffic")).toBeInTheDocument();
    expect(screen.getByText("Threat")).toBeInTheDocument();
  });

  it("calls onChange with idx on click", async () => {
    // Arrange
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <LogTypeTabs
        logTypes={[makeLT("Traffic", "published"), makeLT("Threat", "draft")]}
        activeIdx={0}
        onChange={onChange}
      />,
    );

    // Act
    await user.click(screen.getByText("Threat"));

    // Assert
    expect(onChange).toHaveBeenCalledWith(1);
  });
});
