"use client";

import { useEffect, useState } from "react";
import { useDebounce } from "use-debounce";

import { EditorPane } from "@/components/analyzer/editor-pane";
import { LogPane } from "@/components/analyzer/log-pane";
import { MatchBar } from "@/components/analyzer/match-bar";
import { ResultPane } from "@/components/analyzer/result-pane";
import { SaveSampleDialog } from "@/components/analyzer/save-sample-dialog";
import { ApiError, apiFetch } from "@/lib/api/client";
import { useMatch, useParse } from "@/lib/api/queries/analyzer";
import type { components } from "@/lib/api/types";
import { loadAnalyzerState, saveAnalyzerState } from "@/lib/storage/analyzer-state";

type EngineVersion = "0.25" | "0.32";
type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];
type MatchCandidate = components["schemas"]["MatchCandidate"];
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
    });
  }, [debouncedVrl, debouncedLogs, engineVersion, parseMutate]);

  const matchMutate = match.mutate;
  // Auto match
  useEffect(() => {
    if (noKey) return;
    if (!debouncedFirstLog.trim()) return;
    matchMutate({ raw_log: debouncedFirstLog, top_k: 3 });
  }, [debouncedFirstLog, noKey, matchMutate]);

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

  const parseResult = parse.data ?? null;
  const parseStatus = parseResult?.summary
    ? {
        ok: parseResult.summary.error === 0,
        errors: parseResult.summary.error,
        total: parseResult.summary.total,
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
      <div className="grid grid-cols-1 gap-4 px-6 pt-4 lg:grid-cols-2">
        <EditorPane
          vrl={vrl}
          onVrlChange={setVrl}
          engineVersion={engineVersion}
          onEngineChange={setEngineVersion}
          parseStatus={parseStatus}
        />
        <LogPane logs={logs} onLogsChange={setLogs} />
      </div>
      <div className="px-6 pb-6 pt-4">
        <ResultPane
          parseResult={parseResult}
          fields={fields}
          hasLogTypeContext={!!logTypeId}
          onSaveBackToLibrary={logTypeId ? handleSaveBackToLibrary : undefined}
          onSaveAsSample={logTypeId ? () => setSampleDialogOpen(true) : undefined}
        />
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
