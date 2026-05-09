import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { CopilotPanel } from "@/components/layout/copilot-panel";
import { CopilotToggle } from "@/components/layout/copilot-toggle";
import { TopNav } from "@/components/layout/top-nav";
import { getServerUser } from "@/lib/auth/server";

export default async function AuthedLayout({ children }: { children: ReactNode }) {
  const user = await getServerUser();
  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex h-dvh flex-col">
      <TopNav />
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-auto">{children}</main>
        <CopilotPanel />
      </div>
      <CopilotToggle />
    </div>
  );
}
