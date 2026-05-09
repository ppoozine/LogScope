"use client";

import type { ReactNode } from "react";

import { useCopilotStore } from "@/lib/copilot/store";

/**
 * Kept as a no-op so root layout's <CopilotProvider> keeps compiling.
 * Zustand needs no Provider; state lives in `useCopilotStore`.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

type CopilotState = {
  isOpen: boolean;
  toggle: () => void;
  close: () => void;
};

export function useCopilot(): CopilotState {
  const isOpen = useCopilotStore((s) => s.isOpen);
  const toggle = useCopilotStore((s) => s.toggle);
  const close = useCopilotStore((s) => s.close);
  return { isOpen, toggle, close };
}
