"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLogTypeStats } from "@/lib/api/queries/library-stats";
import { cn } from "@/lib/utils";

type StatsRange = "7d" | "14d" | "30d" | "90d";
const RANGES: StatsRange[] = ["7d", "14d", "30d", "90d"];

type Props = { logTypeId: string };

export function LogTypeStatsTab({ logTypeId }: Props) {
  const [range, setRange] = useState<StatsRange>("7d");
  const query = useLogTypeStats(logTypeId, range);

  if (query.isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">載入中…</p>;
  }
  if (query.isError) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-sm">
        暫時無法取得統計
        <button type="button" className="ml-3 underline" onClick={() => query.refetch()}>
          重試
        </button>
      </div>
    );
  }
  const stats = query.data!;
  if (!stats.enabled) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-sm text-muted-foreground">
        Stats 功能需啟用 ClickHouse（環境變數 <code>CLICKHOUSE_URL</code>）
      </div>
    );
  }
  if (stats.timeline.length === 0) {
    return (
      <div className="flex flex-col gap-3 p-6">
        <RangeToggle range={range} onChange={setRange} />
        <p className="text-sm text-muted-foreground">過去 {stats.range_days} 天無 parse 紀錄</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <RangeToggle range={range} onChange={setRange} />
        <div className="text-xs text-muted-foreground">
          總計 {stats.totals.total} · 成功 {stats.totals.success} · 失敗 {stats.totals.error} ·
          成功率 {(stats.totals.success_rate * 100).toFixed(1)}%
        </div>
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart
            data={stats.timeline.map((p) => ({
              day: p.day,
              successRate: Number((p.success_rate * 100).toFixed(2)),
              volume: p.total,
            }))}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="successRate"
              stroke="#22c55e"
              dot={false}
              name="Success rate"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="volume"
              stroke="#6366f1"
              dot={false}
              name="Volume"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RangeToggle({
  range,
  onChange,
}: {
  range: StatsRange;
  onChange: (r: StatsRange) => void;
}) {
  return (
    <div className="flex gap-1">
      {RANGES.map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => onChange(r)}
          className={cn(
            "rounded border px-2 py-0.5 text-xs",
            r === range
              ? "border-purple-600 bg-purple-100 text-purple-900"
              : "border-transparent text-muted-foreground hover:border-muted",
          )}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
