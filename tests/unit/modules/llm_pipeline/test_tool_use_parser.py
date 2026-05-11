from types import SimpleNamespace

import pytest

from app.modules.llm_pipeline.exceptions import (
    SchemaMismatchError,
    VrlFieldsDisjointError,
)
from app.modules.llm_pipeline.services.tool_use_parser import (
    DraftPayload,
    check_self_consistency,
    parse_tool_use,
)


def _resp_with_tool_use(tool_input: dict) -> SimpleNamespace:
    """Build a fake Anthropic Message-like object with one tool_use block."""
    block = SimpleNamespace(
        type="tool_use", name="submit_draft", id="t1", input=tool_input,
    )
    return SimpleNamespace(content=[block], stop_reason="tool_use")


_GOOD_PAYLOAD = {
    "log_type": {
        "name": "PAN-OS TRAFFIC",
        "format": "syslog",
        "transport": "syslog_udp",
        "description": None,
    },
    "fields": [
        {
            "field_name": "src_ip", "field_type": "ip",
            "is_required": True, "is_identifier": False,
            "description": "src", "example_value": "10.0.0.1",
        },
    ],
    "vrl_code": ". = parse_syslog!(.message)\n.src_ip = parts[6] ?? null",
    "engine_version": "0.32",
    "notes": "ok",
}


class TestParseToolUse:
    def test_happy_path(self):
        resp = _resp_with_tool_use(_GOOD_PAYLOAD)
        d = parse_tool_use(resp)
        assert isinstance(d, DraftPayload)
        assert d.log_type.name == "PAN-OS TRAFFIC"
        assert len(d.fields) == 1
        assert d.engine_version == "0.32"

    def test_missing_tool_use_block_raises(self):
        resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            stop_reason="end_turn",
        )
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_wrong_tool_name_raises(self):
        block = SimpleNamespace(
            type="tool_use", name="other_tool", id="t1", input={},
        )
        resp = SimpleNamespace(content=[block], stop_reason="tool_use")
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_invalid_payload_shape_raises(self):
        bad = dict(_GOOD_PAYLOAD)
        del bad["fields"]
        resp = _resp_with_tool_use(bad)
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_two_tool_use_blocks_raises(self):
        block = SimpleNamespace(type="tool_use", name="submit_draft", id="t1", input=_GOOD_PAYLOAD)
        resp = SimpleNamespace(content=[block, block], stop_reason="tool_use")
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_empty_response_raises(self):
        resp = SimpleNamespace(content=[], stop_reason="end_turn")
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_empty_fields_list_raises(self):
        # Defense-in-depth: even if the LLM bypasses minItems, Pydantic
        # rejects fields=[] at parse time rather than letting it slip
        # through to the self-consistency or VRL-compile checks.
        bad = {**_GOOD_PAYLOAD, "fields": []}
        resp = _resp_with_tool_use(bad)
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)


class TestCheckSelfConsistency:
    def _draft(self, vrl: str, field_names: list[str]):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            DraftPayload,
            _Field,
            _LogTypeMeta,
        )
        return DraftPayload(
            log_type=_LogTypeMeta(name="x", format="json"),
            fields=[
                _Field(field_name=n, field_type="string") for n in field_names
            ],
            vrl_code=vrl,
            engine_version="0.32",
            notes="",
        )

    def test_field_name_in_vrl_passes(self):
        d = self._draft(".src_ip = parts[6] ?? null", ["src_ip"])
        check_self_consistency(d)  # no raise

    def test_no_field_in_vrl_raises(self):
        d = self._draft("x = 1", ["src_ip", "dst_ip"])
        with pytest.raises(VrlFieldsDisjointError):
            check_self_consistency(d)

    def test_splat_parse_json_passes_even_without_field_names(self):
        d = self._draft(". = parse_json!(.message)", ["src_ip", "dst_ip"])
        check_self_consistency(d)

    def test_splat_parse_syslog_passes(self):
        d = self._draft(". = parse_syslog!(.message)", ["timestamp"])
        check_self_consistency(d)

    def test_splat_parse_key_value_passes(self):
        d = self._draft(". = parse_key_value!(.message)", ["timestamp"])
        check_self_consistency(d)

    def test_splat_parse_kv_passes(self):
        # 0.25 syntax variant
        d = self._draft(". = parse_kv!(.message)", ["timestamp"])
        check_self_consistency(d)

    def test_inline_marker_raises_schema_mismatch(self):
        d = self._draft(".src_ip = <|cursor|> null", ["src_ip"])
        with pytest.raises(SchemaMismatchError):
            check_self_consistency(d)

    def test_inline_sel_start_raises(self):
        d = self._draft("<|sel_start|>... <|sel_end|>", ["src_ip"])
        with pytest.raises(SchemaMismatchError):
            check_self_consistency(d)
