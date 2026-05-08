import { describe, expect, it } from "vitest";

import { diffMatches, diffPaths, stableStringify } from "@/lib/vrl/diff";

describe("stableStringify", () => {
  it("sorts keys at every level", () => {
    expect(stableStringify({ b: 1, a: 2 })).toBe(stableStringify({ a: 2, b: 1 }));
  });

  it("handles nested objects", () => {
    expect(stableStringify({ b: { d: 1, c: 2 }, a: 3 })).toBe(
      stableStringify({ a: 3, b: { c: 2, d: 1 } }),
    );
  });
});

describe("diffPaths", () => {
  it("empty for identical", () => {
    expect([...diffPaths({ a: 1 }, { a: 1 })]).toEqual([]);
  });

  it("flags top-level value mismatch", () => {
    const paths = [...diffPaths({ a: 1 }, { a: 2 })];
    expect(paths).toContain(".a");
  });

  it("flags missing key on either side", () => {
    const paths = [...diffPaths({ a: 1 }, { a: 1, b: 2 })];
    expect(paths).toContain(".b");
  });

  it("flags array length mismatch + element diffs", () => {
    const paths = [...diffPaths({ tags: [1, 2] }, { tags: [1, 2, 3] })];
    expect(paths).toContain(".tags");
    expect(paths).toContain(".tags[2]");
  });

  it("flags primitive vs object type mismatch", () => {
    const paths = [...diffPaths({ x: 1 }, { x: { y: 1 } })];
    expect(paths).toContain(".x");
  });
});

describe("diffMatches", () => {
  it("true when both success with same output", () => {
    expect(
      diffMatches(
        { status: "success", output: { a: 1, b: 2 } },
        { status: "success", output: { b: 2, a: 1 } },
      ),
    ).toBe(true);
  });

  it("false when outputs differ", () => {
    expect(
      diffMatches({ status: "success", output: { a: 1 } }, { status: "success", output: { a: 2 } }),
    ).toBe(false);
  });

  it("false when status mismatch", () => {
    expect(diffMatches({ status: "success", output: {} }, { status: "error", error: "x" })).toBe(
      false,
    );
  });

  it("compares error strings when both error", () => {
    expect(
      diffMatches({ status: "error", error: "boom" }, { status: "error", error: "boom" }),
    ).toBe(true);
    expect(
      diffMatches({ status: "error", error: "boom" }, { status: "error", error: "other" }),
    ).toBe(false);
  });
});
