"use client";

import { createContext, type ReactNode, useCallback, useContext, useState } from "react";

type CopilotState = {
  isOpen: boolean;
  toggle: () => void;
  close: () => void;
};

const Ctx = createContext<CopilotState | null>(null);

export function CopilotProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);
  const close = useCallback(() => setIsOpen(false), []);

  return <Ctx.Provider value={{ isOpen, toggle, close }}>{children}</Ctx.Provider>;
}

export function useCopilot(): CopilotState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCopilot must be used inside CopilotProvider");
  return v;
}
