"""Pydantic schema validation for Copilot."""

import pytest
from pydantic import ValidationError

from app.modules.copilot.schemas import (
    ChatMessage,
    ChatRequest,
    InlineVrlRequest,
)


class TestChatMessage:
    def test_user_role_accepted(self):
        m = ChatMessage(role="user", content="hi")
        assert m.role == "user"

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage.model_validate({"role": "system", "content": "x"})


class TestChatRequest:
    def test_minimum_valid_request(self):
        r = ChatRequest.model_validate(
            {"messages": [{"role": "user", "content": "hi"}]}
        )
        assert len(r.messages) == 1
        assert r.skill is None
        assert r.page_context is None

    def test_empty_messages_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest.model_validate({"messages": []})

    def test_too_many_messages_rejected(self):
        many = [{"role": "user", "content": "x"}] * 41
        with pytest.raises(ValidationError):
            ChatRequest.model_validate({"messages": many})

    def test_skill_log_explain_accepted(self):
        r = ChatRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "skill": "log_explain",
            }
        )
        assert r.skill == "log_explain"

    def test_skill_vrl_generate_accepted(self):
        r = ChatRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "hi"}],
                "skill": "vrl_generate",
            }
        )
        assert r.skill == "vrl_generate"

    def test_skill_vrl_optimize_accepted(self):
        from app.modules.copilot.schemas import ChatRequest
        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            skill="vrl_optimize",
        )
        assert r.skill == "vrl_optimize"

    def test_skill_anomaly_accepted(self):
        from app.modules.copilot.schemas import ChatRequest
        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            skill="anomaly",
        )
        assert r.skill == "anomaly"

    def test_invalid_skill_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest.model_validate(
                {
                    "messages": [{"role": "user", "content": "hi"}],
                    "skill": "not_a_real_skill",
                }
            )


class TestPageContext:
    def test_minimal_analyzer_context(self):
        from app.modules.copilot.schemas import AnalyzerPageContext

        ctx = AnalyzerPageContext(page="analyzer")
        assert ctx.page == "analyzer"
        assert ctx.vrl is None
        assert ctx.logs == []
        assert ctx.parse_results == []
        assert ctx.match_top_candidate is None

    def test_full_analyzer_context(self):
        from app.modules.copilot.schemas import AnalyzerPageContext

        ctx = AnalyzerPageContext.model_validate(
            {
                "page": "analyzer",
                "vrl": ". = parse_syslog!(.message)",
                "vrl_engine": "v0.32",
                "logs": ["log a", "log b"],
                "parse_results": [
                    {"index": 1, "status": "ok"},
                    {"index": 2, "status": "error", "message": "field missing"},
                ],
                "match_top_candidate": {
                    "vendor_slug": "paloalto",
                    "product_slug": "pan-os",
                    "log_type_name": "Traffic",
                    "confidence": 0.94,
                },
            }
        )
        assert ctx.vrl_engine == "v0.32"
        assert len(ctx.parse_results) == 2
        assert ctx.match_top_candidate is not None
        assert ctx.match_top_candidate.confidence == 0.94

    def test_invalid_page_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[{"role": "user", "content": "hi"}],
                page_context={"page": "library"},  # not in 4 literals
            )


class TestDiscriminatedPageContext:
    def test_analyzer_page_context_still_works(self):
        from app.modules.copilot.schemas import ChatRequest

        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            page_context={"page": "analyzer", "logs": ["a"]},
        )
        assert r.page_context.page == "analyzer"

    def test_library_overview_page_context(self):
        from app.modules.copilot.schemas import ChatRequest

        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            page_context={
                "page": "library_overview",
                "filters": {"status": "published", "q": None},
                "vendor_count": 5,
                "product_count": 12,
                "products_missing_parse_rule": ["paloalto/panorama"],
            },
        )
        assert r.page_context.vendor_count == 5

    def test_library_overview_missing_required_field(self):
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[{"role": "user", "content": "hi"}],
                page_context={"page": "library_overview"},  # missing vendor_count etc.
            )

    def test_library_product_page_context(self):
        from app.modules.copilot.schemas import ChatRequest

        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            page_context={
                "page": "library_product",
                "vendor_slug": "paloalto",
                "product_slug": "pan-os",
                "product_status": "active",
                "active_log_type": {
                    "name": "traffic",
                    "fields": [{"name": "src_ip", "type": "string", "required": True}],
                    "samples_count": 5,
                    "parse_rule_head": ". = parse_syslog!(.message)",
                },
            },
        )
        assert r.page_context.active_log_type.name == "traffic"

    def test_library_versions_page_context(self):
        from app.modules.copilot.schemas import ChatRequest

        r = ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            page_context={
                "page": "library_versions",
                "vendor_slug": "paloalto",
                "product_slug": "pan-os",
                "log_type_name": "traffic",
                "diff": {
                    "base_version": "v3",
                    "head_version": "v4",
                    "base_vrl": "old",
                    "head_vrl": "new",
                },
            },
        )
        assert r.page_context.diff.head_version == "v4"

    def test_unknown_page_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[{"role": "user", "content": "hi"}],
                page_context={"page": "library"},  # not in 4 literals
            )


