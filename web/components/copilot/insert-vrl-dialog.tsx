"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCopilotStore } from "@/lib/copilot/store";

export function InsertVrlDialog() {
  const pendingInsert = useCopilotStore((s) => s.pendingInsert);
  const editorBridge = useCopilotStore((s) => s.editorBridge);
  const confirmInsert = useCopilotStore((s) => s.confirmInsert);
  const cancelInsert = useCopilotStore((s) => s.cancelInsert);

  if (!pendingInsert) return null;
  const current = editorBridge.getVrl();
  const proposed = pendingInsert.proposedVrl;

  return (
    <Dialog open onOpenChange={(open) => !open && cancelInsert()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>套用 Copilot 提議的 VRL？</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <DiffPanel label="目前 VRL" content={current} />
          <DiffPanel label="Copilot 提議" content={proposed} highlight />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={cancelInsert}>取消</Button>
          <Button onClick={confirmInsert}>套用 Insert</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DiffPanel({
  label,
  content,
  highlight,
}: {
  label: string;
  content: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <pre
        className={`max-h-80 overflow-auto rounded border p-2 font-mono text-[11px] ${
          highlight ? "bg-emerald-50" : "bg-muted/40"
        }`}
      >
        {content}
      </pre>
    </div>
  );
}
