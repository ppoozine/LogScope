"use client";

import { useEffect, useRef } from "react";

import { useCopilotStore } from "@/lib/copilot/store";
import type { MatchHypothesis, ParseResult } from "@/lib/copilot/types";

type AnalyzerStateForCopilot = {
  vrl: string | null;
  vrlEngine: string | null;
  logs: string[];
  parseResults: ParseResult[];
  matchTopCandidate: MatchHypothesis | null;
  setVrl: (next: string) => void;
  getVrl: () => string;
};

/**
 * Push the current analyzer view state into the Copilot store as `pageContext`.
 *
 * Re-runs whenever any field changes. We use `JSON.stringify` keys for the
 * array/object fields so callers don't have to memoise — payloads are tiny
 * (logs cap at 20 lines, parse results match log count) so the cost is
 * negligible. A `latestRef` mirrors the live state so the effect closure can
 * dispatch the structured values without listing them as raw deps (which
 * would defeat the stringify-key strategy and re-fire on every parent
 * render).
 */
export function useAnalyzerCopilotContext(state: AnalyzerStateForCopilot): void {
  const setPageContext = useCopilotStore((s) => s.setPageContext);
  const registerEditor = useCopilotStore((s) => s.registerEditor);
  const unregisterEditor = useCopilotStore((s) => s.unregisterEditor);

  const latestRef = useRef(state);
  latestRef.current = state;

  const logsKey = JSON.stringify(state.logs);
  const parseKey = JSON.stringify(state.parseResults);
  const matchKey = JSON.stringify(state.matchTopCandidate);

  // biome-ignore lint/correctness/useExhaustiveDependencies: ref pattern + JSON.stringify keys intentionally bypass static deps; primitive `vrl`/`vrlEngine` listed so the effect re-fires when they change
  useEffect(() => {
    const s = latestRef.current;
    setPageContext({
      page: "analyzer",
      vrl: s.vrl,
      vrlEngine: s.vrlEngine,
      logs: s.logs,
      parseResults: s.parseResults,
      matchTopCandidate: s.matchTopCandidate,
    });
    return () => setPageContext(null);
  }, [setPageContext, state.vrl, state.vrlEngine, logsKey, parseKey, matchKey]);

  // Register the editor bridge so Copilot can push generated VRL back into
  // the editor. Uses separate effect with different cleanup semantics:
  // pageContext clears to null on unmount, bridge resets to the null sentinel.
  // biome-ignore lint/correctness/useExhaustiveDependencies: state.setVrl / state.getVrl listed as deps — callers stabilise with useCallback/useRef
  useEffect(() => {
    registerEditor({ setVrl: state.setVrl, getVrl: state.getVrl });
    return () => unregisterEditor();
  }, [registerEditor, unregisterEditor, state.setVrl, state.getVrl]);
}