class TestInlineVrlRequest:
    def test_insert_mode_valid(self):
        r = InlineVrlRequest(
            instruction="加 dst_ip",
            mode="insert",
            current_vrl=". = parse_syslog!(.message)",
            cursor_offset=10,
            vrl_engine="0.32",
            logs=["log1"],
        )
        assert r.mode == "insert"
        assert r.cursor_offset == 10

    def test_insert_mode_missing_cursor_offset(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="insert",
                current_vrl="abc",
                # cursor_offset omitted
            )

    def test_insert_mode_cursor_offset_out_of_range(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="insert",
                current_vrl="abc",        # length 3
                cursor_offset=99,
            )

    def test_replace_mode_valid(self):
        r = InlineVrlRequest(
            instruction="改用 parse_regex",
            mode="replace",
            current_vrl="abcdefghij",
            selection_start=2,
            selection_end=5,
        )
        assert r.mode == "replace"
        assert r.selection_start == 2
        assert r.selection_end == 5

    def test_replace_mode_start_ge_end(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="replace",
                current_vrl="abcdefghij",
                selection_start=5,
                selection_end=5,
            )

    def test_replace_mode_end_out_of_range(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="replace",
                current_vrl="abc",
                selection_start=0,
                selection_end=99,
            )

    def test_empty_instruction_rejected(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="",
                mode="insert",
                current_vrl="",
                cursor_offset=0,
            )

    def test_empty_current_vrl_with_cursor_zero_ok(self):
        r = InlineVrlRequest(
            instruction="寫一段 syslog parser",
            mode="insert",
            current_vrl="",
            cursor_offset=0,
        )
        assert r.cursor_offset == 0

    def test_logs_cap(self):
        # 51 logs should be rejected (max_length=50)
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="insert",
                current_vrl="",
                cursor_offset=0,
                logs=["l"] * 51,
            )

    def test_current_vrl_too_long(self):
        # 50001 chars should be rejected
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="insert",
                current_vrl="a" * 50_001,
                cursor_offset=0,
            )

    def test_invalid_engine_rejected(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                mode="insert",
                current_vrl="",
                cursor_offset=0,
                vrl_engine="0.99",
            )

    def test_default_skill_is_vrl_inline(self):
        r = InlineVrlRequest(
            instruction="x",
            mode="insert",
            current_vrl="",
            cursor_offset=0,
        )
        assert r.skill == "vrl_inline"

    def test_vrl_fix_valid_request(self):
        r = InlineVrlRequest(
            instruction="Fix this",
            skill="vrl_fix",
            mode="replace",
            current_vrl="abcdefghij",
            selection_start=2,
            selection_end=5,
            compile_error="error[E110]: ...",
        )
        assert r.skill == "vrl_fix"
        assert r.compile_error == "error[E110]: ..."

    def test_vrl_fix_missing_compile_error(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                skill="vrl_fix",
                mode="replace",
                current_vrl="abcdefghij",
                selection_start=2,
                selection_end=5,
                # compile_error omitted
            )

    def test_vrl_fix_blank_compile_error(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                skill="vrl_fix",
                mode="replace",
                current_vrl="abcdefghij",
                selection_start=2,
                selection_end=5,
                compile_error="   ",
            )

    def test_vrl_fix_requires_replace_mode(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                skill="vrl_fix",
                mode="insert",
                current_vrl="abcdefghij",
                cursor_offset=0,
                compile_error="error[E110]: ...",
            )

    def test_vrl_fix_compile_error_too_long(self):
        with pytest.raises(ValidationError):
            InlineVrlRequest(
                instruction="x",
                skill="vrl_fix",
                mode="replace",
                current_vrl="abcdefghij",
                selection_start=2,
                selection_end=5,
                compile_error="x" * 20_001,
            )
