// web/lib/api/client.ts
const BASE_URL = ""; // dev: rewritten to localhost:8000 by next.config; prod: same-origin

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
  const url = new URL(`${BASE_URL}${path}`, "http://placeholder");
  if (opts.searchParams) {
    for (const [k, v] of Object.entries(opts.searchParams)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    }
  }
  // For client side, only relative path matters; for server side, callers must
  // pass an absolute path. We rebuild path from URL parts.
  const finalUrl = `${url.pathname}${url.search}`;

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
