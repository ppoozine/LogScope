const VRL_BLOCK_RE = /```vrl\n([\s\S]*?)\n```/;

export function extractVrlBlock(text: string): string | null {
  const m = VRL_BLOCK_RE.exec(text);
  return m ? m[1] : null;
}
