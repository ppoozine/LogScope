import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/msw/server";
import { VersionsTab } from "../versions-tab";

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

const VERSIONS = [
  {
    id: "r3",
    log_type_id: "lt1",
    version: 3,
    vrl_code: ". = 3",
    engine_version: "0.32",
    status: "draft",
    notes: null,
    created_at: "2026-05-08T00:00:00Z",
    updated_at: "2026-05-08T00:00:00Z",
  },
  {
    id: "r2",
    log_type_id: "lt1",
    version: 2,
    vrl_code: ". = 2",
    engine_version: "0.32",
    status: "published",
    notes: null,
    created_at: "2026-05-07T00:00:00Z",
    updated_at: "2026-05-07T00:00:00Z",
  },
  {
    id: "r1",
    log_type_id: "lt1",
    version: 1,
    vrl_code: ". = 1",
    engine_version: "0.32",
    status: "archived",
    notes: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
  },
];

describe("VersionsTab", () => {
  it("renders rows for all versions with status badges", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => {
      expect(screen.getByText("v3")).toBeInTheDocument();
      expect(screen.getByText("v2")).toBeInTheDocument();
      expect(screen.getByText("v1")).toBeInTheDocument();
    });
    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.getByText("published")).toBeInTheDocument();
    expect(screen.getByText("archived")).toBeInTheDocument();
  });

  it("shows Promote only for draft", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => screen.getByText("v3"));
    const promoteButtons = screen.getAllByRole("button", { name: /Promote/i });
    expect(promoteButtons).toHaveLength(1);
  });

  it("clicking Promote opens confirm and POSTs on confirm", async () => {
    server.use(
      http.get("/api/v1/library/log_types/lt1/parse_rules", () =>
        HttpResponse.json({ data: VERSIONS }),
      ),
      http.post("/api/v1/library/parse_rules/r3/promote", () =>
        HttpResponse.json({ data: { ...VERSIONS[0], status: "published" } }),
      ),
    );
    render(withQuery(<VersionsTab logTypeId="lt1" />));
    await waitFor(() => screen.getByText("v3"));

    fireEvent.click(screen.getByRole("button", { name: /Promote/i }));
    const confirm = await screen.findByRole("button", { name: /確定/i });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /確定/i })).not.toBeInTheDocument(),
    );
  });
});
