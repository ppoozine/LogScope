import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "@/components/library/empty-state";

describe("EmptyState", () => {
  it("renders message and calls onAddVendor when button clicked", async () => {
    // Arrange
    const onAddVendor = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<EmptyState onAddVendor={onAddVendor} />);
    await user.click(screen.getByRole("button", { name: /新增 Vendor/ }));

    // Assert
    expect(screen.getByText(/還沒有任何 vendor/)).toBeInTheDocument();
    expect(onAddVendor).toHaveBeenCalledOnce();
  });
});
