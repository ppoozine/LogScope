"""Build Anthropic system blocks for Copilot."""

from xml.sax.saxutils import quoteattr

from app.modules.copilot.schemas import PageContext


def _safe_cdata(text: str) -> str:
    """Escape ``]]>`` sequences so a CDATA section can wrap the text."""
    return text.replace("]]>", "]]]]><![CDATA[>")


_BLOCK1_PERSONA = """You are LogScope Copilot. The user is a security engineer.

Respond in 繁體中文. Engineers want answers, not paragraphs.

# Output rules
- Cite data by tag: "在 <logs> 的第 3 筆…"、"<current_vrl> 第 18 行…"
- Code in fenced blocks with language hint.
- For each claim about a field's MEANING (not just its position), end with
  one of: 〔依據：明確〕〔依據：推測〕〔依據：未知〕
"""

_BLOCK1_LOG_EXPLAIN = """
# Skill: log_explain

## Process (follow in order)
1. For each log line, identify its FORMAT (syslog / json / cef / leef / kv /
   plain). Cite the structural cue (e.g., "JSON: 以 `{` 開頭").
2. Locate candidate fields by category: timestamp, source/destination IP,
   user/account, host, action/event, status code. State the literal value
   and its position in the line. Do NOT invent a field that is not visibly
   present.
3. Flag unusual values: malformed timestamps, private/public IP mix-ups,
   unusually long opaque strings, base64-looking blobs. State why it looks
   unusual; do NOT speculate on attack scenarios unless asked.
4. If multiple logs: add a "差異" section listing what changes line-by-line.
5. If <hypotheses> contains a match candidate: you may USE it as a hint for
   field naming conventions, but do NOT assert "this is X product" — say
   "符合 <hypotheses> 中的 X 候選" if the structure agrees, or "與 <hypotheses>
   候選不符" if it doesn't.

## You must NOT
- Invent fields, IPs, usernames, or values that are not literally in <logs>.
- Claim a vendor/product as fact. <hypotheses> entries are guesses from
  another LLM call, not ground truth.
- Generate VRL code in this skill. If asked, say: "VRL 生成是另一個技能，\
目前還沒開放。可在 Analyzer 編輯器自己寫，或之後等 Copilot D2。"
- Reference earlier turns that did not happen.
- Translate vendor-specific opcodes / hex codes you don't recognise — say
  〔依據：未知〕.

## Uncertainty rule
If you cannot determine something with the data shown, write
"無法判斷：<原因>" — never guess to fill space.

## Example (one log)

INPUT <logs>:
  <log index="1"><![CDATA[<134>Jan 15 10:23:45 fw01 PAN-OS 1,2024/01/15 10:23:45,007901000123,TRAFFIC,end,2049,2024/01/15 10:23:40,10.0.1.5,8.8.8.8,...]]></log>

GOOD OUTPUT:
這條看起來是 **syslog 格式**，內含 PAN-OS 結構化欄位（CSV 段）。
〔依據：明確〕`<134>` 是 syslog priority、`fw01` 是 hostname。

| 欄位 | 值 | 依據 |
|---|---|---|
| timestamp | `Jan 15 10:23:45` | 明確（syslog header）|
| host | `fw01` | 明確 |
| product 標識 | `PAN-OS` | 明確（出現在 message body）|
| serial number | `007901000123` | 推測（PAN-OS CSV 第 3 欄通常是 SN）|
| action | `TRAFFIC end` | 推測（PAN-OS CSV 慣例）|
| src_ip | `10.0.1.5` | 推測（無 header 標籤，依位置）|
| dst_ip | `8.8.8.8` | 推測（同上）|

異常：無。`8.8.8.8` 是 Google DNS、`10.0.1.5` 是私網，方向合理。
"""

_BLOCK1_NO_SKILL = """
# No active skill

The user opened Copilot without a page context. Answer general log / VRL /
security questions briefly and helpfully.
"""

