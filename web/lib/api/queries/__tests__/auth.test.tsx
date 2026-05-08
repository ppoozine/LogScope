// web/lib/api/queries/__tests__/auth.test.tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useLogin, useMe } from "@/lib/api/queries/auth";
import { server } from "@/test/msw/server";
import { makeQueryClient } from "@/test/utils";

const BASE = "/api/v1";

function withClient<T>(hook: () => T) {
  const client = makeQueryClient();
  return renderHook(hook, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}

describe("useLogin", () => {
  it("returns ok on valid credentials", async () => {
    // Arrange
    const { result } = withClient(() => useLogin());

    // Act
    result.current.mutate({
      email: "admin@logscope.local",
      password: "changeme",
    });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("throws ApiError on 401", async () => {
    // Arrange
    const { result } = withClient(() => useLogin());

    // Act / Assert
    await expect(
      result.current.mutateAsync({ email: "wrong@x.y", password: "wrong" }),
    ).rejects.toMatchObject({ status: 401, code: "unauthorized" });
  });
});

describe("useMe", () => {
  it("fetches admin user", async () => {
    // Arrange
    const { result } = withClient(() => useMe());

    // Act
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.data?.email).toBe("admin@logscope.local");
  });

  it("returns 401 cleanly when /me unauthorized", async () => {
    // Arrange
    server.use(
      http.get(`${BASE}/auth/me`, () =>
        HttpResponse.json(
          { error: { code: "unauthorized", detail: "missing session" } },
          { status: 401 },
        ),
      ),
    );
    const { result } = withClient(() => useMe());

    // Act
    await waitFor(() => expect(result.current.isError).toBe(true));

    // Assert
    expect(result.current.error?.status).toBe(401);
  });
});
