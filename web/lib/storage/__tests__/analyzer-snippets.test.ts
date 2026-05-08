import { afterEach, describe, expect, it } from "vitest";

import {
  type AnalyzerSnippet,
  deleteSnippet,
  loadSnippets,
  mergeSnippets,
  saveSnippets,
  upsertSnippet,
} from "@/lib/storage/analyzer-snippets";

afterEach(() => {
  window.localStorage.removeItem("analyzer:snippets");
});

const sample: AnalyzerSnippet = {
  name: "demo",
  vrl: ".x = 1\n.",
  logs: "a",
  engineVersion: "0.32",
  savedAt: "2026-05-08T00:00:00Z",
};

describe("analyzer-snippets", () => {
  it("returns empty when nothing saved", () => {
    expect(loadSnippets()).toEqual([]);
  });

  it("upserts new snippet", () => {
    upsertSnippet(sample);
    expect(loadSnippets()).toEqual([sample]);
  });

  it("upserts overwrites same name", () => {
    upsertSnippet(sample);
    upsertSnippet({ ...sample, vrl: "different" });
    const list = loadSnippets();
    expect(list).toHaveLength(1);
    expect(list[0].vrl).toBe("different");
  });

  it("delete removes by name", () => {
    upsertSnippet(sample);
    upsertSnippet({ ...sample, name: "other" });
    deleteSnippet("demo");
    expect(loadSnippets().map((s) => s.name)).toEqual(["other"]);
  });

  it("loadSnippets ignores malformed entries", () => {
    window.localStorage.setItem(
      "analyzer:snippets",
      JSON.stringify([sample, { not: "valid" }, { name: "x" }]),
    );
    expect(loadSnippets()).toHaveLength(1);
  });

  it("loadSnippets sorts by name", () => {
    saveSnippets([
      { ...sample, name: "zebra" },
      { ...sample, name: "alpha" },
    ]);
    expect(loadSnippets().map((s) => s.name)).toEqual(["alpha", "zebra"]);
  });

  it("mergeSnippets adds and replaces", () => {
    upsertSnippet(sample); // existing "demo"
    const result = mergeSnippets([
      { ...sample, vrl: "replaced" }, // same name → replace
      { ...sample, name: "newone" }, // new
    ]);
    expect(result).toEqual({ added: 1, replaced: 1, total: 2 });
    const list = loadSnippets();
    expect(list).toHaveLength(2);
    expect(list.find((s) => s.name === "demo")?.vrl).toBe("replaced");
  });

  it("mergeSnippets rejects non-array", () => {
    expect(() => mergeSnippets({ not: "array" })).toThrow(/JSON array/);
  });

  it("mergeSnippets rejects array with no valid entries", () => {
    expect(() => mergeSnippets([{ junk: 1 }])).toThrow(/No valid/);
  });
});
