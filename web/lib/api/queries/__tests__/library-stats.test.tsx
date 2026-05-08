// web/lib/api/queries/__tests__/library-stats.test.ts
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useLogTypeStats, useProductCoverage } from "@/lib/api/queries/library-stats";
import { usePromoteParseRule } from "@/lib/api/queries/parse-rules";
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

describe("useLogTypeStats", () => {
  it("fetches stats with given range", async () => {
    server.use(
      http.get(`${BASE}/library/log_types/abc/stats`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("range")).toBe("14d");
        return HttpResponse.json({
          data: {
            enabled: true,
            range_days: 14,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        });
      }),
    );

    const { result } = withClient(() => useLogTypeStats("abc", "14d"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.range_days).toBe(14);
  });
});

describe("useProductCoverage", () => {
  it("fetches coverage for vendor/product", async () => {
    server.use(
      http.get(`${BASE}/library/products/v/p/coverage`, () =>
        HttpResponse.json({
          data: { enabled: true, range_days: 7, log_types: [] },
        }),
      ),
    );
    const { result } = withClient(() => useProductCoverage("v", "p", "7d"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.enabled).toBe(true);
  });
});

describe("usePromoteParseRule", () => {
  it("POSTs to /promote and resolves", async () => {
    server.use(
      http.post(`${BASE}/library/parse_rules/r1/promote`, () =>
        HttpResponse.json({
          data: {
            id: "r1",
            log_type_id: "lt1",
            version: 2,
            vrl_code: ".",
            engine_version: "0.32",
            status: "published",
            notes: null,
            created_at: "2026-05-08T00:00:00Z",
            updated_at: "2026-05-08T00:00:00Z",
          },
        }),
      ),
    );
    const { result } = withClient(() => usePromoteParseRule());
    const data = await result.current.mutateAsync("r1");
    expect(data.data.status).toBe("published");
  });
});
