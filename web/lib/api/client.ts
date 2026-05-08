// web/lib/api/client.ts
// Browser: relative path, rewritten by next.config rewrites.
// Server (RSC / Server Actions): Next.js rewrites don't apply, need absolute URL.
const BASE_URL =
  typeof window === "undefined" ? (process.env.INTERNAL_API_URL ?? "http://localhost:8000") : "";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type FetchOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  searchParams?: Record<string, string | undefined>;
  // For server-side rendering — pass cookie header explicitly
  cookie?: string;
};

export async function apiFetch<T = unknown>(path: string, opts: FetchOptions = {}): Promise<T> {
  // When BASE_URL is empty (browser / jsdom), path is relative ("/api/v1/…").
  // new URL() in Node.js rejects bare relative paths, so we supply a synthetic
  // base that is stripped back out before the final fetch call.
  const urlBase = BASE_URL !== "" ? BASE_URL : "http://localhost";
  const url = new URL(`${BASE_URL}${path}`, urlBase);
  if (opts.searchParams) {
    for (const [k, v] of Object.entries(opts.searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    }
  }
  // Browser: relative URL works; server: absolute URL required (BASE_URL is set).
  const finalUrl = typeof window === "undefined" ? url.toString() : `${url.pathname}${url.search}`;

  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.cookie) headers.Cookie = opts.cookie;

  const res = await fetch(finalUrl, {
    method: opts.method ?? "GET",
    headers,
    credentials: "include",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let code = "unknown";
    let detail = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      detail = body?.error?.detail ?? detail;
    } catch {
      // not JSON
    }
    throw new ApiError(res.status, code, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}
