"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useLogin } from "@/lib/api/queries/auth";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") ?? "/library";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const login = useLogin();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ email, password });
      router.push(next);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "帳號或密碼錯誤" : err.message);
      } else {
        setError("登入失敗，請稍後再試");
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full max-w-sm flex-col gap-4 rounded-lg border bg-card p-8 shadow-sm"
    >
      <h1 className="text-xl font-semibold tracking-tight">登入 LogScope</h1>

      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="password">密碼</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <Button type="submit" disabled={login.isPending}>
        {login.isPending ? "登入中…" : "登入"}
      </Button>
    </form>
  );
}
