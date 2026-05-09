import { describe, expect, it } from "vitest";

import { extractVrlBlock } from "@/lib/copilot/extract-vrl-block";

describe("extractVrlBlock", () => {
  it("extracts content of a single ```vrl block", () => {
    const text = "前言\n```vrl\n. = parse_syslog!(.message)\n```\n後續說明";
    expect(extractVrlBlock(text)).toBe(". = parse_syslog!(.message)");
  });

  it("returns null when no vrl block exists", () => {
    expect(extractVrlBlock("純文字回應")).toBeNull();
    expect(extractVrlBlock("```python\nprint(1)\n```")).toBeNull();
  });

  it("returns the FIRST vrl block when multiple exist", () => {
    const text = "```vrl\nfirst\n```\n中間\n```vrl\nsecond\n```";
    expect(extractVrlBlock(text)).toBe("first");
  });

  it("returns null for an unclosed (streaming-mid) vrl block", () => {
    const text = "```vrl\n. = parse_syslog"; // 還沒到 closing ```
    expect(extractVrlBlock(text)).toBeNull();
  });

  it("handles multi-line vrl content", () => {
    const text = "```vrl\nline1\nline2\nline3\n```";
    expect(extractVrlBlock(text)).toBe("line1\nline2\nline3");
  });
});
