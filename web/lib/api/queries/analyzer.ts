import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type ParseRequest = components["schemas"]["ParseRequest"];
type ParseResponse = components["schemas"]["ParseResponse"];
type MatchRequest = components["schemas"]["MatchRequest"];
type MatchResponse = components["schemas"]["MatchResponse"];

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
