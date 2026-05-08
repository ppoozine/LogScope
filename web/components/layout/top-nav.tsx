import Link from "next/link";

import { UserMenu } from "@/components/layout/user-menu";
import { cn } from "@/lib/utils";

type Tab = { href: string; label: string; disabled?: boolean; comingIn?: string };

const TABS: Tab[] = [
  { href: "/library", label: "Library" },
  { href: "/analyzer", label: "Analyzer", disabled: true, comingIn: "spec C" },
  { href: "/copilot", label: "Copilot", disabled: true, comingIn: "spec D" },
];

export function TopNav({ activeHref }: { activeHref?: string }) {
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-4 border-b bg-background px-6">
      <Link href="/library" className="text-base font-bold tracking-tight text-purple-700">
        LogScope
      </Link>

      <nav className="flex items-center gap-1">
        {TABS.map((tab) => (
          <NavTab key={tab.href} tab={tab} isActive={activeHref?.startsWith(tab.href) ?? false} />
        ))}
      </nav>

      <div className="ml-auto">
        <UserMenu />
      </div>
    </header>
  );
}

function NavTab({ tab, isActive }: { tab: Tab; isActive: boolean }) {
  const className = cn(
    "rounded px-3 py-1.5 text-sm font-medium transition-colors",
    isActive ? "bg-teal-50 text-teal-700" : "text-muted-foreground hover:text-foreground",
    tab.disabled && "pointer-events-none opacity-50",
  );

  if (tab.disabled) {
    return (
      <span className={className} title={tab.comingIn ? `Coming in ${tab.comingIn}` : undefined}>
        {tab.label}
      </span>
    );
  }

  return (
    <Link href={tab.href} className={className}>
      {tab.label}
    </Link>
  );
}
