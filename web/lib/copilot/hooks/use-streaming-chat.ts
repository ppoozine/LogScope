"use client";

import { useCallback } from "react";

import { streamChat } from "@/lib/copilot/sse-client";
import { useCopilotStore } from "@/lib/copilot/store";
import type {
  BackendPageContext,
  ChatRequestBody,
  PageContext,
  SkillName,
} from "@/lib/copilot/types";

function pickDefaultSkill(ctx: PageContext | null): SkillName | null {
  if (!ctx) return null;
  if (ctx.page !== "analyzer") return null;
  return "log_explain";
}

function toBackendPageContext(ctx: PageContext): BackendPageContext {
  return {
    page: ctx.page,
    vrl: ctx.vrl,
    vrl_engine: ctx.vrlEngine,
    logs: ctx.logs,
    parse_results: ctx.parseResults.map((r) => ({
      index: r.index,
      status: r.status,
      ...(r.message !== undefined ? { message: r.message } : {}),
    })),
    match_top_candidate: ctx.matchTopCandidate
      ? {
          vendor_slug: ctx.matchTopCandidate.vendorSlug,
          product_slug: ctx.matchTopCandidate.productSlug,
          log_type_name: ctx.matchTopCandidate.logTypeName,
          confidence: ctx.matchTopCandidate.confidence,
        }
      : null,
  };
}

export function useStreamingChat() {
  const send = useCallback(async (text: string, options?: { skill?: SkillName }) => {
    const state0 = useCopilotStore.getState();
    if (state0.isStreaming) return;

    const ctx = state0.pageContext;
    const skill: SkillName | null = options?.skill ?? pickDefaultSkill(ctx);

    // immediately mark streaming to block double-clicks
    useCopilotStore.setState({ isStreaming: true, lastSkill: skill });

    state0.appendUserMessage(text);
    const assistantId = state0.appendAssistantPlaceholder();
    const controller = new AbortController();
    useCopilotStore.setState({ abortController: controller });

    // Build request body from CURRENT messages (includes the user turn we just appended).
    // Drop the last (empty assistant) message so backend sees a user-final history.
    const allMessages = useCopilotStore.getState().messages;
    const messagesForRequest = allMessages
      .slice(0, -1)
      .map((m) => ({ role: m.role, content: m.content }));

    const body: ChatRequestBody = {
      messages: messagesForRequest,
      skill,
      page_context: ctx ? toBackendPageContext(ctx) : null,
    };

    try {
      for await (const ev of streamChat(body, controller.signal)) {
        if (ev.type === "text_delta") {
          useCopilotStore.getState().appendDelta(assistantId, ev.text);
        } else if (ev.type === "error") {
          useCopilotStore.getState().setMessageError(assistantId, ev.message);
        } else if (ev.type === "done") {
          useCopilotStore.getState().finalizeMessage(assistantId);
          break;
        }
      }
    } catch (err) {
      const e = err as Error;
      if (e.name === "AbortError") {
        useCopilotStore.getState().finalizeMessage(assistantId);
      } else {
        useCopilotStore.getState().setMessageError(assistantId, "連線中斷");
      }
    } finally {
      useCopilotStore.setState({ isStreaming: false, abortController: null });
    }
  }, []);

  const abort = useCallback(() => {
    const c = useCopilotStore.getState().abortController;
    c?.abort();
  }, []);

  return { send, abort };
}
