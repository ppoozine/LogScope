import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PUBLIC_PATHS = new Set(["/login"]);

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // 跳過 API rewrites、static、Next 內部資源
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || pathname === "/favicon.ico") {
    return NextResponse.next();
  }

  // Note: 我們只用 cookie 是否「存在」做粗篩——存在就放行給後續頁面驗證。
  // 不用「有 cookie = 已登入」判斷，因為 server-side session 可能失效（redis 重啟）；
  // 那種情況下 (authed) layout 會 redirect /login，proxy 若再判定 loggedIn 跳 /library 就死循環。
  // 「已登入訪 /login → /library」的判斷改寫在 /login page 內（會用 getServerUser 真的驗）。
  const session = req.cookies.get("session")?.value;

  if (!session && !PUBLIC_PATHS.has(pathname)) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
