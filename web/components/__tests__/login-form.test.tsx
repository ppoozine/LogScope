import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/login-form";
import { server } from "@/test/msw/server";
import { renderWithClient } from "@/test/utils";

const BASE = "/api/v1";

// Stub Next.js navigation hooks
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

describe("LoginForm", () => {
  it("renders email and password inputs", () => {
    // Arrange / Act
    renderWithClient(<LoginForm />);

    // Assert
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("密碼")).toBeInTheDocument();
  });

  it("submits and clears error on success", async () => {
    // Arrange
    const user = userEvent.setup();
    renderWithClient(<LoginForm />);

    // Act
    await user.type(screen.getByLabelText("Email"), "admin@logscope.local");
    await user.type(screen.getByLabelText("密碼"), "changeme");
    fireEvent.click(screen.getByRole("button", { name: /登入/ }));

    // Assert: should not display error after submit
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("shows error on 401", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/auth/login`, () =>
        HttpResponse.json(
          { error: { code: "unauthorized", detail: "invalid credentials" } },
          { status: 401 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithClient(<LoginForm />);

    // Act
    await user.type(screen.getByLabelText("Email"), "x@y.z");
    await user.type(screen.getByLabelText("密碼"), "wrong");
    fireEvent.click(screen.getByRole("button", { name: /登入/ }));

    // Assert
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("帳號或密碼錯誤");
    });
  });
});
