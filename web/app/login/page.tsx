import { Suspense } from "react";

import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
