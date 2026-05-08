import { Button } from "@/components/ui/button";

export function EmptyState({ onAddVendor }: { onAddVendor: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-muted-foreground/30 py-16">
      <h2 className="text-base font-medium">還沒有任何 vendor</h2>
      <p className="text-sm text-muted-foreground">從新增 Vendor 開始建立特徵庫</p>
      <Button onClick={onAddVendor}>新增 Vendor</Button>
    </div>
  );
}
