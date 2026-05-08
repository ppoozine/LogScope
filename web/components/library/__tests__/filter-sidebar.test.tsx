import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FilterSidebar } from "@/components/library/filter-sidebar";

describe("FilterSidebar", () => {
  it("calls onChange with selected status", async () => {
    // Arrange
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FilterSidebar filters={{}} onChange={onChange} />);

    // Act
    await user.click(screen.getByRole("button", { name: /Published/ }));

    // Assert
    expect(onChange).toHaveBeenCalledWith({ status: "published" });
  });

  it("highlights active filter", () => {
    // Arrange / Act
    render(<FilterSidebar filters={{ status: "published" }} onChange={vi.fn()} />);

    // Assert
    const publishedBtn = screen.getByRole("button", { name: /Published/ });
    expect(publishedBtn).toHaveClass("bg-muted");
  });

  it("renders status filter options", () => {
    // Arrange / Act
    render(<FilterSidebar filters={{}} onChange={vi.fn()} />);

    // Assert
    expect(screen.getByRole("button", { name: /全部/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Published/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Draft/ })).toBeInTheDocument();
  });
});
