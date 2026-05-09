"""Pydantic schema validation for Copilot."""

import pytest
from pydantic import ValidationError

from app.modules.copilot.schemas import (
    ChatMessage,
    ChatRequest,
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
