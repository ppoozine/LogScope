"use client";

import { useCopilotStore } from "@/lib/copilot/store";

export function SafetyBanner() {
  const skill = useCopilotStore((s) => s.lastSkill);
  if (skill !== "vrl_generate" && skill !== "vrl_optimize") return null;
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] text-amber-800">
      ⚠ 生成的 VRL 不要 hard-code API key / token / password
    </div>
  );
}
