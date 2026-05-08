import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { components } from "@/lib/api/types";

import { VersionDiffModal } from "../version-diff-modal";

type ParseRuleRead = components["schemas"]["ParseRuleRead"];

const RULES: ParseRuleRead[] = [
  {
    id: "r2",
    version: 2,
    vrl_code: ".x = 2",
    status: "draft",
    log_type_id: "1",
    engine_version: "0.32",
    notes: null,
    created_at: "",
    updated_at: "",
  },
  {
    id: "r1",
    version: 1,
    vrl_code: ".x = 1",
    status: "published",
    log_type_id: "1",
    engine_version: "0.32",
    notes: null,
    created_at: "",
    updated_at: "",
  },
];

describe("VersionDiffModal", () => {
  it("renders diff between selected versions", async () => {
    const { container } = render(
      <VersionDiffModal rules={RULES} initialLeftId="r1" initialRightId="r2" onClose={vi.fn()} />,
    );
    // diff viewer shows both texts somewhere
    await waitFor(() => {
      expect(container.textContent).toContain(".x = 1");
      expect(container.textContent).toContain(".x = 2");
    });
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(
      <VersionDiffModal rules={RULES} initialLeftId="r1" initialRightId="r2" onClose={onClose} />,
    );
    screen.getByRole("button", { name: /關閉|close/i }).click();
    expect(onClose).toHaveBeenCalled();
  });
});
