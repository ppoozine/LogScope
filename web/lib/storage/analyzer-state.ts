const KEY = "analyzer:state";

export type AnalyzerStorage = {
  vrl: string;
  logs: string;
  engineVersion: "0.25" | "0.32";
};

export function loadAnalyzerState(): AnalyzerStorage | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<AnalyzerStorage>;
    if (
      typeof parsed?.vrl === "string" &&
      typeof parsed?.logs === "string" &&
      (parsed?.engineVersion === "0.25" || parsed?.engineVersion === "0.32")
    ) {
      return parsed as AnalyzerStorage;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveAnalyzerState(state: AnalyzerStorage): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(state));
}

export function clearAnalyzerState(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
}
