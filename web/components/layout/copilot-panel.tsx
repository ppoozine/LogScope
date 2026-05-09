"use client";

import { X } from "lucide-react";

import { ChatInput } from "@/components/copilot/chat-input";
import { ContextStrip } from "@/components/copilot/context-strip";
import { InsertVrlDialog } from "@/components/copilot/insert-vrl-dialog";
import { MessageList } from "@/components/copilot/message-list";
import { QuickButtons } from "@/components/copilot/quick-buttons";
import { SafetyBanner } from "@/components/copilot/safety-banner";
import { useCopilot } from "@/components/providers/copilot-context";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/lib/use-media-query";
import { cn } from "@/lib/utils";

const DESKTOP_QUERY = "(min-width: 1024px)";

export function CopilotPanel() {
  const { isOpen, close } = useCopilot();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  return (
    <>
      {isDesktop ? (
        <DockedPanel isOpen={isOpen} onClose={close} />
      ) : (
        <SheetPanel isOpen={isOpen} onClose={close} />
      )}
      <InsertVrlDialog />
    </>
  );
}

function PanelBody() {
  return (
    <>
      <ContextStrip />
      <SafetyBanner />
      <MessageList />
      <QuickButtons />
      <ChatInput />
    </>
  );
}

function DockedPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <aside
      aria-label="Copilot"
      aria-hidden={!isOpen}
      className={cn(
        "flex h-full shrink-0 flex-col overflow-hidden border-l border-border bg-background transition-[width] duration-200 ease-out",
        isOpen ? "w-[380px]" : "w-0",
      )}
    >
      {/* Inner wrapper holds full 380px so contents don't reflow during the
          width transition; outer width animates the visible area. */}
      <div className="flex h-full w-[380px] flex-col">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <span className="text-purple-600">✦</span>
            Copilot
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Copilot"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </header>
        <PanelBody />
      </div>
    </aside>
  );
}

function SheetPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="flex w-[380px] flex-col gap-0 p-0 sm:max-w-[380px]">
        <SheetHeader className="border-b border-border px-4 py-3">
          <SheetTitle className="flex items-center gap-2 text-base">
            <span className="text-purple-600">✦</span>
            Copilot
          </SheetTitle>
        </SheetHeader>
        <PanelBody />
      </SheetContent>
    </Sheet>
  );
}
