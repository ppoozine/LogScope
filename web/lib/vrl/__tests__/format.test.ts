import { describe, expect, it } from "vitest";

import { formatVrlSource } from "@/lib/vrl/format";

describe("formatVrlSource", () => {
  it("indents braces", () => {
    const src = "if .x > 0 {\n.y = 1\n}";
    expect(formatVrlSource(src)).toBe("if .x > 0 {\n  .y = 1\n}");
  });

  it("indents nested braces", () => {
    const src = "if a {\nif b {\n.x = 1\n}\n}";
    expect(formatVrlSource(src)).toBe("if a {\n  if b {\n    .x = 1\n  }\n}");
  });

  it("ignores braces inside strings", () => {
    const src = '.x = "{ should not indent }"\n.y = 1';
    expect(formatVrlSource(src)).toBe('.x = "{ should not indent }"\n.y = 1');
  });

  it("ignores braces after # comment", () => {
    const src = "# { fake brace\n.x = 1";
    expect(formatVrlSource(src)).toBe("# { fake brace\n.x = 1");
  });

  it("collapses 3+ blank lines", () => {
    const src = "a\n\n\n\nb";
    expect(formatVrlSource(src)).toBe("a\n\nb");
  });

  it("trims trailing whitespace", () => {
    const src = "a   \nb\t\nc";
    expect(formatVrlSource(src)).toBe("a\nb\nc");
  });

  it("preserves single blank lines", () => {
    expect(formatVrlSource("a\n\nb")).toBe("a\n\nb");
  });
});
