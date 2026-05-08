import { StreamLanguage, type StringStream } from "@codemirror/language";

const KEYWORDS = new Set(["if", "else", "null", "true", "false", "del", "exists", "abort"]);

const BUILTINS = new Set([
  "parse_csv",
  "parse_csv!",
  "parse_json",
  "parse_json!",
  "parse_regex",
  "parse_regex!",
  "parse_syslog",
  "parse_syslog!",
  "to_string",
  "to_string!",
  "to_int",
  "to_int!",
  "to_float",
  "to_float!",
  "to_timestamp",
  "to_timestamp!",
  "downcase",
  "downcase!",
  "upcase",
  "upcase!",
  "starts_with",
  "ends_with",
  "contains",
  "match",
  "replace",
  "split",
  "join",
  "length",
  "now",
  "format_timestamp",
  "format_timestamp!",
]);

interface StreamStreamLike {
  start: number;
  position: number;
  eol(): boolean;
  next(): string | undefined;
  eatSpace(): boolean;
  match(pat: string | RegExp): boolean | RegExpMatchArray | null;
  skipToEnd(): void;
}

function vrlToken(stream: StreamStreamLike): string | null {
  if (stream.eatSpace()) return null;

  if (stream.match("#")) {
    stream.skipToEnd();
    return "comment";
  }

  if (stream.match('"')) {
    let escaped = false;
    while (!stream.eol()) {
      const ch = stream.next();
      if (escaped) {
        escaped = false;
        continue;
      }
      if (ch === "\\") {
        escaped = true;
        continue;
      }
      if (ch === '"') break;
    }
    return "string";
  }

  if (stream.match(/^\.[a-zA-Z_][a-zA-Z0-9_]*/)) {
    return "variableName";
  }

  const m = stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*!?/);
  if (m) {
    const word = String(m);
    if (KEYWORDS.has(word)) return "keyword";
    if (BUILTINS.has(word)) return "function";
    return null;
  }

  if (stream.match(/^-?\d+(\.\d+)?/)) {
    return "number";
  }

  // Consume unrecognized character so the stream always advances.
  stream.next();
  return null;
}

export function tokenizeVrlLine(line: string): Set<string> {
  const stream = new StreamSimulator(line);
  const tags = new Set<string>();
  while (!stream.eol()) {
    const before = stream.position;
    const tag = vrlToken(stream);
    if (tag) tags.add(tag);
    if (stream.position === before) stream.next();
  }
  return tags;
}

export const vrlLanguage = StreamLanguage.define({
  name: "vrl",
  startState: () => ({}),
  token: (stream: StringStream) => vrlToken(stream as unknown as StreamStreamLike),
});

class StreamSimulator implements StreamStreamLike {
  start = 0;
  position = 0;
  private text: string;

  constructor(text: string) {
    this.text = text;
  }

  eol(): boolean {
    return this.position >= this.text.length;
  }

  next(): string | undefined {
    if (this.eol()) return undefined;
    return this.text[this.position++];
  }

  eatSpace(): boolean {
    const before = this.position;
    while (!this.eol() && /\s/.test(this.text[this.position])) this.position++;
    return this.position > before;
  }

  match(pat: string | RegExp): boolean | RegExpMatchArray | null {
    this.start = this.position;
    if (typeof pat === "string") {
      if (this.text.startsWith(pat, this.position)) {
        this.position += pat.length;
        return true;
      }
      return false;
    }
    const m = this.text.slice(this.position).match(pat);
    if (m && m.index === 0) {
      this.position += m[0].length;
      return m;
    }
    return null;
  }

  skipToEnd(): void {
    this.position = this.text.length;
  }
}
