import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SampleList } from "@/components/library/sample-list";

describe("SampleList", () => {
  it("renders empty state when no samples", () => {
    // Arrange / Act
    render(<SampleList samples={[]} />);

    // Assert
    expect(screen.getByText(/尚未加入 sample/)).toBeInTheDocument();
  });

  it("renders raw_log and label badge per sample", () => {
    // Arrange / Act
    render(
      <SampleList
        samples={[
          {
            id: "s1",
            log_type_id: "lt1",
            raw_log: "1,2,allow",
            label: "normal",
            description: null,
            created_at: "2026-05-08T00:00:00Z",
          },
          {
            id: "s2",
            log_type_id: "lt1",
            raw_log: "1,2,error",
            label: "error",
            description: null,
            created_at: "2026-05-08T00:00:00Z",
          },
        ]}
      />,
    );

    // Assert
    expect(screen.getByText("1,2,allow")).toBeInTheDocument();
    expect(screen.getByText("1,2,error")).toBeInTheDocument();
    expect(screen.getByText("normal")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });
});
