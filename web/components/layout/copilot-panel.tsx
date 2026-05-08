"use client";

import { useCopilot } from "@/components/providers/copilot-context";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export function CopilotPanel() {
  const { isOpen, close } = useCopilot();

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && close()}>
      <SheetContent side="right" className="w-[380px] sm:max-w-[380px]">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="text-purple-600">✦</span>
            Copilot
          </SheetTitle>
        </SheetHeader>

        <div className="mt-6 flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-muted-foreground/30 p-10 text-center">
          <p className="text-sm font-medium text-foreground">即將於 spec D 開放</p>
          <p className="text-xs text-muted-foreground">
            VRL 生成、Log 解釋、Library 比對三技能會在這裡。
          </p>
        </div>

        <div className="mt-6">
          <input
            type="text"
            placeholder="問 Copilot…"
            disabled
            className="w-full rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground"
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
