import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VrlDisplay } from "@/components/library/vrl-display";

describe("VrlDisplay", () => {
  it("renders empty state when no rule", () => {
    // Arrange / Act
    render(<VrlDisplay rule={null} />);

    // Assert
    expect(screen.getByText(/尚未建立 parse rule/)).toBeInTheDocument();
  });

  it("renders VRL code, version, engine when rule provided", () => {
    // Arrange / Act
    render(
      <VrlDisplay
        rule={{
          id: "r1",
          log_type_id: "lt1",
          version: 3,
          vrl_code: ".action = 'allow'",
          engine_version: "0.32",
          status: "published",
          notes: null,
          created_at: "2026-05-08T00:00:00Z",
          updated_at: "2026-05-08T00:00:00Z",
        }}
      />,
    );

    // Assert
    expect(screen.getByText(".action = 'allow'")).toBeInTheDocument();
    expect(screen.getByText(/v3/)).toBeInTheDocument();
    expect(screen.getByText(/0\.32/)).toBeInTheDocument();
  });

  it("disables 'edit' and 'load' buttons in v1c", () => {
    // Arrange / Act
    render(
      <VrlDisplay
        rule={{
          id: "r1",
          log_type_id: "lt1",
          version: 1,
          vrl_code: ".",
          engine_version: "0.32",
          status: "draft",
          notes: null,
          created_at: "2026-05-08T00:00:00Z",
          updated_at: "2026-05-08T00:00:00Z",
        }}
      />,
    );

    // Assert
    expect(screen.getByRole("button", { name: /載入 Analyzer/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /編輯/ })).toBeDisabled();
  });
});
