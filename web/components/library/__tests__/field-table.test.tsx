import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FieldTable } from "@/components/library/field-table";
import type { components } from "@/lib/api/types";

type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];

function makeField(
  name: string,
  type: FieldSchemaRead["field_type"],
  identifier = false,
): FieldSchemaRead {
  return {
    id: `f-${name}`,
    log_type_id: "lt1",
    field_name: name,
    field_type: type,
    description: null,
    is_required: false,
    is_identifier: identifier,
    example_value: null,
    sort_order: 0,
  };
}

describe("FieldTable", () => {
  it("renders empty state when no fields", () => {
    // Arrange / Act
    render(<FieldTable fields={[]} />);

    // Assert
    expect(screen.getByText(/尚未定義欄位/)).toBeInTheDocument();
  });

  it("renders rows with identifier badge", () => {
    // Arrange / Act
    render(
      <FieldTable fields={[makeField("src_ip", "ip", true), makeField("action", "string")]} />,
    );

    // Assert
    expect(screen.getByText("src_ip")).toBeInTheDocument();
    expect(screen.getByText("identifier")).toBeInTheDocument();
    expect(screen.getByText("action")).toBeInTheDocument();
  });
});
