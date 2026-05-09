import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
import { useCopilotStore } from "@/lib/copilot/store";
import { server } from "@/test/msw/server";

function resetStore() {
  useCopilotStore.setState({
    isOpen: false,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
  });
}

function sseResponse(frames: string[]): HttpResponse<string> {
  const body = frames.join("");
  return new HttpResponse(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("useStreamingChat", () => {
  it("appends user + assistant messages and streams text into the assistant", async () => {
    // Arrange
    resetStore();
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sseResponse([
          'event: text_delta\ndata: {"text":"hi "}\n\n',
          'event: text_delta\ndata: {"text":"there"}\n\n',
          "event: done\ndata: {}\n\n",
        ]),
      ),
    );
    const { result } = renderHook(() => useStreamingChat());

    // Act
    await act(async () => {
      await result.current.send("explain this log");
    });

    // Assert
    await waitFor(() => {
      expect(useCopilotStore.getState().isStreaming).toBe(false);
    });
    const msgs = useCopilotStore.getState().messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0]).toMatchObject({ role: "user", content: "explain this log" });
    expect(msgs[1]).toMatchObject({ role: "assistant", content: "hi there" });
  });

  it("sets error on assistant bubble for backend error event", async () => {
    // Arrange
    resetStore();
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sseResponse([
          'event: error\ndata: {"code":"no_api_key","message":"沒設 key"}\n\n',
          "event: done\ndata: {}\n\n",
        ]),
      ),
    );
    const { result } = renderHook(() => useStreamingChat());

    // Act
    await act(async () => {
      await result.current.send("hi");
    });

    // Assert
    await waitFor(() => {
      expect(useCopilotStore.getState().isStreaming).toBe(false);
    });
    const msgs = useCopilotStore.getState().messages;
    expect(msgs[1].error).toBe("沒設 key");
  });

  it("does not double-send when isStreaming is true", async () => {
    // Arrange
    resetStore();
    useCopilotStore.setState({ isStreaming: true });
    const { result } = renderHook(() => useStreamingChat());

    // Act
    await act(async () => {
      await result.current.send("nope");
    });

    // Assert: nothing got appended
    expect(useCopilotStore.getState().messages).toHaveLength(0);
  });
});
