"use client";

import { useEffect } from "react";

import { useCopilot } from "@/components/providers/copilot-context";
import { cn } from "@/lib/utils";

export function CopilotToggle() {
  const { isOpen, toggle } = useCopilot();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // ⌘\ on macOS, Ctrl+\ elsewhere
      if (e.key === "\\" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isOpen ? "Close Copilot" : "Open Copilot"}
      className={cn(
        "fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full",
        "bg-purple-600 text-white shadow-lg transition hover:bg-purple-700",
        isOpen && "rotate-90",
      )}
    >
      <span className="text-lg">✦</span>
    </button>
  );
}
