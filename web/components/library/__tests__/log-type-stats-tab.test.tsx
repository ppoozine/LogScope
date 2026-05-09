import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { LogTypeStatsTab } from "../log-type-stats-tab";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("LogTypeStatsTab", () => {
  it("shows banner when stats disabled", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: false,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(withQuery(<LogTypeStatsTab logTypeId="lt1" />));
    await waitFor(() => expect(screen.getByText(/啟用 ClickHouse/i)).toBeInTheDocument());
  });

  it("renders empty state when timeline has no entries", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/stats", () =>
        HttpResponse.json({
          data: {
            enabled: true,
            range_days: 7,
            timeline: [],
            engine_usage: [],
            totals: { total: 0, success: 0, error: 0, success_rate: 0 },
          },
        }),
      ),
    );
    render(withQuery(<LogTypeStatsTab logTypeId="lt1" />));
    await waitFor(() => expect(screen.getByText(/無 parse 紀錄/i)).toBeInTheDocument());
  });
});
