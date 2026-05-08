/**
 * Stable JSON pretty-print with sorted object keys at every level.
 *
 * Used to compare engine outputs without false-positive diffs from
 * key ordering differences between engine versions.
 */
export function stableStringify(value: unknown, indent = 2): string {
  return JSON.stringify(value, sortedReplacer, indent);
}

function sortedReplacer(_key: string, value: unknown): unknown {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const sorted: Record<string, unknown> = {};
    for (const k of Object.keys(value as Record<string, unknown>).sort()) {
      sorted[k] = (value as Record<string, unknown>)[k];
    }
    return sorted;
  }
  return value;
}

/**
 * Recursively walk two JSON values; return the set of dotted/bracketed
 * paths where they differ. Examples: ".user.id", ".tags[3]".
 *
 * Top-level mismatch returns a set containing "" (the root).
 */
export function diffPaths(
  a: unknown,
  b: unknown,
  path = "",
  out: Set<string> = new Set(),
): Set<string> {
  if (a === b) return out;
  const ta = typeof a;
  const tb = typeof b;
  if (a === null || b === null || ta !== tb || ta !== "object") {
    out.add(path);
    return out;
  }
  if (Array.isArray(a) !== Array.isArray(b)) {
    out.add(path);
    return out;
  }
  if (Array.isArray(a)) {
    const arrA = a as unknown[];
    const arrB = b as unknown[];
    if (arrA.length !== arrB.length) out.add(path);
    const len = Math.max(arrA.length, arrB.length);
    for (let i = 0; i < len; i++) {
      if (i >= arrA.length || i >= arrB.length) {
        out.add(`${path}[${i}]`);
        continue;
      }
      diffPaths(arrA[i], arrB[i], `${path}[${i}]`, out);
    }
    return out;
  }
  const objA = a as Record<string, unknown>;
  const objB = b as Record<string, unknown>;
  const keys = new Set([...Object.keys(objA), ...Object.keys(objB)]);
  for (const k of keys) {
    const sub = `${path}.${k}`;
    if (!(k in objA) || !(k in objB)) {
      out.add(sub);
      continue;
    }
    diffPaths(objA[k], objB[k], sub, out);
  }
  return out;
}

/**
 * Compare two ParseResultItem-like objects:
 * - Both must have the same status
 * - For success: stable-stringified output must match
 * - For error: error string must match
 */
export function diffMatches(
  ra: { status: string; output?: unknown; error?: string | null },
  rb: { status: string; output?: unknown; error?: string | null },
): boolean {
  if (ra.status !== rb.status) return false;
  if (ra.status === "error") return (ra.error ?? "") === (rb.error ?? "");
  return stableStringify(ra.output) === stableStringify(rb.output);
}
