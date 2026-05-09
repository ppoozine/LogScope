import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { CopilotPanel } from "@/components/layout/copilot-panel";
import { useCopilotStore } from "@/lib/copilot/store";
import { server } from "@/test/msw/server";

function reset() {
  useCopilotStore.setState({
    isOpen: true,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
  });
}

function sse(body: string): HttpResponse<string> {
  return new HttpResponse(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("CopilotPanel", () => {
  beforeEach(reset);

  it("sends a message and renders streamed assistant content", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sse('event: text_delta\ndata: {"text":"hello"}\n\n' + "event: done\ndata: {}\n\n"),
      ),
    );
    render(<CopilotPanel />);
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByPlaceholderText("問 Copilot…"), "hi");
    await act(async () => {
      await user.click(screen.getByLabelText("Send"));
    });

    // Assert
    await waitFor(() => {
      expect(screen.getByText("hi")).toBeInTheDocument();
      expect(screen.getByText("hello")).toBeInTheDocument();
    });
  });

  it("shows retry chip on backend error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sse(
          'event: error\ndata: {"code":"no_api_key","message":"沒設 key"}\n\n' +
            "event: done\ndata: {}\n\n",
        ),
      ),
    );
    render(<CopilotPanel />);
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByPlaceholderText("問 Copilot…"), "hi");
    await act(async () => {
      await user.click(screen.getByLabelText("Send"));
    });

    // Assert
    await waitFor(() => {
      expect(screen.getByText("沒設 key")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /重試/ })).toBeInTheDocument();
    });
  });

  it("hides quick-buttons when no pageContext", () => {
    render(<CopilotPanel />);
    expect(screen.queryByText(/解釋這幾筆 log/)).toBeNull();
  });

  it("shows quick-buttons when analyzer pageContext is set with logs", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["log a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<CopilotPanel />);
    expect(screen.getByText(/解釋這幾筆 log/)).toBeInTheDocument();
  });
});
