"""Build Anthropic system blocks for Copilot."""

from typing import Literal
from xml.sax.saxutils import quoteattr

from app.modules.copilot.schemas import PageContext


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


def _build_block1(skill: Literal["log_explain"] | None) -> str:
    if skill == "log_explain":
        return _BLOCK1_PERSONA + _BLOCK1_LOG_EXPLAIN
    return _BLOCK1_PERSONA + _BLOCK1_NO_SKILL


def _render_page_context_xml(
    ctx: PageContext,
    *,
    max_log_lines: int,
    max_vrl_chars: int,
) -> str:
    """Render PageContext as a single XML string for prompt block 2.

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
            safe = raw.replace("]]>", "]]]]><![CDATA[>")
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
        safe_vrl = content.replace("]]>", "]]]]><![CDATA[>")
        lines.append(f"  <current_vrl{attr}>")
        lines.append(f"    <![CDATA[{safe_vrl}]]>")
        lines.append("  </current_vrl>")

    # parse_results
    if ctx.parse_results:
        lines.append("  <parse_results>")
        for r in ctx.parse_results:
            if r.status == "error":
                msg_attr = f" message={quoteattr(r.message or '')}"
            else:
                msg_attr = ""
            lines.append(
                f'    <result index="{r.index}" status="{r.status}"{msg_attr}/>'
            )
        lines.append("  </parse_results>")

    lines.append("</page_context>")
    return "\n".join(lines)
