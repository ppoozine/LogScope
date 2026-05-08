import type { components } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type LogTypeDetail = components["schemas"]["LogTypeDetail"];

type Props = {
  logTypes: LogTypeDetail[];
  activeIdx: number;
  onChange: (idx: number) => void;
};

export function LogTypeTabs({ logTypes, activeIdx, onChange }: Props) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b">
      {logTypes.map((lt, idx) => {
        const isActive = idx === activeIdx;
        return (
          <button
            key={lt.id}
            type="button"
            onClick={() => onChange(idx)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm transition",
              isActive
                ? "border-purple-600 font-semibold text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <span>{lt.name}</span>
            <span className="ml-2 rounded bg-muted px-1.5 text-[10px] text-muted-foreground">
              {lt.status}
            </span>
          </button>
        );
      })}
    </div>
  );
}
