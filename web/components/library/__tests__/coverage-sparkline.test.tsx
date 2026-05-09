import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CoverageSparkline } from "../coverage-sparkline";

describe("CoverageSparkline", () => {
  it("renders one bar per data point", () => {
    const { container } = render(<CoverageSparkline data={[0, 0.5, 1]} />);
    const bars = container.querySelectorAll("rect");
    expect(bars.length).toBe(3);
  });

  it("renders empty state when data is empty", () => {
    const { getByText } = render(<CoverageSparkline data={[]} />);
    expect(getByText(/—/)).toBeInTheDocument();
  });

  it("clamps values to 0..1", () => {
    const { container } = render(<CoverageSparkline data={[-0.5, 1.5]} />);
    const bars = container.querySelectorAll("rect");
    const heights = Array.from(bars).map((b) => Number(b.getAttribute("height")));
    expect(heights[0]).toBeLessThanOrEqual(20);
    expect(heights[1]).toBeLessThanOrEqual(20);
    expect(heights[0]).toBeGreaterThanOrEqual(0);
  });
});
