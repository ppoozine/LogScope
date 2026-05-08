"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

type SampleLabel = "normal" | "edge_case" | "error";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (args: { label: SampleLabel; description: string }) => Promise<void> | void;
  pending?: boolean;
  rawLog: string;
};

export function SaveSampleDialog({ open, onOpenChange, onSubmit, pending, rawLog }: Props) {
  const [label, setLabel] = useState<SampleLabel>("normal");
  const [description, setDescription] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await onSubmit({ label, description });
  };

  const preview = rawLog.split("\n")[0]?.slice(0, 200) ?? "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>存為 sample</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs text-muted-foreground">內容（第一行）</Label>
            <pre className="overflow-x-auto rounded border bg-muted p-2 text-[11px]">
              {preview || "(空)"}
            </pre>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="sample-label">類型</Label>
            <select
              id="sample-label"
              value={label}
              onChange={(e) => setLabel(e.target.value as SampleLabel)}
              className="h-10 rounded-md border bg-background px-3 text-sm"
            >
              <option value="normal">normal — 正常 log</option>
              <option value="edge_case">edge_case — 邊緣情況</option>
              <option value="error">error — 錯誤 / 異常</option>
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="sample-desc">說明（可選）</Label>
            <input
              id="sample-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="h-10 rounded-md border bg-background px-3 text-sm"
              placeholder="例如：拒絕的封包"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={pending || !preview}>
              {pending ? "存入中…" : "存入"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
