"use client";

import { Send, Square } from "lucide-react";
import { useCallback, useState } from "react";

import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
import { useCopilotStore } from "@/lib/copilot/store";
import { cn } from "@/lib/utils";

export function ChatInput() {
  const [draft, setDraft] = useState("");
  const isStreaming = useCopilotStore((s) => s.isStreaming);
  const { send, abort } = useStreamingChat();

  const handleSend = useCallback(() => {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft("");
    void send(text);
  }, [draft, isStreaming, send]);

  return (
    <div className="flex items-end gap-2 border-t border-border bg-background p-3">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
        placeholder="問 Copilot…"
        rows={1}
        className={cn(
          "min-h-[40px] max-h-[120px] flex-1 resize-y rounded-md border bg-muted px-3 py-2 text-sm",
          "focus:outline-none focus:ring-1 focus:ring-purple-500",
        )}
        disabled={isStreaming}
      />
      {isStreaming ? (
        <button
          type="button"
          onClick={abort}
          aria-label="Stop"
          className="flex h-10 w-10 items-center justify-center rounded-md bg-red-600 text-white hover:bg-red-700"
        >
          <Square size={16} />
        </button>
      ) : (
        <button
          type="button"
          onClick={handleSend}
          aria-label="Send"
          disabled={!draft.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-md bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
        >
          <Send size={16} />
        </button>
      )}
    </div>
  );
}
