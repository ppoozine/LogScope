import { afterEach, describe, expect, it } from "vitest";

import {
  clearAnalyzerState,
  loadAnalyzerState,
  saveAnalyzerState,
} from "@/lib/storage/analyzer-state";

afterEach(() => clearAnalyzerState());

describe("analyzer-state", () => {
  it("round-trips state", () => {
    saveAnalyzerState({ vrl: ".x = 1\n.", logs: "a", engineVersion: "0.32" });
    expect(loadAnalyzerState()).toEqual({
      vrl: ".x = 1\n.",
      logs: "a",
      engineVersion: "0.32",
    });
  });

  it("returns null when nothing saved", () => {
    expect(loadAnalyzerState()).toBeNull();
  });

  it("returns null when payload malformed", () => {
    window.localStorage.setItem("analyzer:state", "not json");
    expect(loadAnalyzerState()).toBeNull();
  });

  it("returns null when engineVersion is invalid", () => {
    window.localStorage.setItem(
      "analyzer:state",
      JSON.stringify({ vrl: "", logs: "", engineVersion: "999" }),
    );
    expect(loadAnalyzerState()).toBeNull();
  });
});
