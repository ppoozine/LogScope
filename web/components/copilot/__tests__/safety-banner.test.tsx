import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SafetyBanner } from "@/components/copilot/safety-banner";
import { useCopilotStore } from "@/lib/copilot/store";

describe("<SafetyBanner>", () => {
  it("renders for vrl_generate", () => {
    useCopilotStore.setState({ lastSkill: "vrl_generate" });
    render(<SafetyBanner />);
    expect(screen.getByText(/hard-code/i)).toBeInTheDocument();
  });

  it("renders for vrl_optimize", () => {
    // M3 future skill — set as any to bypass M1 type narrowness
    // biome-ignore lint/suspicious/noExplicitAny: M1 hasn't extended SkillName yet
    useCopilotStore.setState({ lastSkill: "vrl_optimize" as any });
    render(<SafetyBanner />);
    expect(screen.getByText(/hard-code/i)).toBeInTheDocument();
  });

  it("does not render for log_explain", () => {
    useCopilotStore.setState({ lastSkill: "log_explain" });
    const { container } = render(<SafetyBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("does not render when lastSkill is null", () => {
    useCopilotStore.setState({ lastSkill: null });
    const { container } = render(<SafetyBanner />);
    expect(container.firstChild).toBeNull();
  });
});
