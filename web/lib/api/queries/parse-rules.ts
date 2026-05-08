// web/lib/api/queries/parse-rules.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

export function useParseRulesByLogType(logTypeId: string | null) {
  return useQuery<ParseRuleRead[]>({
    enabled: logTypeId !== null,
    queryKey: ["library", "parse-rules", logTypeId],
    queryFn: async () => {
      const r = await apiFetch<{ data: ParseRuleRead[] }>(
        `/api/v1/library/log_types/${logTypeId}/parse_rules`,
      );
      return r.data;
    },
  });
}

export function usePromoteParseRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) =>
      apiFetch<{ data: ParseRuleRead }>(`/api/v1/library/parse_rules/${ruleId}/promote`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["library", "parse-rules", data.data.log_type_id] });
      qc.invalidateQueries({ queryKey: ["library", "product-detail"] });
      qc.invalidateQueries({ queryKey: ["library", "overview"] });
    },
  });
}
