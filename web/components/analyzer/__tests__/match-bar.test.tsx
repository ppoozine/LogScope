import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MatchBar } from "@/components/analyzer/match-bar";

const candidate = {
  vendor_slug: "palo-alto",
  product_slug: "pan-os",
  log_type_id: "11111111-1111-1111-1111-111111111111",
  log_type_name: "Traffic",
  confidence: 0.94,
  reason: "符合 PAN-OS",
};

describe("MatchBar", () => {
  it("renders empty state", () => {
    render(<MatchBar candidates={[]} isLoading={false} onApply={vi.fn()} onMatch={vi.fn()} />);
    expect(screen.getByText(/尚無候選/)).toBeInTheDocument();
  });

  it("shows no-key fallback when noKey=true", () => {
    render(
      <MatchBar candidates={[]} isLoading={false} onApply={vi.fn()} onMatch={vi.fn()} noKey />,
    );
    expect(screen.getByText(/未設 ANTHROPIC_API_KEY/)).toBeInTheDocument();
  });

  it("renders candidate with confidence pct", () => {
    render(
      <MatchBar candidates={[candidate]} isLoading={false} onApply={vi.fn()} onMatch={vi.fn()} />,
    );
    expect(screen.getByText("palo-alto · pan-os")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();
  });

  it("calls onApply when 套用 clicked", async () => {
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(
      <MatchBar candidates={[candidate]} isLoading={false} onApply={onApply} onMatch={vi.fn()} />,
    );
    await user.click(screen.getByRole("button", { name: "套用" }));
    expect(onApply).toHaveBeenCalledWith(candidate);
  });

  it("calls onMatch when Match clicked", async () => {
    const onMatch = vi.fn();
    const user = userEvent.setup();
    render(<MatchBar candidates={[]} isLoading={false} onApply={vi.fn()} onMatch={onMatch} />);
    await user.click(screen.getByRole("button", { name: "Match" }));
    expect(onMatch).toHaveBeenCalled();
  });
});
