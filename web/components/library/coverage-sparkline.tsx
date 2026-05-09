import { cn } from "@/lib/utils";

type Props = {
  data: number[]; // 0..1 success rate per day
  width?: number; // default 70px
  height?: number; // default 20px
  className?: string;
};

const CHART_HEIGHT = 20;

export function CoverageSparkline({ data, width = 70, height = CHART_HEIGHT, className }: Props) {
  if (data.length === 0) {
    return <span className={cn("text-xs text-muted-foreground", className)}>—</span>;
  }
  const barWidth = width / data.length;
  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label="success rate sparkline"
      className={className}
    >
      {data.map((v, i) => {
        const clamped = Math.max(0, Math.min(1, v));
        const barH = clamped * height;
        const x = i * barWidth;
        const y = height - barH;
        const color = clamped >= 0.95 ? "#22c55e" : clamped >= 0.7 ? "#eab308" : "#ef4444";
        return (
          <rect
            // biome-ignore lint/suspicious/noArrayIndexKey: sparkline data is immutable and never reordered
            key={i}
            x={x}
            y={y}
            width={Math.max(barWidth - 1, 1)}
            height={barH}
            fill={color}
          />
        );
      })}
    </svg>
  );
}
