"use client";

import type { EditorView } from "@codemirror/view";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDebounce } from "use-debounce";

import type { InlineProviders } from "@/components/analyzer/cm6-inline";
import { DiffPane } from "@/components/analyzer/diff-pane";
import { EditorPane } from "@/components/analyzer/editor-pane";
import { LogPane } from "@/components/analyzer/log-pane";
import { MatchBar } from "@/components/analyzer/match-bar";
import { ResultPane } from "@/components/analyzer/result-pane";
import { SaveSampleDialog } from "@/components/analyzer/save-sample-dialog";
import { SnippetsBar } from "@/components/analyzer/snippets-bar";
import type { CheckCaller } from "@/components/analyzer/vrl-lint";
import { setVrlFixDispatcher } from "@/components/analyzer/vrl-lint";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api/client";
import { useMatch, useParse } from "@/lib/api/queries/analyzer";
import type { components } from "@/lib/api/types";
import { useAnalyzerCopilotContext } from "@/lib/copilot/hooks/use-analyzer-context";
import { useInlineVrl } from "@/lib/copilot/hooks/use-inline-vrl";
import type { InlineVrlRequest } from "@/lib/copilot/types";
import { loadAnalyzerState, saveAnalyzerState } from "@/lib/storage/analyzer-state";
import { formatVrlSource } from "@/lib/vrl/format";

type EngineVersion = "0.25" | "0.32";
type CheckResponse = components["schemas"]["CheckResponse"];
type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];
type MatchCandidate = components["schemas"]["MatchCandidate"];
type ParseResponse = components["schemas"]["ParseResponse"];
type SampleLabel = "normal" | "edge_case" | "error";

type Preload = {
  log_type_id: string;
  vrl_code: string | null;
  engine_version: EngineVersion;
  sample_raw_log: string | null;
  fields: FieldSchemaRead[];
};

type Props = { preload: Preload | null; noKey: boolean };

