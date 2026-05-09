"use client";

import { useMemo, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";

import type { components } from "@/lib/api/types";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

type Props = {
  rules: ParseRuleRead[];
  initialLeftId: string;
  initialRightId: string;
  onClose: () => void;
};

export function VersionDiffModal({ rules, initialLeftId, initialRightId, onClose }: Props) {
  const [leftId, setLeftId] = useState(initialLeftId);
  const [rightId, setRightId] = useState(initialRightId);

  const left = useMemo(() => rules.find((r) => r.id === leftId), [rules, leftId]);
  const right = useMemo(() => rules.find((r) => r.id === rightId), [rules, rightId]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6"
    >
      <div className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-lg bg-card shadow-lg">
        <header className="flex items-center justify-between border-b p-3">
          <h3 className="text-sm font-semibold">版本比對</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-2 py-0.5 text-xs"
            aria-label="close"
          >
            關閉
          </button>
        </header>
        <div className="flex gap-3 border-b p-3 text-xs">
          <Selector label="Left" value={leftId} onChange={setLeftId} rules={rules} />
          <Selector label="Right" value={rightId} onChange={setRightId} rules={rules} />
        </div>
        <div className="overflow-auto">
          <ReactDiffViewer
            oldValue={left?.vrl_code ?? ""}
            newValue={right?.vrl_code ?? ""}
            splitView
            useDarkTheme={false}
          />
        </div>
      </div>
    </div>
  );
}

function Selector({
  label,
  value,
  onChange,
  rules,
}: {
  label: string;
  value: string;
  onChange: (id: string) => void;
  rules: ParseRuleRead[];
}) {
  return (
    <label className="flex items-center gap-1">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border bg-background px-2 py-0.5"
      >
        {rules.map((r) => (
          <option key={r.id} value={r.id}>
            v{r.version} ({r.status})
          </option>
        ))}
      </select>
    </label>
  );
}
