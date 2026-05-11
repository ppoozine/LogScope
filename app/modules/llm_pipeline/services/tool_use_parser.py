"""Parse Anthropic tool_use response into typed DraftPayload."""
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.modules.llm_pipeline.exceptions import (
    SchemaMismatchError,
    VrlFieldsDisjointError,
)

# Pydantic models for input_schema validation (mirrors DRAFT_TOOL_SCHEMA).
# Underscore prefix marks these as module-internal; tests import them by name
# to construct fixtures, which is the documented pattern for this module.


class _LogTypeMeta(BaseModel):
    name: str
    format: Literal["syslog", "json", "cef", "leef", "csv", "other"]
    transport: Literal[
        "syslog_udp", "syslog_tcp", "http", "file", "other"
    ] | None = None
    description: str | None = None


class _Field(BaseModel):
    field_name: str
    field_type: Literal[
        "string", "int", "float", "bool", "timestamp", "ip", "object", "array"
    ]
    description: str | None = None
    is_required: bool = False
    is_identifier: bool = False
    example_value: str | None = None


class _ToolInput(BaseModel):
    log_type: _LogTypeMeta
    # min_length=1 mirrors DRAFT_TOOL_SCHEMA's minItems=1 server-side, so even
    # if the LLM ignores the schema (or a future SDK strips constraints) we
    # reject empty fields up front rather than depending on the downstream
    # self-consistency check.
    fields: list[_Field] = Field(min_length=1)
    vrl_code: str
    engine_version: Literal["0.25", "0.32"] = "0.32"
    notes: str = ""


@dataclass(frozen=True)
class DraftPayload:
    log_type: _LogTypeMeta
    fields: list[_Field]
    vrl_code: str
    engine_version: str
    notes: str


def parse_tool_use(response: Any) -> DraftPayload:
    """Extract the single submit_draft tool call from an Anthropic response.

    Raises:
        SchemaMismatchError if structure is wrong.
    """
    blocks = getattr(response, "content", None) or []
    tool_blocks = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
    if len(tool_blocks) != 1:
        raise SchemaMismatchError(
            f"expected 1 tool_use block, got {len(tool_blocks)}"
        )
    block = tool_blocks[0]
    if getattr(block, "name", None) != "submit_draft":
        raise SchemaMismatchError(
            f"expected tool name 'submit_draft', got {getattr(block, 'name', None)!r}"
        )
    raw_input = getattr(block, "input", None) or {}
    try:
        validated = _ToolInput.model_validate(raw_input)
    except ValidationError as e:
        raise SchemaMismatchError(str(e)) from e
    return DraftPayload(
        log_type=validated.log_type,
        fields=validated.fields,
        vrl_code=validated.vrl_code,
        engine_version=validated.engine_version,
        notes=validated.notes,
    )


_SPLAT_PATTERNS = (
    ". = parse_json!",
    ". = parse_syslog!",
    ". = parse_key_value!",
    ". = parse_kv!",
)
_INLINE_SENTINELS = ("<|cursor|>", "<|sel_start|>", "<|sel_end|>")


def check_self_consistency(draft: DraftPayload) -> None:
    """Run service-layer checks before VRL compile.

    Raises:
        SchemaMismatchError if vrl_code contains inline sentinels.
        VrlFieldsDisjointError if no field_name appears in vrl_code AND
            vrl_code does not use splat-style assignment.
    """
    vrl = draft.vrl_code
    for sentinel in _INLINE_SENTINELS:
        if sentinel in vrl:
            raise SchemaMismatchError(
                f"vrl_code contains inline sentinel: {sentinel}"
            )
    has_splat = any(p in vrl for p in _SPLAT_PATTERNS)
    if has_splat:
        return
    field_names = {f.field_name for f in draft.fields}
    if not any(name in vrl for name in field_names):
        raise VrlFieldsDisjointError(
            "no field_name appears in vrl_code and no splat-assign is used"
        )
