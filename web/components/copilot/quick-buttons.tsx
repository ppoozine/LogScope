"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api/client";
import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
import { useCopilotStore } from "@/lib/copilot/store";

type MatchCandidate = {
  vendor_slug: string;
  product_slug: string;
  log_type_name: string;
  confidence: number;
  reason: string;
};

type MatchResponse = { candidates: MatchCandidate[] };

export function QuickButtons() {
  const ctx = useCopilotStore((s) => s.pageContext);
  const isStreaming = useCopilotStore((s) => s.isStreaming);
  const { send } = useStreamingChat();
  const [matching, setMatching] = useState(false);

  if (!ctx || ctx.page !== "analyzer" || ctx.logs.length === 0) return null;

  const handleMatchLibrary = async () => {
    if (matching || ctx.logs.length === 0) return;
    setMatching(true);
    try {
      const r = await apiFetch<{ data: MatchResponse }>("/api/v1/analyzer/match", {
        method: "POST",
        body: { raw_log: ctx.logs[0], top_k: 3 },
      });
      const lines = r.data.candidates.map(
        (c, i) =>
          `Candidate ${i + 1}: ${c.vendor_slug}/${c.product_slug}, log_type=${c.log_type_name}, confidence=${c.confidence.toFixed(2)}\n  reason: ${c.reason}`,
      );
      const message = `請依下列 candidates 比對 <logs> 中的 log，告訴我哪一個最可能、為什麼，以及不符合的地方。\n\n${lines.join("\n\n")}`;
      void send(message, { skill: "log_explain" });
    } catch {
      window.alert("比對暫時無法使用");
    } finally {
      setMatching(false);
    }
  };

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
      {ctx.vrl && (
        <button
          type="button"
          disabled={isStreaming}
          onClick={() =>
            void send(
              "請優化 <current_vrl>，看 <parse_results> 中哪幾行錯了。輸出 ```vrl ... ``` 區塊（單一完整程式）+「改了什麼」逐行說明。",
              { skill: "vrl_optimize" },
            )
          }
          className="rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs text-purple-800 hover:bg-purple-100 disabled:opacity-50"
        >
          ✦ 最佳化 VRL
        </button>
      )}
      <button
        type="button"
        disabled={isStreaming}
        onClick={() =>
          void send("請列出 <logs> 中各筆的異常值，每筆標示「第 N 筆」+ 一行描述 + 〔依據〕。", {
            skill: "anomaly",
          })
        }
        className="rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs text-purple-800 hover:bg-purple-100 disabled:opacity-50"
      >
        ✦ 找異常值
      </button>
      <button
        type="button"
        disabled={isStreaming || matching}
        onClick={() => void handleMatchLibrary()}
        className="rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs text-purple-800 hover:bg-purple-100 disabled:opacity-50"
      >
        ✦ {matching ? "比對中…" : "比對 Library"}
      </button>
    </div>
  );
}