_BLOCK1_VRL_GENERATE = """
# Skill: vrl_generate

You are generating VRL (Vector Remap Language) parse rules. The user has
raw logs in <logs> and possibly partial VRL in <current_vrl>.

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

## Process (follow in order)

1. Read <logs>; identify FORMAT (json / syslog / cef / leef / kv / csv /
   plain text). Cite the structural cue.
2. List the fields you will extract. State each field's source position
   (json path / regex group / csv index / split index).
3. Write VRL in EXACTLY ONE ```vrl ... ``` fenced block. The block must
   be a complete, compilable program — the user will copy it as-is into
   the editor.
4. After the code block, list edge cases:
   - which fields can be missing on some lines (and what your fallback
     returns)
   - which engine version this targets
   - what was intentionally NOT extracted

## You must NOT

- Invent fields not visibly present in <logs>.
- Invent VRL function names. Stick to the cheatsheet above; if you need
  something not listed, say so in prose and skip that field.
- Hard-code API keys, tokens, passwords, or production hostnames.
  Use `del()` if a sensitive field needs removal.
- Output more than one ```vrl block. If you want to show alternatives,
  describe them in prose; pick one canonical version for the block.
- Use a function returning `Result` without `!` or `??`. That is a
  compile error.

## Example A — syslog + PAN-OS CSV

INPUT <logs>:
  <log index="1"><![CDATA[<134>Jan 15 10:23:45 fw01 1,2024/01/15 10:23:45,007901000123,TRAFFIC,end,2049,10.0.1.5,8.8.8.8]]></log>

OUTPUT:

這是 syslog header 包 PAN-OS CSV body。先 `parse_syslog!` 抓
hostname/timestamp，再 `split` message 處理 CSV 段；CSV 欄位數會因
log_subtype 而異，所以後面索引用 `?? null` fallback。

```vrl
. = parse_syslog!(.message)
parts = split(string!(.message), ",")
.serial    = parts[2] ?? null
.log_type  = parts[3] ?? null
.action    = parts[4] ?? null
.src_ip    = parts[6] ?? null
.dst_ip    = parts[7] ?? null
```

注意：
- `?? null` 確保某些 log_subtype 欄位較少時不會 abort 整筆 event
- 此版本針對 engine 0.32；0.25 將 `string!` 改 `to_string!` 即可

## Example B — JSON

INPUT <logs>:
  <log index="1"><![CDATA[{"ts":"2024-01-15T10:23:45Z","user":"alice","action":"login","src_ip":"10.0.1.5"}]]></log>

OUTPUT:

JSON 格式，`parse_json!` 直接展開到 root，再把 `.ts` 轉成 timestamp：

```vrl
. = parse_json!(.message)
.timestamp = to_timestamp!(.ts, "%Y-%m-%dT%H:%M:%SZ")
del(.ts)
```

注意：
- 假設所有 logs 都是 JSON；若樣本中有 plain text 行請改 `parse_json(...) ?? {}`
- `del(.ts)` 用 .timestamp 取代原欄位，保持 schema 一致
"""

_SKILL_BLOCKS: dict[str, str] = {
    "log_explain":  _BLOCK1_LOG_EXPLAIN,
    "vrl_generate": _BLOCK1_VRL_GENERATE,
}


def _build_block1(skill: str | None) -> str:
    if skill is None:
        return _BLOCK1_PERSONA + _BLOCK1_NO_SKILL
    block = _SKILL_BLOCKS.get(skill)
    if block is None:
        # schema validation already restricts skill, defensive fallback
        return _BLOCK1_PERSONA + _BLOCK1_NO_SKILL
    return _BLOCK1_PERSONA + block


