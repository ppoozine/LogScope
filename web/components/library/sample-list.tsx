import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type SampleLogRead = components["schemas"]["SampleLogRead"];

const LABEL_COLOR: Record<string, string> = {
  normal: "bg-emerald-50 text-emerald-700",
  edge_case: "bg-amber-50 text-amber-700",
  error: "bg-red-50 text-red-700",
};

export function SampleList({ samples }: { samples: SampleLogRead[] }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">Sample logs（{samples.length}）</h3>
      {samples.length === 0 ? (
        <p className="text-xs text-muted-foreground">尚未加入 sample</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {samples.map((sample) => (
            <li key={sample.id} className="rounded border p-2">
              <div className="mb-1 flex items-center gap-2">
                <span
                  className={cn(
                    "rounded px-1.5 text-[10px] font-medium",
                    LABEL_COLOR[sample.label] ?? "bg-muted text-muted-foreground",
                  )}
                >
                  {sample.label}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled
                  title="Coming in spec C"
                  className="ml-auto h-6 text-xs"
                >
                  在 Analyzer 試打
                </Button>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words text-[11px] text-muted-foreground">
                {sample.raw_log}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
