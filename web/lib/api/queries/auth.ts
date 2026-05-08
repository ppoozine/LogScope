// web/lib/api/queries/auth.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type ApiError, apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type LoginRequest = components["schemas"]["LoginRequest"];
type UserRead = components["schemas"]["UserRead"];

type DataResponseUser = { data: UserRead };
type DataResponseDict = { data: Record<string, unknown> };

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) =>
      apiFetch<DataResponseDict>("/api/v1/auth/login", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<DataResponseDict>("/api/v1/auth/logout", { method: "POST" }),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useMe() {
  return useQuery<UserRead, ApiError>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const r = await apiFetch<DataResponseUser>("/api/v1/auth/me");
      return r.data;
    },
    retry: false,
    staleTime: 1000 * 60 * 5,
  });
}
