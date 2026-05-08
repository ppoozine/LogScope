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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";
import { useCreateVendor } from "@/lib/api/queries/library";

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

export function AddVendorDialog({ open, onOpenChange }: Props) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateVendor();

  const reset = () => {
    setName("");
    setSlug("");
    setError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ name, slug: slug || undefined, status: "active" });
      onOpenChange(false);
      reset();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("此 slug 已存在");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("建立失敗");
      }
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) reset();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增 Vendor</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="v-name">名稱</Label>
            <Input
              id="v-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Palo Alto Networks"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="v-slug">Slug（可選）</Label>
            <Input
              id="v-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="palo-alto-networks（自動產生）"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "建立中…" : "建立"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
