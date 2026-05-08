import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilterSidebar } from "@/components/library/filter-sidebar";

describe("FilterSidebar", () => {
  it("calls onChange with selected category", async () => {
    // Arrange
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FilterSidebar filters={{}} onChange={onChange} groups={[]} />);

    // Act
    await user.click(screen.getByRole("button", { name: /Network/ }));

    // Assert
    expect(onChange).toHaveBeenCalledWith({ category: "network" });
  });

  it("highlights active filter", () => {
    // Arrange / Act
    render(<FilterSidebar filters={{ status: "published" }} onChange={vi.fn()} groups={[]} />);

    // Assert
    const publishedBtn = screen.getByRole("button", { name: /Published/ });
    expect(publishedBtn).toHaveClass("bg-muted");
  });

  it("shows category counts derived from groups", () => {
    // Arrange / Act
    render(
      <FilterSidebar
        filters={{}}
        onChange={vi.fn()}
        groups={[
          {
            vendor: { id: "v1", name: "Acme", slug: "acme", logo_url: null },
            products: [
              {
                id: "p1",
                name: "P1",
                slug: "p1",
                category: "network",
                status: "active",
                log_type_counts: { total: 0, published: 0, draft: 0 },
                is_empty: true,
              },
              {
                id: "p2",
                name: "P2",
                slug: "p2",
                category: "network",
                status: "active",
                log_type_counts: { total: 0, published: 0, draft: 0 },
                is_empty: true,
              },
            ],
          },
        ]}
      />,
    );

    // Assert: Network 應顯示 count 2
    const networkBtn = screen.getByRole("button", { name: /Network/ });
    expect(networkBtn).toHaveTextContent("2");
  });
});
