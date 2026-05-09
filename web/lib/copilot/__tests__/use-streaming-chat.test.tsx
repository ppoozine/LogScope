import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { toBackendPageContext, useStreamingChat } from "@/lib/copilot/hooks/use-streaming-chat";
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

  it("send accepts an explicit skill option and updates lastSkill", async () => {
    // Arrange
    resetStore();
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sseResponse(['event: text_delta\ndata: {"text":"ok"}\n\n', "event: done\ndata: {}\n\n"]),
      ),
    );
    const { result } = renderHook(() => useStreamingChat());
    useCopilotStore.setState({
      pageContext: {
        page: "analyzer",
        vrl: "x",
        vrlEngine: null,
        logs: ["a"],
        parseResults: [],
        matchTopCandidate: null,
      },
    });

    // Act
    await act(async () => {
      await result.current.send("生成 VRL", { skill: "vrl_generate" });
    });

    // Assert
    await waitFor(() => {
      expect(useCopilotStore.getState().isStreaming).toBe(false);
    });
    expect(useCopilotStore.getState().lastSkill).toBe("vrl_generate");
  });

  it("send falls back to log_explain when no explicit skill given on analyzer page", async () => {
    // Arrange
    resetStore();
    server.use(
      http.post("/api/v1/copilot/chat", () =>
        sseResponse(['event: text_delta\ndata: {"text":"ok"}\n\n', "event: done\ndata: {}\n\n"]),
      ),
    );
    const { result } = renderHook(() => useStreamingChat());
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

    // Act
    await act(async () => {
      await result.current.send("hi");
    });

    // Assert
    await waitFor(() => {
      expect(useCopilotStore.getState().isStreaming).toBe(false);
    });
    expect(useCopilotStore.getState().lastSkill).toBe("log_explain");
  });
});

describe("toBackendPageContext", () => {
  it("converts analyzer ctx to snake_case backend shape", () => {
    const r = toBackendPageContext({
      page: "analyzer",
      vrl: ". = .",
      vrlEngine: "0.32",
      logs: ["a"],
      parseResults: [{ index: 0, status: "ok" }],
      matchTopCandidate: {
        vendorSlug: "v",
        productSlug: "p",
        logTypeName: "t",
        confidence: 0.9,
      },
    });
    expect(r).toEqual({
      page: "analyzer",
      vrl: ". = .",
      vrl_engine: "0.32",
      logs: ["a"],
      parse_results: [{ index: 0, status: "ok" }],
      match_top_candidate: {
        vendor_slug: "v",
        product_slug: "p",
        log_type_name: "t",
        confidence: 0.9,
      },
    });
  });

  it("converts library_overview ctx", () => {
    const r = toBackendPageContext({
      page: "library_overview",
      filters: { status: "published", q: undefined },
      vendorCount: 5,
      productCount: 12,
      productsMissingParseRule: ["v/p"],
    });
    expect(r).toMatchObject({
      page: "library_overview",
      vendor_count: 5,
      product_count: 12,
      products_missing_parse_rule: ["v/p"],
    });
  });

  it("converts library_product ctx with active log type", () => {
    const r = toBackendPageContext({
      page: "library_product",
      vendorSlug: "v",
      productSlug: "p",
      productStatus: "active",
      activeLogType: {
        name: "traffic",
        fields: [{ name: "src_ip", type: "string", required: true }],
        samplesCount: 5,
        parseRuleHead: ". = parse_syslog!(.message)",
      },
    });
    expect(r).toMatchObject({
      page: "library_product",
      vendor_slug: "v",
      product_slug: "p",
      product_status: "active",
      active_log_type: {
        name: "traffic",
        samples_count: 5,
        parse_rule_head: ". = parse_syslog!(.message)",
      },
    });
  });

  it("converts library_product ctx with null active log type", () => {
    const r = toBackendPageContext({
      page: "library_product",
      vendorSlug: "v",
      productSlug: "p",
      productStatus: "active",
      activeLogType: null,
    });
    expect(r).toMatchObject({
      page: "library_product",
      active_log_type: null,
    });
  });

  it("converts library_versions ctx with diff", () => {
    const r = toBackendPageContext({
      page: "library_versions",
      vendorSlug: "v",
      productSlug: "p",
      logTypeName: "t",
      diff: {
        baseVersion: "v3",
        headVersion: "v4",
        baseVrl: "old",
        headVrl: "new",
      },
    });
    expect(r).toMatchObject({
      page: "library_versions",
      vendor_slug: "v",
      product_slug: "p",
      log_type_name: "t",
      diff: {
        base_version: "v3",
        head_version: "v4",
        base_vrl: "old",
        head_vrl: "new",
      },
    });
  });

  it("converts library_versions ctx with no diff", () => {
    const r = toBackendPageContext({
      page: "library_versions",
      vendorSlug: "v",
      productSlug: "p",
      logTypeName: "t",
      diff: null,
    });
    expect(r).toMatchObject({
      page: "library_versions",
      diff: null,
    });
  });
});
