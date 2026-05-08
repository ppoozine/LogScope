import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/types";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

export function VrlDisplay({ rule }: { rule: ParseRuleRead | null | undefined }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <header className="mb-3 flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">VRL Parse Rule</h3>
          {rule && (
            <span className="text-xs text-muted-foreground">
              v{rule.version} · engine {rule.engine_version} · {rule.status}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled title="Coming in spec C">
            載入 Analyzer
          </Button>
          <Button size="sm" variant="outline" disabled title="Coming in spec C">
            編輯
          </Button>
        </div>
      </header>
      {rule ? (
        <pre className="overflow-x-auto rounded-md bg-zinc-900 p-3 text-xs text-zinc-100">
          <code>{rule.vrl_code}</code>
        </pre>
      ) : (
        <p className="text-xs text-muted-foreground">尚未建立 parse rule</p>
      )}
    </section>
  );
}
