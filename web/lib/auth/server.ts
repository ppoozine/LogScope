"use server";

import { cookies } from "next/headers";

import { ApiError, apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type UserRead = components["schemas"]["UserRead"];

export async function getServerUser(): Promise<UserRead | null> {
  const cookieStore = await cookies();
  const session = cookieStore.get("session")?.value;
  if (!session) return null;

  try {
    const r = await apiFetch<{ data: UserRead }>("/api/v1/auth/me", {
      cookie: `session=${session}`,
    });
    return r.data;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}
