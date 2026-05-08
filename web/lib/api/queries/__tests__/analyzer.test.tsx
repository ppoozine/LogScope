import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useMatch, useParse } from "@/lib/api/queries/analyzer";
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

describe("useParse", () => {
  it("posts vrl + logs and unwraps data", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/analyzer/parse`, () =>
        HttpResponse.json({
          data: {
            kind: "ok",
            engine: "0.32",
            summary: { total: 1, success: 1, error: 0 },
            results: [{ index: 0, input: "a", status: "success", output: { x: 1 } }],
          },
        }),
      ),
    );
    const { result } = withClient(() => useParse());

    // Act
    result.current.mutate({
      vrl_code: ".x = 1\n.",
      logs: ["a"],
      engine_version: "0.32",
    });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.summary?.success).toBe(1);
  });
});

describe("useMatch", () => {
  it("returns candidates list", async () => {
    // Arrange
    server.use(
      http.post(`${BASE}/analyzer/match`, () =>
        HttpResponse.json({
          data: {
            candidates: [
              {
                vendor_slug: "palo-alto",
                product_slug: "pan-os",
                log_type_id: "11111111-1111-1111-1111-111111111111",
                log_type_name: "Traffic",
                confidence: 0.9,
                reason: "符合 PAN-OS 格式",
              },
            ],
          },
        }),
      ),
    );
    const { result } = withClient(() => useMatch());

    // Act
    result.current.mutate({ raw_log: "x", top_k: 3 });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.candidates).toHaveLength(1);
  });
});