def _render_analyzer_xml(
    ctx,
    *,
    max_log_lines: int,
    max_vrl_chars: int,
) -> str:
    """Render AnalyzerPageContext as XML for prompt block 2.

    Uses CDATA for raw log lines and VRL content; quoteattr for attributes.
    Hypotheses block always renders (empty if no candidate) so the LLM sees
    the structure. Sections that have no data are omitted entirely.
    """
    lines: list[str] = []
    lines.append(f'<page_context page="{ctx.page}">')

    # facts
    vrl_lines_n = ctx.vrl.count("\n") + 1 if ctx.vrl else 0
    parse_ok = sum(1 for r in ctx.parse_results if r.status == "ok")
    parse_err = sum(1 for r in ctx.parse_results if r.status == "error")
    engine = ctx.vrl_engine or "unknown"
    lines.append("  <facts>")
    lines.append(f"    <vrl_lines>{vrl_lines_n}</vrl_lines>")
    lines.append(f"    <vrl_engine>{engine}</vrl_engine>")
    lines.append(f"    <log_count>{len(ctx.logs)}</log_count>")
    lines.append(f'    <parse_summary ok="{parse_ok}" error="{parse_err}"/>')
    lines.append("  </facts>")

    # hypotheses
    lines.append("  <hypotheses>")
    if ctx.match_top_candidate is not None:
        m = ctx.match_top_candidate
        lines.append(
            f'    <match_candidate source="MatchBar" '
            f'vendor="{m.vendor_slug}" product="{m.product_slug}" '
            f'log_type="{m.log_type_name}" confidence="{m.confidence:.2f}"/>'
        )
    lines.append("  </hypotheses>")

    # logs
    if ctx.logs:
        showing = min(len(ctx.logs), max_log_lines)
        lines.append(f'  <logs count="{len(ctx.logs)}" showing="{showing}">')
        for i, raw in enumerate(ctx.logs[:max_log_lines]):
            safe = _safe_cdata(raw)
            lines.append(f'    <log index="{i + 1}"><![CDATA[{safe}]]></log>')
        lines.append("  </logs>")

    # current_vrl
    if ctx.vrl:
        if len(ctx.vrl) > max_vrl_chars:
            truncated = ctx.vrl[:max_vrl_chars]
            attr = f' truncated_to="{max_vrl_chars}"'
            content = truncated
        else:
            attr = ""
            content = ctx.vrl
        safe_vrl = _safe_cdata(content)
        lines.append(f"  <current_vrl{attr}>")
        lines.append(f"    <![CDATA[{safe_vrl}]]>")
        lines.append("  </current_vrl>")

    # parse_results — render 1-based index to match <log index="1"> rendering
    # above (backend ParseResultItem.index is 0-based; LLM cannot otherwise
    # cross-reference a failing parse_result back to its log line).
    if ctx.parse_results:
        lines.append("  <parse_results>")
        for r in ctx.parse_results:
            if r.status == "error":
                msg_attr = f" message={quoteattr(r.message or '')}"
            else:
                msg_attr = ""
            lines.append(
                f'    <result index="{r.index + 1}" status="{r.status}"{msg_attr}/>'
            )
        lines.append("  </parse_results>")

    lines.append("</page_context>")
    return "\n".join(lines)


def _render_library_overview_xml(ctx, *, max_products: int) -> str:
    """Render LibraryOverviewPageContext as XML."""
    lines = ['<page_context page="library_overview">']
    lines.append("  <facts>")

    # filters renders only non-None values; quoteattr handles quotes safely
    filter_attrs = " ".join(
        f"{k}={quoteattr(v)}"
        for k, v in (ctx.filters or {}).items()
        if v is not None
    )
    if filter_attrs:
        lines.append(f"    <filters {filter_attrs}/>")
    else:
        lines.append("    <filters/>")

    lines.append(f"    <vendor_count>{ctx.vendor_count}</vendor_count>")
    lines.append(f"    <product_count>{ctx.product_count}</product_count>")
    lines.append("  </facts>")

    missing = ctx.products_missing_parse_rule or []
    showing = min(len(missing), max_products)
    lines.append(
        f'  <products_missing_parse_rule count="{len(missing)}" showing="{showing}">'
    )
    for slug in missing[:max_products]:
        lines.append(f"    <product slug={quoteattr(slug)}/>")
    lines.append("  </products_missing_parse_rule>")

    lines.append("</page_context>")
    return "\n".join(lines)


