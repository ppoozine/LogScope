"""Prompt construction for E2 draft generation."""

from dataclasses import dataclass
from xml.sax.saxutils import quoteattr

from app.modules.copilot.services._vrl_cheatsheet import VRL_CHEATSHEET

DRAFT_TOOL_SCHEMA: dict = {
    "name": "submit_draft",
    "description": (
        "Submit a single LogType draft (metadata + fields + VRL parse rule) "
        "extracted from the vendor doc. Call this exactly once per request."
    ),
    "input_schema": {
        "type": "object",
        "required": ["log_type", "fields", "vrl_code", "engine_version", "notes"],
        "properties": {
            "log_type": {
                "type": "object",
                "required": ["name", "format"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 200},
                    "format": {
                        "type": "string",
                        "enum": ["syslog", "json", "cef", "leef", "csv", "other"],
                    },
                    "transport": {
                        "type": "string",
                        "enum": ["syslog_udp", "syslog_tcp", "http", "file", "other"],
                    },
                    "description": {"type": "string", "maxLength": 1000},
                },
            },
            "fields": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "required": ["field_name", "field_type"],
                    "properties": {
                        "field_name": {"type": "string", "minLength": 1, "maxLength": 100},
                        "field_type": {
                            "type": "string",
                            "enum": ["string", "int", "float", "bool", "timestamp", "ip", "object", "array"],
                        },
                        "description": {"type": "string"},
                        "is_required": {"type": "boolean", "default": False},
                        "is_identifier": {"type": "boolean", "default": False},
                        "example_value": {"type": "string"},
                    },
                },
            },
            "vrl_code": {"type": "string", "minLength": 1},
            "engine_version": {"type": "string", "enum": ["0.25", "0.32"], "default": "0.32"},
            "notes": {
                "type": "string",
                "description": "Reviewer-facing notes — what was uncertain, alternative interpretations, fields not extracted",
                "maxLength": 2000,
            },
        },
    },
}


BLOCK1_TEXT = f"""You are LogScope's library builder.

Your job: read a vendor doc and propose ONE LogType draft via the `submit_draft` tool.

# Output rules
- No prose response. Submit only via the `submit_draft` tool.
- Do NOT invent fields not described in the doc.
- snake_case field names matching the convention in <existing_log_types>.
- For each field whose meaning you inferred (rather than the doc stated literally),
  end its `description` with one of: 〔依據：明確〕〔依據：推測〕〔依據：未知〕
  (sourced from D-series Copilot conventions).

# Process (follow in order)
1. Identify the LogType in the doc. If the doc covers multiple subtypes, pick
   the one matching <hint>. Otherwise pick the first / most prominent.
2. List fields with: source position in doc / VRL extraction strategy / type.
3. Write VRL targeting `engine_version` (default 0.32; if doc indicates older
   syntax or hint specifies, use 0.25).
4. Cross-check: every field in `fields[]` must be assigned in `vrl_code`
   OR the VRL must use a splat-style assign (`. = parse_json!(...)`,
   `. = parse_syslog!(...)`, `. = parse_key_value!(...)`); every field assigned
   in `vrl_code` must appear in `fields[]`.

{VRL_CHEATSHEET}

# You must NOT
- Invent fields not visibly described in the doc.
- Invent VRL function names. Stick to the cheatsheet above.
- Hard-code secrets / tokens / production hostnames into the VRL.
- Split the same conceptual field into two `fields[]` entries.

# Uncertainty handling
If the doc is ambiguous about a field, write `notes` like
"無法確定 X：<原因>" — submit a smaller fields[] rather than guessing.

# Example — PAN-OS TRAFFIC log

INPUT (excerpt of <doc>):
> PAN-OS TRAFFIC log format (CSV after syslog header):
>   FUTURE_USE,Receive Time,Serial Number,Type,Threat/Content Type,FUTURE_USE,
>   Source IP,Destination IP,...

OUTPUT (tool call):
{{
  "log_type": {{
    "name": "PAN-OS TRAFFIC",
    "format": "syslog",
    "transport": "syslog_udp",
    "description": "Palo Alto traffic logs (CSV body inside syslog)"
  }},
  "fields": [
    {{"field_name": "serial",   "field_type": "string", "is_identifier": true,  "description": "PAN serial 〔依據：明確〕"}},
    {{"field_name": "log_type", "field_type": "string", "description": "PAN log subtype 〔依據：明確〕"}},
    {{"field_name": "src_ip",   "field_type": "ip", "is_required": true, "description": "source IP 〔依據：明確〕"}},
    {{"field_name": "dst_ip",   "field_type": "ip", "is_required": true, "description": "destination IP 〔依據：明確〕"}}
  ],
  "vrl_code": ". = parse_syslog!(.message)\\nparts = split(string!(.message), \\",\\")\\n.serial   = parts[2] ?? null\\n.log_type = parts[3] ?? null\\n.src_ip   = parts[6] ?? null\\n.dst_ip   = parts[7] ?? null",
  "engine_version": "0.32",
  "notes": "PAN CSV column count varies by subtype — used `?? null` fallback."
}}
"""