export function AnalyzerView({ preload, noKey }: Props) {
  const [vrl, setVrl] = useState(preload?.vrl_code ?? "");
  const [logs, setLogs] = useState(preload?.sample_raw_log ?? "");
  const [engineVersion, setEngineVersion] = useState<EngineVersion>(
    preload?.engine_version ?? "0.32",
  );
  const [sampleDialogOpen, setSampleDialogOpen] = useState(false);
  const [diffMode, setDiffMode] = useState(false);
  const [v25Result, setV25Result] = useState<ParseResponse | null>(null);
  const [v32Result, setV32Result] = useState<ParseResponse | null>(null);
  const [diffPending, setDiffPending] = useState(false);

  const logTypeId = preload?.log_type_id ?? null;
  const fields = preload?.fields ?? [];

  const parse = useParse();
  const match = useMatch();

  // Hydrate from localStorage on mount, unless preload supplied data
  useEffect(() => {
    if (preload) return;
    const stored = loadAnalyzerState();
    if (stored) {
      setVrl(stored.vrl);
      setLogs(stored.logs);
      setEngineVersion(stored.engineVersion);
    }
  }, [preload]);

  // Persist on every change
  useEffect(() => {
    saveAnalyzerState({ vrl, logs, engineVersion });
  }, [vrl, logs, engineVersion]);

  // Debounce inputs for parse + match
  const [debouncedVrl] = useDebounce(vrl, 400);
  const [debouncedLogs] = useDebounce(logs, 400);
  const [debouncedFirstLog] = useDebounce(logs.split("\n")[0] ?? "", 1000);

  const parseMutate = parse.mutate;
  // Auto parse
  useEffect(() => {
    if (!debouncedVrl.trim() || !debouncedLogs.trim()) return;
    parseMutate({
      vrl_code: debouncedVrl,
      logs: debouncedLogs.split("\n"),
      engine_version: engineVersion,
      log_type_id: logTypeId ?? undefined,
    });
  }, [debouncedVrl, debouncedLogs, engineVersion, parseMutate, logTypeId]);

  const matchMutate = match.mutate;
  // Auto match
  useEffect(() => {
    if (noKey) return;
    if (!debouncedFirstLog.trim()) return;
    matchMutate({ raw_log: debouncedFirstLog, top_k: 3 });
  }, [debouncedFirstLog, noKey, matchMutate]);

  // Push analyzer state into the Copilot store so the chat panel can read it.
  // Hook clears the store on unmount (e.g. when navigating away from /analyzer).
  const parseData = parse.data ?? null;
  const matchData = match.data ?? null;
  const topCandidate = matchData?.candidates?.[0] ?? null;

  // Stable callbacks for the editor bridge. vrlRef mirrors the latest vrl
  // value so getVrlForCopilot always returns the current value without
  // needing to re-create the callback (which would re-trigger hook deps).
  const vrlRef = useRef(vrl);
  vrlRef.current = vrl;
  const getVrlForCopilot = useCallback(() => vrlRef.current, []);
  const setVrlForCopilot = useCallback((next: string) => setVrl(next), []);

  useAnalyzerCopilotContext({
    vrl: vrl ? vrl : null,
    vrlEngine: parseData?.engine ?? null,
    logs: logs ? logs.split("\n").filter((l) => l.length > 0) : [],
    parseResults:
      parseData?.results?.map((r) => ({
        index: r.index,
        status: r.status === "success" ? "ok" : "error",
        message: r.error || undefined,
      })) ?? [],
    matchTopCandidate: topCandidate
      ? {
          vendorSlug: topCandidate.vendor_slug,
          productSlug: topCandidate.product_slug,
          logTypeName: topCandidate.log_type_name,
          confidence: topCandidate.confidence,
        }
      : null,
    setVrl: setVrlForCopilot,
    getVrl: getVrlForCopilot,
  });

  const [inlineView, setInlineView] = useState<EditorView | null>(null);
  const { send: sendInline } = useInlineVrl(inlineView);
  const sendInlineRef = useRef(sendInline);
  sendInlineRef.current = sendInline;

  const inlineProviders = useMemo<InlineProviders>(
    () => ({
      getEngineVersion: () => engineVersion,
      getLogs: () => (logs ? logs.split("\n").filter((l) => l.length > 0) : []),
      sendInlineRequest: (req: InlineVrlRequest) => {
        void sendInlineRef.current(req);
      },
    }),
    [engineVersion, logs],
  );

  // Register the VRL compile-error fix dispatcher so the linter's
  // "Fix with Copilot" action can route into the inline VRL flow.
  // Effect deps: only engineVersion — sendInlineRef is a ref (always stable),
  // and fix does not need sample logs so we avoid re-registering on every
  // logs change.
  useEffect(() => {
    setVrlFixDispatcher((view, diag) => {
      const line = view.state.doc.lineAt(diag.from);
      void sendInlineRef.current({
        instruction: "Fix this VRL compile error",
        skill: "vrl_fix",
        mode: "replace",
        current_vrl: view.state.doc.toString(),
        selection_start: line.from,
        selection_end: line.to,
        vrl_engine: engineVersion,
        logs: [],
        compile_error: diag.message,
      });
    });
    return () => setVrlFixDispatcher(null);
  }, [engineVersion]);

  // Fire-and-forget /check call. We swallow network errors here (instead of
  // letting React Query bubble them through the dev overlay) — the linter
  // doesn't need the failure surfaced; an offline/blocked /check just means
  // no inline diagnostics this tick.
  const handleCheck = useCallback<CheckCaller>(
    async (vrlSource) => {
      try {
        const r = await apiFetch<{ data: CheckResponse }>("/api/v1/analyzer/check", {
          method: "POST",
          body: { vrl_code: vrlSource, engine_version: engineVersion },
        });
        return r.data;
      } catch {
        return { kind: "ok", engine: engineVersion, compile_error: null };
      }
    },
    [engineVersion],
  );

  const handleManualParse = useCallback(() => {
    if (!vrl.trim() || !logs.trim()) return;
    parseMutate({
      vrl_code: vrl,
      logs: logs.split("\n"),
      engine_version: engineVersion,
      log_type_id: logTypeId ?? undefined,
    });
  }, [vrl, logs, engineVersion, parseMutate, logTypeId]);

  const handleRunBoth = useCallback(async () => {
    if (!vrl.trim() || !logs.trim()) return;
    setDiffMode(true);
    setDiffPending(true);
    setV25Result(null);
    setV32Result(null);
    const logLines = logs.split("\n");
    try {
      const [r25, r32] = await Promise.all([
        apiFetch<{ data: ParseResponse }>("/api/v1/analyzer/parse", {
          method: "POST",
          body: {
            vrl_code: vrl,
            logs: logLines,
            engine_version: "0.25",
            log_type_id: logTypeId ?? undefined,
          },
        }),
        apiFetch<{ data: ParseResponse }>("/api/v1/analyzer/parse", {
          method: "POST",
          body: {
            vrl_code: vrl,
            logs: logLines,
            engine_version: "0.32",
            log_type_id: logTypeId ?? undefined,
          },
        }),
      ]);
      setV25Result(r25.data);
      setV32Result(r32.data);
    } finally {
      setDiffPending(false);
    }
  }, [vrl, logs, logTypeId]);

  const handleFormat = useCallback(() => {
    setVrl((prev) => formatVrlSource(prev));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "Enter") {
        e.preventDefault();
        if (e.shiftKey) {
          handleRunBoth();
        } else {
          handleManualParse();
        }
      } else if (e.shiftKey && (e.key === "F" || e.key === "f")) {
        e.preventDefault();
        handleFormat();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleManualParse, handleRunBoth, handleFormat]);

  const handleApplyCandidate = (c: MatchCandidate) => {
    window.location.href = `/analyzer?log_type_id=${c.log_type_id}`;
  };

  const handleManualMatch = () => {
    const first = logs.split("\n")[0] ?? "";
    if (!first.trim()) return;
    matchMutate({ raw_log: first, top_k: 3 });
  };

  const handleSaveBackToLibrary = async () => {
    if (!logTypeId) return;
    try {
      await apiFetch(`/api/v1/library/log_types/${logTypeId}/parse_rules`, {
        method: "POST",
        body: {
          vrl_code: vrl,
          engine_version: engineVersion,
          notes: "via Analyzer",
        },
      });
      window.alert("已建立新的 draft parse rule");
    } catch (err) {
      window.alert(err instanceof ApiError ? `存回失敗：${err.message}` : "存回失敗");
    }
  };

  const handleSaveSample = async (args: { label: SampleLabel; description: string }) => {
    if (!logTypeId) return;
    try {
      const firstLine = logs.split("\n")[0] ?? "";
      await apiFetch(`/api/v1/library/log_types/${logTypeId}/samples`, {
        method: "POST",
        body: {
          raw_log: firstLine,
          label: args.label,
          description: args.description || null,
        },
      });
      setSampleDialogOpen(false);
      window.alert("sample 已存入");
    } catch (err) {
      window.alert(err instanceof ApiError ? `存入失敗：${err.message}` : "存入失敗");
    }
  };

  const parseStatus = parseData?.summary
    ? {
        ok: parseData.summary.error === 0,
        errors: parseData.summary.error,
        total: parseData.summary.total,
      }
    : undefined;

  return (
    <div className="flex flex-col">
      <MatchBar
        candidates={match.data?.candidates ?? []}
        isLoading={match.isPending}
        onApply={handleApplyCandidate}
        onMatch={handleManualMatch}
        noKey={noKey}
      />
      <SnippetsBar
        current={{ vrl, logs, engineVersion }}
        onLoad={(state) => {
          setVrl(state.vrl);
          setLogs(state.logs);
          setEngineVersion(state.engineVersion);
        }}
      />
      <div className="flex items-center gap-2 border-b bg-muted/40 px-6 py-2">
        <Button
          size="sm"
          onClick={handleManualParse}
          title="Parse (⌘/Ctrl + Enter)"
          className="h-7 text-xs"
        >
          Parse
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={handleRunBoth}
          disabled={diffPending}
          title="Run on both 0.25 and 0.32 (⇧⌘/Ctrl + Enter)"
          className="h-7 text-xs"
        >
          {diffPending ? "Running…" : "Run both"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={handleFormat}
          title="Format VRL (⇧⌘/Ctrl + F)"
          className="h-7 text-xs"
        >
          Format
        </Button>
        <span className="ml-auto text-[11px] text-muted-foreground">
          ⌘+Enter parse · ⇧⌘+F format
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4 px-6 pt-4 lg:grid-cols-2">
        <EditorPane
          vrl={vrl}
          onVrlChange={setVrl}
          engineVersion={engineVersion}
          onEngineChange={setEngineVersion}
          parseStatus={parseStatus}
          onCheck={handleCheck}
          onViewReady={setInlineView}
          inlineEnabled
          inlineProviders={inlineProviders}
        />
        <LogPane logs={logs} onLogsChange={setLogs} />
      </div>
      <div className="px-6 pb-6 pt-4">
        {diffMode ? (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-end">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setDiffMode(false);
                  setV25Result(null);
                  setV32Result(null);
                }}
                className="h-7 text-xs"
              >
                ← 回 single-engine 結果
              </Button>
            </div>
            <DiffPane v25={v25Result} v32={v32Result} />
          </div>
        ) : (
          <ResultPane
            parseResult={parseData ?? null}
            fields={fields}
            hasLogTypeContext={!!logTypeId}
            onSaveBackToLibrary={logTypeId ? handleSaveBackToLibrary : undefined}
            onSaveAsSample={logTypeId ? () => setSampleDialogOpen(true) : undefined}
            currentVrl={vrl}
            vrlEngine={engineVersion}
            logs={logs ? logs.split("\n").filter((l) => l.length > 0) : []}
          />
        )}
      </div>
      <SaveSampleDialog
        open={sampleDialogOpen}
        onOpenChange={setSampleDialogOpen}
        onSubmit={handleSaveSample}
        rawLog={logs}
      />
    </div>
  );
}
