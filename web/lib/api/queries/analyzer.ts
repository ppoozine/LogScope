import { useMutation, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type ParseRequest = components["schemas"]["ParseRequest"];
type ParseResponse = components["schemas"]["ParseResponse"];
type MatchRequest = components["schemas"]["MatchRequest"];
type MatchResponse = components["schemas"]["MatchResponse"];
type FixtureItem = components["schemas"]["FixtureItem"];
type FixtureListResponse = components["schemas"]["FixtureListResponse"];

export function useParse() {
  return useMutation<ParseResponse, Error, ParseRequest>({
    mutationFn: async (body) => {
      const r = await apiFetch<{ data: ParseResponse }>("/api/v1/analyzer/parse", {
        method: "POST",
        body,
      });
      return r.data;
    },
  });
}

export function useMatch() {
  return useMutation<MatchResponse, Error, MatchRequest>({
    mutationFn: async (body) => {
      const r = await apiFetch<{ data: MatchResponse }>("/api/v1/analyzer/match", {
        method: "POST",
        body,
      });
      return r.data;
    },
  });
}

export function useFixtures() {
  return useQuery<FixtureItem[]>({
    queryKey: ["analyzer", "fixtures"],
    queryFn: async () => {
      const r = await apiFetch<{ data: FixtureListResponse }>("/api/v1/analyzer/fixtures");
      return r.data.fixtures;
    },
    staleTime: 1000 * 60 * 10, // 10 min — fixtures change rarely
  });
}
