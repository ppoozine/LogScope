import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { extractVrlBlock } from "./extract-vrl-block";
import type { ChatMessage, EditorBridge, PageContext, PendingInsert, SkillName } from "./types";

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
  editorBridge: EditorBridge;
  pendingInsert: PendingInsert | null;
  lastSkill: SkillName | null;

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

  registerEditor: (b: { setVrl: (s: string) => void; getVrl: () => string }) => void;
  unregisterEditor: () => void;
  requestInsert: (proposedVrl: string, messageId: string) => void;
  confirmInsert: () => void;
  cancelInsert: () => void;
  setLastSkill: (s: SkillName | null) => void;
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
      editorBridge: { setVrl: null, getVrl: () => "" },
      pendingInsert: null,
      lastSkill: null,

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

      finalizeMessage: (id) =>
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id && m.role === "assistant"
              ? { ...m, vrlBlock: extractVrlBlock(m.content) ?? undefined }
              : m,
          ),
        })),

      clearMessages: () => set({ messages: [] }),

      registerEditor: ({ setVrl, getVrl }) => set({ editorBridge: { setVrl, getVrl } }),

      unregisterEditor: () => set({ editorBridge: { setVrl: null, getVrl: () => "" } }),

      requestInsert: (proposedVrl, messageId) => set({ pendingInsert: { proposedVrl, messageId } }),

      confirmInsert: () => {
        const { pendingInsert, editorBridge } = useCopilotStore.getState();
        if (!pendingInsert) return;
        if (editorBridge.setVrl) editorBridge.setVrl(pendingInsert.proposedVrl);
        set({ pendingInsert: null });
      },

      cancelInsert: () => set({ pendingInsert: null }),

      setLastSkill: (lastSkill) => set({ lastSkill }),
    }),
    {
      name: "logscope.copilot",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (s) => ({ isOpen: s.isOpen, messages: s.messages }),
    },
  ),
);
