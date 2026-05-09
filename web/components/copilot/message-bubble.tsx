"use client";

import { RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
import { useCopilotStore } from "@/lib/copilot/store";
import type { ChatMessage } from "@/lib/copilot/types";
import { cn } from "@/lib/utils";

import { StreamingIndicator } from "./streaming-indicator";

type Props = {
  message: ChatMessage;
  isLastAssistant: boolean;
};

export function MessageBubble({ message, isLastAssistant }: Props) {
  const isUser = message.role === "user";
  const isStreaming = useCopilotStore((s) => s.isStreaming);
  const messages = useCopilotStore((s) => s.messages);
  const { send } = useStreamingChat();
  const hasError = !!message.error;
  const showStreamingDots =
    isLastAssistant && isStreaming && !hasError && message.content.length === 0;

  const handleRetry = () => {
    // re-send the last user message
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) void send(lastUser.content);
  };

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isUser
            ? "bg-purple-600 text-white"
            : hasError
              ? "border border-red-500 bg-red-50 text-red-900"
              : "bg-muted text-foreground",
        )}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{message.content}</span>
        ) : hasError ? (
          <div>
            <div>{message.error}</div>
            <button
              type="button"
              onClick={handleRetry}
              className="mt-2 inline-flex items-center gap-1 rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
            >
              <RefreshCw size={12} />
              重試
            </button>
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}
        {showStreamingDots && (
          <div className="mt-1">
            <StreamingIndicator />
          </div>
        )}
      </div>
    </div>
  );
}
