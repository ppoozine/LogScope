import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCopilotStore } from "@/lib/copilot/store";

beforeEach(() => {
  // reset store between tests
  useCopilotStore.setState({
    isOpen: false,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
  });
  sessionStorage.clear();
});

describe("useCopilotStore", () => {
  it("toggles isOpen", () => {
    const { toggle } = useCopilotStore.getState();
    expect(useCopilotStore.getState().isOpen).toBe(false);
    toggle();
    expect(useCopilotStore.getState().isOpen).toBe(true);
    toggle();
    expect(useCopilotStore.getState().isOpen).toBe(false);
  });

  it("appendUserMessage adds a user message with id", () => {
    useCopilotStore.getState().appendUserMessage("hello");
    const msgs = useCopilotStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].role).toBe("user");
    expect(msgs[0].content).toBe("hello");
    expect(msgs[0].id).toBeTruthy();
  });

  it("appendAssistantPlaceholder returns id and adds empty assistant", () => {
    const id = useCopilotStore.getState().appendAssistantPlaceholder();
    const msgs = useCopilotStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe(id);
    expect(msgs[0].role).toBe("assistant");
    expect(msgs[0].content).toBe("");
  });

  it("appendDelta appends text to the matching message", () => {
    const id = useCopilotStore.getState().appendAssistantPlaceholder();
    useCopilotStore.getState().appendDelta(id, "hello ");
    useCopilotStore.getState().appendDelta(id, "world");
    expect(useCopilotStore.getState().messages[0].content).toBe("hello world");
  });

  it("setMessageError sets error on matching message", () => {
    const id = useCopilotStore.getState().appendAssistantPlaceholder();
    useCopilotStore.getState().setMessageError(id, "boom");
    expect(useCopilotStore.getState().messages[0].error).toBe("boom");
  });

  it("clearMessages empties the array", () => {
    useCopilotStore.getState().appendUserMessage("a");
    useCopilotStore.getState().appendAssistantPlaceholder();
    useCopilotStore.getState().clearMessages();
    expect(useCopilotStore.getState().messages).toEqual([]);
  });

  it("appending beyond MAX_HISTORY shifts oldest", () => {
    // Default MAX_HISTORY = 20, so 21st message should evict oldest.
    for (let i = 0; i < 21; i++) {
      useCopilotStore.getState().appendUserMessage(`m${i}`);
    }
    const msgs = useCopilotStore.getState().messages;
    expect(msgs).toHaveLength(20);
    expect(msgs[0].content).toBe("m1"); // m0 evicted
    expect(msgs[19].content).toBe("m20");
  });

  it("setPageContext updates and clears", () => {
    useCopilotStore.getState().setPageContext({
      page: "analyzer",
      vrl: null,
      vrlEngine: null,
      logs: [],
      parseResults: [],
      matchTopCandidate: null,
    });
    expect(useCopilotStore.getState().pageContext?.page).toBe("analyzer");
    useCopilotStore.getState().setPageContext(null);
    expect(useCopilotStore.getState().pageContext).toBeNull();
  });
});

describe("editor bridge", () => {
  beforeEach(() =>
    useCopilotStore.setState({
      editorBridge: { setVrl: null, getVrl: () => "" },
      pendingInsert: null,
      lastSkill: null,
    }),
  );

  it("registerEditor stores callbacks", () => {
    const setVrl = vi.fn();
    const getVrl = vi.fn(() => "current");
    useCopilotStore.getState().registerEditor({ setVrl, getVrl });
    const b = useCopilotStore.getState().editorBridge;
    expect(b.setVrl).toBe(setVrl);
    expect(b.getVrl()).toBe("current");
  });

  it("unregisterEditor clears callbacks", () => {
    useCopilotStore.getState().registerEditor({ setVrl: vi.fn(), getVrl: () => "" });
    useCopilotStore.getState().unregisterEditor();
    expect(useCopilotStore.getState().editorBridge.setVrl).toBeNull();
  });

  it("requestInsert sets pendingInsert", () => {
    useCopilotStore.getState().requestInsert(". = .", "msg-1");
    expect(useCopilotStore.getState().pendingInsert).toEqual({
      proposedVrl: ". = .",
      messageId: "msg-1",
    });
  });

  it("confirmInsert calls editorBridge.setVrl and clears pending", () => {
    const setVrl = vi.fn();
    useCopilotStore.getState().registerEditor({ setVrl, getVrl: () => "old" });
    useCopilotStore.getState().requestInsert("new vrl", "msg-1");
    useCopilotStore.getState().confirmInsert();
    expect(setVrl).toHaveBeenCalledWith("new vrl");
    expect(useCopilotStore.getState().pendingInsert).toBeNull();
  });

  it("cancelInsert clears pending without calling setVrl", () => {
    const setVrl = vi.fn();
    useCopilotStore.getState().registerEditor({ setVrl, getVrl: () => "old" });
    useCopilotStore.getState().requestInsert("new", "msg-1");
    useCopilotStore.getState().cancelInsert();
    expect(setVrl).not.toHaveBeenCalled();
    expect(useCopilotStore.getState().pendingInsert).toBeNull();
  });

  it("confirmInsert no-ops when bridge is unregistered", () => {
    useCopilotStore.getState().requestInsert("x", "m");
    // bridge.setVrl is null
    expect(() => useCopilotStore.getState().confirmInsert()).not.toThrow();
    expect(useCopilotStore.getState().pendingInsert).toBeNull();
  });
});

describe("lastSkill", () => {
  it("setLastSkill updates state", () => {
    useCopilotStore.getState().setLastSkill("vrl_generate");
    expect(useCopilotStore.getState().lastSkill).toBe("vrl_generate");
  });
});

describe("finalizeMessage extracts vrlBlock", () => {
  beforeEach(() => useCopilotStore.setState({ messages: [] }));

  it("writes vrlBlock when assistant content has a fenced vrl", () => {
    const id = useCopilotStore.getState().appendAssistantPlaceholder();
    useCopilotStore
      .getState()
      .appendDelta(id, "前言\n```vrl\n. = parse_syslog!(.message)\n```\n結尾");
    useCopilotStore.getState().finalizeMessage(id);
    const msg = useCopilotStore.getState().messages.find((m) => m.id === id);
    expect(msg?.vrlBlock).toBe(". = parse_syslog!(.message)");
  });

  it("leaves vrlBlock undefined when no vrl block in content", () => {
    const id = useCopilotStore.getState().appendAssistantPlaceholder();
    useCopilotStore.getState().appendDelta(id, "純文字回應");
    useCopilotStore.getState().finalizeMessage(id);
    const msg = useCopilotStore.getState().messages.find((m) => m.id === id);
    expect(msg?.vrlBlock).toBeUndefined();
  });
});
