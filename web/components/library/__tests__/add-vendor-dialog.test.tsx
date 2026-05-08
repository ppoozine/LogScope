import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { AddVendorDialog } from "@/components/library/add-vendor-dialog";
import { server } from "@/test/msw/server";
import { renderWithClient } from "@/test/utils";

const BASE = "/api/v1";

describe("AddVendorDialog", () => {
  it("submits and closes on success", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/library/vendors`, () =>
        HttpResponse.json(
          {
            data: {
              id: "v1",
              name: "Acme",
              slug: "acme",
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
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<AddVendorDialog open onOpenChange={onOpenChange} />);

    // Act
    await user.type(screen.getByLabelText("名稱"), "Acme");
    fireEvent.click(screen.getByRole("button", { name: /建立$/ }));

    // Assert
    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("shows 409 error when slug exists", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/library/vendors`, () =>
        HttpResponse.json(
          { error: { code: "conflict", detail: "vendor slug already exists" } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithClient(<AddVendorDialog open onOpenChange={vi.fn()} />);

    // Act
    await user.type(screen.getByLabelText("名稱"), "Acme");
    fireEvent.click(screen.getByRole("button", { name: /建立$/ }));

    // Assert
    await waitFor(() => {
      expect(screen.getByText(/此 slug 已存在/)).toBeInTheDocument();
    });
  });
});
