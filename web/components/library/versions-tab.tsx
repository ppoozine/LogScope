"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useParseRulesByLogType, usePromoteParseRule } from "@/lib/api/queries/parse-rules";
import { cn } from "@/lib/utils";

type Props = { logTypeId: string };

export function VersionsTab({ logTypeId }: Props) {
  const query = useParseRulesByLogType(logTypeId);
  const promote = usePromoteParseRule();
  const [confirming, setConfirming] = useState<string | null>(null);

  if (query.isLoading) return <p className="p-6 text-sm text-muted-foreground">載入中…</p>;
  if (query.isError) return <p className="p-6 text-sm text-destructive">無法取得版本列表</p>;
  const rules = query.data ?? [];
  if (rules.length === 0) {
    return <p className="p-6 text-sm text-muted-foreground">尚無版本</p>;
  }

  return (
    <div className="flex flex-col gap-2 p-6">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="py-2">Version</th>
            <th className="py-2">Status</th>
            <th className="py-2">Created</th>
            <th className="py-2">Engine</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id} className={cn("border-t", r.status === "archived" && "opacity-60")}>
              <td className="py-2 font-mono">v{r.version}</td>
              <td className="py-2">
                <StatusBadge status={r.status} />
              </td>
              <td className="py-2 text-xs text-muted-foreground">{r.created_at}</td>
              <td className="py-2 text-xs">{r.engine_version}</td>
              <td className="py-2 text-right">
                {r.status === "draft" && (
                  <button
                    type="button"
                    className="rounded border px-2 py-0.5 text-xs hover:bg-muted"
                    onClick={() => setConfirming(r.id)}
                  >
                    Promote
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {confirming && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        >
          <div className="w-80 rounded-lg bg-card p-4 shadow-lg">
            <h3 className="text-sm font-semibold">Promote 確認</h3>
            <p className="mt-2 text-xs text-muted-foreground">
              這個版本將取代目前的 published rule，舊版會被 archive。確定？
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded border px-3 py-1 text-xs"
                onClick={() => setConfirming(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="rounded bg-purple-600 px-3 py-1 text-xs text-white"
                onClick={async () => {
                  try {
                    await promote.mutateAsync(confirming!);
                  } finally {
                    setConfirming(null);
                  }
                }}
              >
                確定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant: "default" | "secondary" | "outline" =
    status === "published" ? "default" : status === "archived" ? "secondary" : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}
