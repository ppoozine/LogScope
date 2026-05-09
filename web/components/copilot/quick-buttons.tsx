"use client";

import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
import { useCopilotStore } from "@/lib/copilot/store";

export function QuickButtons() {
  const ctx = useCopilotStore((s) => s.pageContext);
  const isStreaming = useCopilotStore((s) => s.isStreaming);
  const { send } = useStreamingChat();

  if (!ctx || ctx.page !== "analyzer" || ctx.logs.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 border-t border-border bg-background px-3 py-2">
      <button
        type="button"
        disabled={isStreaming}
        onClick={() =>
          void send("請解釋 <logs> 中的這幾筆，依照 process 步驟逐項標出格式、欄位和異常值。")
        }
        className="rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs text-purple-800 hover:bg-purple-100 disabled:opacity-50"
      >
        ✦ 解釋這幾筆 log
      </button>
      <button
        type="button"
        disabled={isStreaming}
        onClick={() =>
          void send(
            "請依照 <logs> 與 <current_vrl> 寫一段 VRL，把欄位 parse 出來；輸出 ```vrl ... ``` 區塊與 edge case 說明。",
            { skill: "vrl_generate" },
          )
        }
        className="rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs text-purple-800 hover:bg-purple-100 disabled:opacity-50"
      >
        ✦ 生成 VRL
      </button>
    </div>
  );
}
