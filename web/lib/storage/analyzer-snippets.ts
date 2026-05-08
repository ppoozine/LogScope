"use client";

const KEY = "analyzer:snippets";

export type AnalyzerSnippet = {
  name: string;
  vrl: string;
  logs: string;
  engineVersion: "0.25" | "0.32";
  savedAt: string; // ISO timestamp
};

function isValidSnippet(s: unknown): s is AnalyzerSnippet {
  if (!s || typeof s !== "object") return false;
  const o = s as Record<string, unknown>;
  return (
    typeof o.name === "string" &&
    o.name.length > 0 &&
    typeof o.vrl === "string" &&
    typeof o.logs === "string" &&
    (o.engineVersion === "0.25" || o.engineVersion === "0.32") &&
    typeof o.savedAt === "string"
  );
}

export function loadSnippets(): AnalyzerSnippet[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isValidSnippet).sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    return [];
  }
}

export function saveSnippets(snippets: AnalyzerSnippet[]): void {
  if (typeof window === "undefined") return;
  const sorted = [...snippets].sort((a, b) => a.name.localeCompare(b.name));
  window.localStorage.setItem(KEY, JSON.stringify(sorted));
}

export function upsertSnippet(snippet: AnalyzerSnippet): AnalyzerSnippet[] {
  const list = loadSnippets();
  const existing = list.findIndex((s) => s.name === snippet.name);
  if (existing >= 0) list[existing] = snippet;
  else list.push(snippet);
  saveSnippets(list);
  return loadSnippets();
}

export function deleteSnippet(name: string): AnalyzerSnippet[] {
  const list = loadSnippets().filter((s) => s.name !== name);
  saveSnippets(list);
  return list;
}

/**
 * Merge imported snippets with existing ones, replacing same-name
 * entries. Returns {added, replaced, total} counts.
 */
export function mergeSnippets(imported: unknown): {
  added: number;
  replaced: number;
  total: number;
} {
  if (!Array.isArray(imported)) {
    throw new Error("Imported file must be a JSON array.");
  }
  const valid = imported.filter(isValidSnippet);
  if (valid.length === 0) {
    throw new Error("No valid snippets found in file.");
  }
  const current = loadSnippets();
  const byName = new Map(current.map((s) => [s.name, s]));
  let added = 0;
  let replaced = 0;
  for (const s of valid) {
    if (byName.has(s.name)) replaced++;
    else added++;
    byName.set(s.name, s);
  }
  saveSnippets([...byName.values()]);
  return { added, replaced, total: valid.length };
}
