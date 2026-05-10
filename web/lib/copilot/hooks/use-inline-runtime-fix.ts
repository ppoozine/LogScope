import { useCallback, useSyncExternalStore } from "react";

import { streamInlineVrl } from "@/lib/copilot/inline-vrl-client";
import { useCopilotStore } from "@/lib/copilot/store";

type RuntimeFixState =
  | { kind: "idle" }
  | { kind: "streaming"; abort: AbortController; chipId: string }
  | { kind: "error"; message: string; chipId: string };

// Module-level singleton: one streaming session at a time, shared across all
// mounted instances of this hook. Multiple chip components read the same state
// via useSyncExternalStore (the React-blessed API for subscribing to external
// stores; handles StrictMode + concurrent rendering correctly).
let _state: RuntimeFixState = { kind: "idle" };
const _listeners = new Set<() => void>();

function _subscribe(l: () => void): () => void {
  _listeners.add(l);
  return () => {
    _listeners.delete(l);
    if (_listeners.size === 0 && _state.kind === "streaming") {
      _state.abort.abort();
      _state = { kind: "idle" };
    }
  };
}

function _getSnapshot(): RuntimeFixState {
  return _state;
}

function _setState(next: RuntimeFixState): void {
  _state = next;
  for (const l of _listeners) l();
}

export type RuntimeFixArgs = {
  chipId: string;
  currentVrl: string;
  failingLog: string;
  runtimeError: string;
  vrlEngine: "0.25" | "0.32";
  logs: string[];
};

export function useInlineRuntimeFix() {
  const state = useSyncExternalStore(_subscribe, _getSnapshot, _getSnapshot);

  // Read requestInsert at start-time, not via subscription, to avoid extra
  // re-renders when unrelated copilot store fields change.
  const start = useCallback(async (args: RuntimeFixArgs) => {
    const requestInsert = useCopilotStore.getState().requestInsert;

    if (_state.kind === "streaming") {
      _state.abort.abort();
    }

    if (!args.currentVrl.trim()) {
      _setState({ kind: "error", message: "VRL 為空、無法修復", chipId: args.chipId });
      return;
    }

    const controller = new AbortController();
    _setState({ kind: "streaming", abort: controller, chipId: args.chipId });

    let buffer = "";
    try {
      for await (const ev of streamInlineVrl(
        {
          instruction: "Fix this runtime parse error",
          skill: "vrl_runtime_fix",
          mode: "replace",
          current_vrl: args.currentVrl,
          selection_start: 0,
          selection_end: args.currentVrl.length,
          vrl_engine: args.vrlEngine,
          logs: args.logs,
          failing_log: args.failingLog,
          runtime_error: args.runtimeError,
        },
        controller.signal,
      )) {
        if (_state.kind !== "streaming" || _state.chipId !== args.chipId) {
          // Superseded by another start() — drop further events.
          return;
        }
        if (ev.type === "text_delta") {
          buffer += ev.text;
        } else if (ev.type === "error") {
          _setState({ kind: "error", message: ev.message, chipId: args.chipId });
          return;
        } else if (ev.type === "done") {
          if (buffer.trim()) {
            requestInsert(buffer, `runtime-fix-${args.chipId}-${Date.now()}`);
            _setState({ kind: "idle" });
          } else {
            _setState({ kind: "error", message: "回應為空", chipId: args.chipId });
          }
          return;
        }
      }
    } catch (err) {
      if (_state.kind === "streaming" && _state.chipId !== args.chipId) {
        return; // superseded
      }
      if ((err as Error).name === "AbortError") {
        _setState({ kind: "idle" });
        return;
      }
      _setState({ kind: "error", message: "連線中斷", chipId: args.chipId });
    }
  }, []);

  const cancel = useCallback(() => {
    if (_state.kind === "streaming") {
      _state.abort.abort();
      _setState({ kind: "idle" });
    }
  }, []);

  return { state, start, cancel };
}
