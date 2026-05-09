"use client";

import { useEffect, useRef } from "react";

import { useCopilotStore } from "@/lib/copilot/store";

import { MessageBubble } from "./message-bubble";

export function MessageList() {
  const messages = useCopilotStore((s) => s.messages);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever message count or streaming content changes.
  // Both deps are read in the guard so biome's exhaustive-deps rule is satisfied,
  // and they truthfully drive when the effect re-runs (new turn vs. delta append).
  const messageCount = messages.length;
  const lastContentLen = messages[messages.length - 1]?.content.length ?? 0;
  useEffect(() => {
    const el = containerRef.current;
    if (!el || messageCount + lastContentLen === 0) return;
    el.scrollTop = el.scrollHeight;
  }, [messageCount, lastContentLen]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted-foreground">
        Copilot 已就緒。輸入問題或點下方快速指令。
      </div>
    );
  }

  // last assistant message index — for streaming dot
  let lastAssistantIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") {
      lastAssistantIdx = i;
      break;
    }
  }

  return (
    <div ref={containerRef} className="flex flex-1 flex-col gap-3 overflow-y-auto px-3 py-3">
      {messages.map((m, idx) => (
        <MessageBubble key={m.id} message={m} isLastAssistant={idx === lastAssistantIdx} />
      ))}
    </div>
  );
}
