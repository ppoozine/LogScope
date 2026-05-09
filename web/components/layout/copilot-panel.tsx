"use client";

import { ChatInput } from "@/components/copilot/chat-input";
import { ContextStrip } from "@/components/copilot/context-strip";
import { MessageList } from "@/components/copilot/message-list";
import { QuickButtons } from "@/components/copilot/quick-buttons";
import { useCopilot } from "@/components/providers/copilot-context";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";

export function CopilotPanel() {
  const { isOpen, close } = useCopilot();

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && close()}>
      <SheetContent side="right" className="flex w-[380px] flex-col gap-0 p-0 sm:max-w-[380px]">
        <SheetHeader className="border-b border-border px-4 py-3">
          <SheetTitle className="flex items-center gap-2 text-base">
            <span className="text-purple-600">✦</span>
            Copilot
          </SheetTitle>
        </SheetHeader>
        <ContextStrip />
        <MessageList />
        <QuickButtons />
        <ChatInput />
      </SheetContent>
    </Sheet>
  );
}