def _safe_cdata(text: str) -> str:
    """Escape ``]]>`` sequences so a CDATA section can wrap the text."""
    return text.replace("]]>", "]]]]><![CDATA[>")


DOC_TRUNCATE_CHARS = 20_000


@dataclass(frozen=True)
class FieldView:
    name: str
    type: str
    required: bool = False


@dataclass(frozen=True)
class ExistingLogTypeView:
    name: str
    format: str
    transport: str | None
    fields: list[FieldView]


@dataclass(frozen=True)
class DraftPromptContext:
    vendor_name: str
    vendor_slug: str
    product_name: str
    product_slug: str
    product_version: str | None
    product_deploy_type: str | None
    existing_log_types: list[ExistingLogTypeView]
    doc_title: str | None
    doc_url: str | None
    doc_content: str
    hint: str | None


def render_block2_xml(ctx: DraftPromptContext) -> str:
    lines: list[str] = []
    lines.append(
        f'<vendor name={quoteattr(ctx.vendor_name)} '
        f'slug={quoteattr(ctx.vendor_slug)} />'
    )
    product_attrs = [
        f'name={quoteattr(ctx.product_name)}',
        f'slug={quoteattr(ctx.product_slug)}',
    ]
    if ctx.product_version:
        product_attrs.append(f'version={quoteattr(ctx.product_version)}')
    if ctx.product_deploy_type:
        product_attrs.append(f'deploy_type={quoteattr(ctx.product_deploy_type)}')
    lines.append(f'<product {" ".join(product_attrs)} />')

    lines.append("")
    lines.append(f'<existing_log_types count="{len(ctx.existing_log_types)}">')
    for elt in ctx.existing_log_types:
        attrs = [f'name={quoteattr(elt.name)}', f'format={quoteattr(elt.format)}']
        if elt.transport:
            attrs.append(f'transport={quoteattr(elt.transport)}')
        lines.append(f'  <log_type {" ".join(attrs)}>')
        lines.append("    <fields>")
        for f in elt.fields:
            lines.append(
                f'      <field name={quoteattr(f.name)} '
                f'type={quoteattr(f.type)} required="{str(f.required).lower()}" />'
            )
        lines.append("    </fields>")
        lines.append("  </log_type>")
    lines.append("</existing_log_types>")

    lines.append("")
    doc_attrs = []
    if ctx.doc_title:
        doc_attrs.append(f'title={quoteattr(ctx.doc_title)}')
    if ctx.doc_url:
        doc_attrs.append(f'url={quoteattr(ctx.doc_url)}')
    content = ctx.doc_content
    if len(content) > DOC_TRUNCATE_CHARS:
        content = content[:DOC_TRUNCATE_CHARS]
        doc_attrs.append(f'truncated_to="{DOC_TRUNCATE_CHARS}"')
    lines.append(f"<doc {' '.join(doc_attrs)}>" if doc_attrs else "<doc>")
    lines.append(f"  <![CDATA[{_safe_cdata(content)}]]>")
    lines.append("</doc>")

    if ctx.hint:
        lines.append("")
        lines.append(f"<hint><![CDATA[{_safe_cdata(ctx.hint)}]]></hint>")

    return "\n".join(lines)


def build_system_blocks(ctx: DraftPromptContext) -> list[dict]:
    """Return Anthropic `system` parameter as 2 TextBlockParam dicts.

    Block 1: cached persona+skill+cheatsheet+example.
    Block 2: per-request XML context.
    """
    return [
        {
            "type": "text",
            "text": BLOCK1_TEXT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": render_block2_xml(ctx),
        },
    ]
