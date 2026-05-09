import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { ChatMessage, PageContext } from "./types";

const MAX_HISTORY = 20;

function newId(): string {
  // small ULID-ish, no extra dep
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

type CopilotState = {
  isOpen: boolean;
  messages: ChatMessage[];
  pageContext: PageContext | null;
  isStreaming: boolean;
  abortController: AbortController | null;

  toggle: () => void;
  open: () => void;
  close: () => void;
  setPageContext: (ctx: PageContext | null) => void;
  setStreaming: (v: boolean) => void;
  setAbortController: (c: AbortController | null) => void;

  appendUserMessage: (content: string) => void;
  appendAssistantPlaceholder: () => string;
  appendDelta: (id: string, delta: string) => void;
  setMessageError: (id: string, error: string) => void;
  finalizeMessage: (id: string) => void;
  clearMessages: () => void;
};

function trim(messages: ChatMessage[]): ChatMessage[] {
  return messages.length <= MAX_HISTORY ? messages : messages.slice(messages.length - MAX_HISTORY);
}

export const useCopilotStore = create<CopilotState>()(
  persist(
    (set) => ({
      isOpen: false,
      messages: [],
      pageContext: null,
      isStreaming: false,
      abortController: null,

      toggle: () => set((s) => ({ isOpen: !s.isOpen })),
      open: () => set({ isOpen: true }),
      close: () => set({ isOpen: false }),
      setPageContext: (ctx) => set({ pageContext: ctx }),
      setStreaming: (v) => set({ isStreaming: v }),
      setAbortController: (c) => set({ abortController: c }),

      appendUserMessage: (content) =>
        set((s) => ({
          messages: trim([...s.messages, { id: newId(), role: "user", content }]),
        })),

      appendAssistantPlaceholder: () => {
        const id = newId();
        set((s) => ({
          messages: trim([...s.messages, { id, role: "assistant", content: "" }]),
        }));
        return id;
      },

      appendDelta: (id, delta) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + delta } : m)),
        })),

      setMessageError: (id, error) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, error } : m)),
        })),

      finalizeMessage: (_id) => {
        // No-op for D1 — content already accumulated. Reserved for future
        // post-processing (markdown sanitisation, code-block detection).
      },

      clearMessages: () => set({ messages: [] }),
    }),
    {
      name: "logscope.copilot",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({ isOpen: s.isOpen, messages: s.messages }),
    },
  ),
);
