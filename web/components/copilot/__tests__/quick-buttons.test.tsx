import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QuickButtons } from "@/components/copilot/quick-buttons";
import { useCopilotStore } from "@/lib/copilot/store";

// Mock useStreamingChat to capture send calls
vi.mock("@/lib/copilot/hooks/use-streaming-chat", () => ({
  useStreamingChat: vi.fn(),
}));

import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";

describe("<QuickButtons>", () => {
  beforeEach(() => {
    useCopilotStore.setState({ isStreaming: false });
    vi.mocked(useStreamingChat).mockReturnValue({ send: vi.fn(), abort: vi.fn() });
  });

  it("renders 解釋 button on analyzer page with logs (D1 baseline)", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.getByRole("button", { name: /解釋這幾筆 log/i })).toBeInTheDocument();
  });

  it("renders 生成 VRL button on analyzer page with logs", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.getByRole("button", { name: /生成 VRL/i })).toBeInTheDocument();
  });

  it("clicking 生成 VRL sends with skill=vrl_generate", () => {
    const sendSpy = vi.fn();
    vi.mocked(useStreamingChat).mockReturnValue({ send: sendSpy, abort: vi.fn() });
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    fireEvent.click(screen.getByRole("button", { name: /生成 VRL/i }));
    expect(sendSpy).toHaveBeenCalledWith(expect.any(String), { skill: "vrl_generate" });
  });

  it("renders nothing when no pageContext", () => {
    useCopilotStore.setState({ pageContext: null });
    const { container } = render(<QuickButtons />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when logs is empty", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: [],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    const { container } = render(<QuickButtons />);
    expect(container.firstChild).toBeNull();
  });

  it("renders 最佳化 VRL when vrl is non-empty (analyzer with vrl + logs)", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: ". = .",
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.getByRole("button", { name: /最佳化 VRL/ })).toBeInTheDocument();
  });

  it("does not render 最佳化 VRL when vrl is null/empty", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.queryByRole("button", { name: /最佳化 VRL/ })).toBeNull();
  });

  it("clicking 最佳化 VRL sends with skill=vrl_optimize", () => {
    const sendSpy = vi.fn();
    vi.mocked(useStreamingChat).mockReturnValue({ send: sendSpy, abort: vi.fn() });
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: ". = .",
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    fireEvent.click(screen.getByRole("button", { name: /最佳化 VRL/ }));
    expect(sendSpy).toHaveBeenCalledWith(expect.any(String), { skill: "vrl_optimize" });
  });

  it("renders 找異常值 when logs present on analyzer page", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.getByRole("button", { name: /找異常值/ })).toBeInTheDocument();
  });

  it("clicking 找異常值 sends with skill=anomaly", () => {
    const sendSpy = vi.fn();
    vi.mocked(useStreamingChat).mockReturnValue({ send: sendSpy, abort: vi.fn() });
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    fireEvent.click(screen.getByRole("button", { name: /找異常值/ }));
    expect(sendSpy).toHaveBeenCalledWith(expect.any(String), { skill: "anomaly" });
  });
});
