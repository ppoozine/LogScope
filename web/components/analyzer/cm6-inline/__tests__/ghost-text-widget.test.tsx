import { describe, expect, it } from "vitest";

import { GhostTextWidget } from "@/components/analyzer/cm6-inline/ghost-text-widget";

describe("GhostTextWidget", () => {
  it("renders ghost text with pre + pointer-events none", () => {
    const w = new GhostTextWidget(".dst_ip = parts[7]", "insert");
    const dom = w.toDOM();
    expect(dom.textContent).toBe(".dst_ip = parts[7]");
    expect(dom.getAttribute("data-cm-inline-ghost")).toBe("insert");
    const style = (dom as HTMLElement).style;
    expect(style.whiteSpace).toBe("pre");
    expect(style.pointerEvents).toBe("none");
  });

  it("eq returns true for same text and mode", () => {
    const a = new GhostTextWidget("abc", "insert");
    const b = new GhostTextWidget("abc", "insert");
    expect(a.eq(b)).toBe(true);
  });

  it("eq returns false when text differs", () => {
    const a = new GhostTextWidget("abc", "insert");
    const b = new GhostTextWidget("abcd", "insert");
    expect(a.eq(b)).toBe(false);
  });

  it("eq returns false when mode differs", () => {
    const a = new GhostTextWidget("abc", "insert");
    const b = new GhostTextWidget("abc", "replace");
    expect(a.eq(b)).toBe(false);
  });
});
