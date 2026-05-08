import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SampleList } from "@/components/library/sample-list";

const SAMPLES = [
  {
    id: "s1",
    log_type_id: "lt1",
    raw_log: "1,2,allow",
    label: "normal" as const,
    description: null,
    created_at: "2026-05-08T00:00:00Z",
  },
  {
    id: "s2",
    log_type_id: "lt1",
    raw_log: "1,2,error",
    label: "error" as const,
    description: null,
    created_at: "2026-05-08T00:00:00Z",
  },
];

describe("SampleList", () => {
  it("renders empty state when no samples", () => {
    // Arrange / Act
    render(<SampleList samples={[]} />);

    // Assert
    expect(screen.getByText(/尚未加入 sample/)).toBeInTheDocument();
  });

  it("renders raw_log and label badge per sample", () => {
    // Arrange / Act
    render(<SampleList samples={SAMPLES} />);

    // Assert
    expect(screen.getByText("1,2,allow")).toBeInTheDocument();
    expect(screen.getByText("1,2,error")).toBeInTheDocument();
    expect(screen.getByText("normal")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("disables '在 Analyzer 試打' buttons when no logTypeId", () => {
    // Arrange / Act
    render(<SampleList samples={SAMPLES} />);

    // Assert
    const buttons = screen.getAllByRole("button", { name: /在 Analyzer 試打/ });
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });

  it("renders '在 Analyzer 試打' as Link with correct href when logTypeId provided", () => {
    // Arrange / Act
    render(<SampleList samples={SAMPLES} logTypeId="lt1" />);

    // Assert: each sample gets a link with correct href
    const links = screen.getAllByRole("link", { name: /在 Analyzer 試打/ });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/analyzer?log_type_id=lt1&sample_id=s1");
    expect(links[1]).toHaveAttribute("href", "/analyzer?log_type_id=lt1&sample_id=s2");
  });
});
