"use client";

import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type MatchCandidate = components["schemas"]["MatchCandidate"];

type Props = {
  candidates: MatchCandidate[];
  isLoading: boolean;
  onApply: (candidate: MatchCandidate) => void;
  onMatch: () => void;
  noKey?: boolean;
};

export function MatchBar({ candidates, isLoading, onApply, onMatch, noKey }: Props) {
  return (
    <div className="flex items-center gap-2 border-b bg-zinc-50 px-3 py-2">
      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Library 比對
      </span>
      <MatchBarBody candidates={candidates} isLoading={isLoading} onApply={onApply} noKey={noKey} />
      <Button
        size="sm"
        variant="ghost"
        onClick={onMatch}
        className="ml-auto h-7 text-xs"
        disabled={isLoading || noKey}
      >
        Match
      </Button>
    </div>
  );
}

function MatchBarBody({
  candidates,
  isLoading,
  onApply,
  noKey,
}: {
  candidates: MatchCandidate[];
  isLoading: boolean;
  onApply: (candidate: MatchCandidate) => void;
  noKey: boolean | undefined;
}) {
  if (noKey) {
    return (
      <span className="text-xs text-muted-foreground">無法比對（未設 ANTHROPIC_API_KEY）</span>
    );
  }
  if (isLoading) {
    return <span className="text-xs text-muted-foreground">辨識中…</span>;
  }
  if (candidates.length === 0) {
    return <span className="text-xs text-muted-foreground">尚無候選</span>;
  }
  return (
    <ul className="flex flex-1 items-center gap-2 overflow-x-auto">
      {candidates.map((c) => (
        <li
          key={c.log_type_id}
          className="flex items-center gap-2 rounded-md border bg-white px-2 py-1 text-xs"
        >
          <span className="font-medium text-purple-700">
            {c.vendor_slug} · {c.product_slug}
          </span>
          <span className="text-muted-foreground">{c.log_type_name}</span>
          <span
            className={cn(
              "font-semibold",
              c.confidence >= 0.7 ? "text-emerald-700" : "text-muted-foreground",
            )}
            title={c.reason}
          >
            {Math.round(c.confidence * 100)}%
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onApply(c)}
            className="h-6 text-[11px]"
          >
            套用
          </Button>
        </li>
      ))}
    </ul>
  );
}
