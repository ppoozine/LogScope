import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PUBLIC_PATHS = new Set(["/login"]);

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 跳過 API rewrites、static、Next 內部資源
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || pathname === "/favicon.ico") {
    return NextResponse.next();
  }

  const session = req.cookies.get("session")?.value;
  const loggedIn = !!session;

  // 已登入訪問 /login → /library
  if (loggedIn && pathname === "/login") {
    return NextResponse.redirect(new URL("/library", req.url));
  }

  // 未登入訪問非 public 路由 → /login?next=...
  if (!loggedIn && !PUBLIC_PATHS.has(pathname)) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