def _render_library_product_xml(ctx, *, max_vrl_chars: int) -> str:
    """Render LibraryProductPageContext as XML."""
    lines = ['<page_context page="library_product">']
    lines.append("  <facts>")
    lines.append(f"    <vendor_slug>{ctx.vendor_slug}</vendor_slug>")
    lines.append(f"    <product_slug>{ctx.product_slug}</product_slug>")
    lines.append(f"    <product_status>{ctx.product_status}</product_status>")
    lines.append("  </facts>")

    if ctx.active_log_type is not None:
        alt = ctx.active_log_type
        lines.append(f"  <active_log_type name={quoteattr(alt.name)}>")
        lines.append(f'    <fields count="{len(alt.fields)}">')
        for f in alt.fields:
            lines.append(
                f"      <field name={quoteattr(f.name)} type={quoteattr(f.type)} "
                f'required="{str(f.required).lower()}"/>'
            )
        lines.append("    </fields>")
        lines.append(f"    <samples_count>{alt.samples_count}</samples_count>")
        if alt.parse_rule_head:
            head = alt.parse_rule_head
            if len(head) > max_vrl_chars:
                attr = f' truncated_to="{max_vrl_chars}"'
                head = head[:max_vrl_chars]
            else:
                attr = ""
            lines.append(f"    <parse_rule_head{attr}>")
            lines.append(f"      <![CDATA[{_safe_cdata(head)}]]>")
            lines.append("    </parse_rule_head>")
        lines.append("  </active_log_type>")

    lines.append("</page_context>")
    return "\n".join(lines)


def _render_library_versions_xml(ctx, *, max_vrl_chars: int) -> str:
    """Render LibraryVersionsPageContext as XML."""
    lines = ['<page_context page="library_versions">']
    lines.append("  <facts>")
    lines.append(f"    <vendor_slug>{ctx.vendor_slug}</vendor_slug>")
    lines.append(f"    <product_slug>{ctx.product_slug}</product_slug>")
    lines.append(f"    <log_type_name>{ctx.log_type_name}</log_type_name>")
    lines.append("  </facts>")

    if ctx.diff is not None:
        d = ctx.diff
        lines.append(
            f"  <diff base_version={quoteattr(d.base_version)} "
            f"head_version={quoteattr(d.head_version)}>"
        )
        for label, body in (("base_vrl", d.base_vrl), ("head_vrl", d.head_vrl)):
            if body is None:
                continue
            if len(body) > max_vrl_chars:
                attr = f' truncated_to="{max_vrl_chars}"'
                body = body[:max_vrl_chars]
            else:
                attr = ""
            lines.append(f"    <{label}{attr}>")
            lines.append(f"      <![CDATA[{_safe_cdata(body)}]]>")
            lines.append(f"    </{label}>")
        lines.append("  </diff>")

    lines.append("</page_context>")
    return "\n".join(lines)


def _render_page_context_xml(
    ctx: PageContext,
    *,
    max_log_lines: int,
    max_vrl_chars: int,
    max_library_products: int,
) -> str:
    """Dispatch PageContext to the appropriate per-page renderer."""
    page = ctx.page
    if page == "analyzer":
        return _render_analyzer_xml(
            ctx, max_log_lines=max_log_lines, max_vrl_chars=max_vrl_chars,
        )
    if page == "library_overview":
        return _render_library_overview_xml(ctx, max_products=max_library_products)
    if page == "library_product":
        return _render_library_product_xml(ctx, max_vrl_chars=max_vrl_chars)
    if page == "library_versions":
        return _render_library_versions_xml(ctx, max_vrl_chars=max_vrl_chars)
    raise ValueError(f"unknown page: {page}")


def build_system_blocks(
    *,
    skill: str | None,
    page_context: PageContext | None,
    max_log_lines: int,
    max_vrl_chars: int,
    max_library_products: int,
) -> list[dict]:
    """Return Anthropic `system` parameter as a list of TextBlockParam dicts.

    Block 1: persona + skill instruction (cache_control: ephemeral).
    Block 2: <page_context> XML (no cache, omitted when page_context is None).
    """
    blocks: list[dict] = [
        {
            "type": "text",
            "text": _build_block1(skill),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if page_context is not None:
        blocks.append(
            {
                "type": "text",
                "text": _render_page_context_xml(
                    page_context,
                    max_log_lines=max_log_lines,
                    max_vrl_chars=max_vrl_chars,
                    max_library_products=max_library_products,
                ),
            }
        )
    return blocks
