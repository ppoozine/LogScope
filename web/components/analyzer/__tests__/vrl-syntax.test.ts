import { describe, expect, it } from "vitest";

import { tokenizeVrlLine } from "@/components/analyzer/vrl-syntax";

describe("tokenizeVrlLine", () => {
  it("classifies comment", () => {
    expect(tokenizeVrlLine("# this is a comment")).toContain("comment");
  });

  it("classifies keyword", () => {
    const tokens = tokenizeVrlLine("if exists(.x) { del(.y) }");
    expect(tokens).toContain("keyword");
  });

  it("classifies string", () => {
    const tokens = tokenizeVrlLine('.action = "allow"');
    expect(tokens).toContain("string");
  });

  it("classifies field access", () => {
    const tokens = tokenizeVrlLine(".src_ip");
    expect(tokens).toContain("variableName");
  });
});
