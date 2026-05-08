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
    <div className="flex min-h-screen flex-col">
      <TopNav />
      <main className="flex-1">{children}</main>
      <CopilotPanel />
      <CopilotToggle />
    </div>
  );
}
