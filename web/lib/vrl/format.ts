/**
 * Best-effort VRL formatter — indents based on `{` / `}` depth.
 *
 * Does NOT understand VRL grammar. Skips braces inside string literals
 * (single + double quoted) and after `#` line comments. Trims trailing
 * whitespace. Collapses 3+ consecutive blank lines down to 1.
 *
 * Ported from pyvrl-playground POC's app.js formatVrlSource().
 */

const INDENT = "  ";

type LineStats = {
  opens: number;
  closes: number;
  startsWithClose: boolean;
};

function analyzeLineBraces(line: string): LineStats {
  let opens = 0;
  let closes = 0;
  let firstToken: "open" | "close" | "other" | null = null;
  let inStr: string | null = null;
  let isEscape = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) {
      if (isEscape) {
        isEscape = false;
        continue;
      }
      if (c === "\\") {
        isEscape = true;
        continue;
      }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === "#") break; // VRL line comment
    if (c === '"' || c === "'") {
      inStr = c;
      if (firstToken === null) firstToken = "other";
      continue;
    }
    if (c === "{") {
      opens++;
      if (firstToken === null) firstToken = "open";
    } else if (c === "}") {
      closes++;
      if (firstToken === null) firstToken = "close";
    } else if (!/\s/.test(c) && firstToken === null) {
      firstToken = "other";
    }
  }
  return { opens, closes, startsWithClose: firstToken === "close" };
}

export function formatVrlSource(src: string): string {
  const lines = src.split(/\r?\n/);
  const out: string[] = [];
  let level = 0;
  for (const raw of lines) {
    const line = raw.replace(/[ \t]+$/, "");
    const trimmed = line.trimStart();
    if (trimmed === "") {
      out.push("");
      continue;
    }
    const stats = analyzeLineBraces(trimmed);
    const dedent = stats.startsWithClose ? 1 : 0;
    const placement = Math.max(0, level - dedent);
    out.push(INDENT.repeat(placement) + trimmed);
    const remainingCloses = stats.closes - dedent;
    level = Math.max(0, placement + stats.opens - remainingCloses);
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n");
}
