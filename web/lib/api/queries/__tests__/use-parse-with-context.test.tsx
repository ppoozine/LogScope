import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useParse } from "@/lib/api/queries/analyzer";
import { server } from "@/test/msw/server";
import { makeQueryClient } from "@/test/utils";

function wrapper() {
  const qc = makeQueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useParse forwards Library context", () => {
  it("includes log_type_id and parse_rule_id in body when provided", async () => {
    let captured: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/v1/analyzer/parse", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ data: { kind: "empty", engine: "0.32" } });
      }),
    );
    const { result } = renderHook(() => useParse(), { wrapper: wrapper() });
    await waitFor(() => expect(typeof result.current.mutate).toBe("function"));
    await result.current.mutateAsync({
      vrl_code: ".x = 1",
      logs: ["a"],
      engine_version: "0.32",
      log_type_id: "lt1",
      parse_rule_id: "r1",
    });
    expect(captured).not.toBeNull();
    expect(captured!.log_type_id).toBe("lt1");
    expect(captured!.parse_rule_id).toBe("r1");
  });
});
