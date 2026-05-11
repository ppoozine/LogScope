"""Shared VRL function cheatsheet — used by copilot vrl_generate and llm_pipeline draft prompts.

Keep this string byte-identical with what shipped in copilot D2 so downstream
prompt-cache hits remain valid.
"""

VRL_CHEATSHEET = """\
## VRL function cheatsheet (engine 0.32)

These are the functions you should reach for first. Do NOT invent
function names — if it's not here and you're not sure, say so.

- `parse_syslog!(.message)` — parses RFC 5424/3164 header into root.
  Sets `.appname`, `.hostname`, `.severity`, `.facility`, `.timestamp`,
  and leaves the body as `.message`.
- `parse_json!(.message)` — parses a JSON object; fields become root
  fields. Use `??` if some logs aren't JSON.
- `parse_key_value!(.message, key_value_delimiter: "=", field_delimiter: " ")`
  — k=v pairs (CEF, many SIEM formats).
- `parse_regex!(string, r'(?P<name>regex)')` — named capture groups
  return a map. Use for vendor-specific layouts.
- `parse_csv!(string)` — string array; index `[0]`, `[1]`...
- `split(string, ",")` — same shape as parse_csv but no quoting rules.
- Conversion: `to_int!`, `to_float!`, `to_bool!`, `to_string!`,
  `to_timestamp!(s, "%Y-%m-%d %H:%M:%S")` (strptime format).
- `del(.field)` — remove a field (use for redaction or cleanup).
- `if exists(.field) { ... }` — conditional on optional fields.
- `string!(.x)` — coerce/assert a value is string (use before `split`).

### Suffixes — get this right or it won't compile

- `!` — fail-fast: aborts the whole event if the call errors. Use when
  the input is structurally guaranteed (e.g., `parse_json!` after you've
  established the log IS json).
- `??` — fallback: returns the right-hand value on error.
  `parse_json(.x) ?? {}` never aborts; you can then check fields.
- Functions that return a `Result` (almost all parse_* and to_*) MUST
  use `!` or `??`. Bare calls are compile errors.

### 0.25 vs 0.32 syntax

Default to 0.32 unless `<facts><vrl_engine>` says otherwise.
- 0.32 added `parse_key_value`; on 0.25 use `parse_kv` instead.
- Both support `parse_syslog`, `parse_json`, `parse_regex`, `split`.

"""
