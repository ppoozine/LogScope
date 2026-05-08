import { redirect } from "next/navigation";
import { Suspense } from "react";

import { LoginForm } from "@/components/login-form";
import { getServerUser } from "@/lib/auth/server";

export default async function LoginPage() {
  // 已登入 → 直接跳 /library。
  // 注意：這裡用 getServerUser 真的 hit /me 驗 cookie 還有效，避免 stale cookie
  // （cookie 還在但 redis session 已過期）造成 /login ↔ /library redirect loop。
  const user = await getServerUser();
  if (user) {
    redirect("/library");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
