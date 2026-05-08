import { HttpResponse, http } from "msw";

const BASE = "/api/v1"; // relative — jsdom resolves to http://localhost/api/v1

export const handlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email === "admin@logscope.local" && body.password === "changeme") {
      return HttpResponse.json(
        { data: { ok: true } },
        { headers: { "Set-Cookie": "session=test-sid; HttpOnly; SameSite=Lax" } },
      );
    }
    return HttpResponse.json(
      { error: { code: "unauthorized", detail: "invalid credentials" } },
      { status: 401 },
    );
  }),

  http.post(`${BASE}/auth/logout`, () =>
    HttpResponse.json(
      { data: { ok: true } },
      {
        headers: { "Set-Cookie": "session=; Max-Age=0" },
      },
    ),
  ),

  http.get(`${BASE}/auth/me`, () =>
    HttpResponse.json({
      data: {
        id: "11111111-1111-1111-1111-111111111111",
        email: "admin@logscope.local",
        display_name: "Admin",
        is_active: true,
        created_at: "2026-05-08T00:00:00Z",
      },
    }),
  ),

  http.get(`${BASE}/library/overview`, () => HttpResponse.json({ data: [] })),
];
