import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VrlDisplay } from "@/components/library/vrl-display";

const RULE = {
  id: "r1",
  log_type_id: "lt1",
  version: 1,
  vrl_code: ".",
  engine_version: "0.32" as const,
  status: "draft" as const,
  notes: null,
  created_at: "2026-05-08T00:00:00Z",
  updated_at: "2026-05-08T00:00:00Z",
};

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

  it("disables '載入 Analyzer' and '編輯' buttons when no logTypeId", () => {
    // Arrange / Act
    render(<VrlDisplay rule={RULE} />);

    // Assert
    expect(screen.getByRole("button", { name: /載入 Analyzer/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /編輯/ })).toBeDisabled();
  });

  it("renders '載入 Analyzer' as Link with correct href when logTypeId provided", () => {
    // Arrange / Act
    render(<VrlDisplay rule={RULE} logTypeId="lt1" />);

    // Assert: anchor exists with correct href
    const link = screen.getByRole("link", { name: /載入 Analyzer/ });
    expect(link).toHaveAttribute("href", "/analyzer?log_type_id=lt1");

    // '編輯' should still be a disabled button
    expect(screen.getByRole("button", { name: /編輯/ })).toBeDisabled();
  });
});
