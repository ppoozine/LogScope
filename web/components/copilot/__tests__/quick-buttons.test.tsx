import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QuickButtons } from "@/components/copilot/quick-buttons";
import { useCopilotStore } from "@/lib/copilot/store";

// Mock useStreamingChat to capture send calls
vi.mock("@/lib/copilot/hooks/use-streaming-chat", () => ({
  useStreamingChat: vi.fn(),
}));

// Mock apiFetch (used by 比對 Library handler)
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

import { apiFetch } from "@/lib/api/client";
import { useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";

describe("<QuickButtons>", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
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

describe("<QuickButtons> 比對 Library", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    useCopilotStore.setState({ isStreaming: false });
    vi.mocked(useStreamingChat).mockReturnValue({ send: vi.fn(), abort: vi.fn() });
  });

  it("renders 比對 Library on analyzer page with logs", () => {
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["raw log line"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    expect(screen.getByRole("button", { name: /比對 Library/ })).toBeInTheDocument();
  });

  it("clicking 比對 Library calls /analyzer/match then sends with skill=log_explain", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      data: {
        candidates: [
          {
            vendor_slug: "paloalto",
            product_slug: "pan-os",
            log_type_id: "lt-1",
            log_type_name: "traffic",
            confidence: 0.94,
            reason: "Looks like syslog with PAN-OS CSV body",
          },
          {
            vendor_slug: "cisco",
            product_slug: "asa",
            log_type_id: "lt-2",
            log_type_name: "syslog",
            confidence: 0.42,
            reason: "Generic syslog only",
          },
        ],
      },
    });
    const sendSpy = vi.fn();
    vi.mocked(useStreamingChat).mockReturnValue({ send: sendSpy, abort: vi.fn() });
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["raw log line"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });

    render(<QuickButtons />);
    fireEvent.click(screen.getByRole("button", { name: /比對 Library/ }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const fetchCall = vi.mocked(apiFetch).mock.calls[0];
    expect(fetchCall[0]).toBe("/api/v1/analyzer/match");
    expect(fetchCall[1]).toEqual({
      method: "POST",
      body: { raw_log: "raw log line", top_k: 3 },
    });

    await waitFor(() => expect(sendSpy).toHaveBeenCalled());
    const [text, options] = sendSpy.mock.calls[0];
    expect(text).toContain("Candidate 1");
    expect(text).toContain("paloalto/pan-os");
    expect(text).toContain("traffic");
    expect(text).toContain("0.94");
    expect(text).toContain("Looks like syslog");
    expect(text).toContain("Candidate 2");
    expect(options).toEqual({ skill: "log_explain" });
  });

  it("button shows loading state while match endpoint is in flight", async () => {
    let resolveFetch!: (v: unknown) => void;
    vi.mocked(apiFetch).mockImplementationOnce(
      () =>
        new Promise((res) => {
          resolveFetch = res;
        }),
    );
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: null,
        vrlEngine: null,
        logs: ["raw"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });
    render(<QuickButtons />);
    const btn = screen.getByRole("button", { name: /比對 Library/ });
    fireEvent.click(btn);
    // After click but before resolve: button shows '比對中…'
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /比對中/ })).toBeDisabled();
    });
    // Resolve and let promise chain finish
    resolveFetch({ data: { candidates: [] } });
  });
});
