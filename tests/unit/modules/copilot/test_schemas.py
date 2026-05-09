"""Pydantic schema validation for Copilot."""

import pytest
from pydantic import ValidationError

from app.modules.copilot.schemas import (
    ChatMessage,
    ChatRequest,
    PageContext,
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

    def test_invalid_skill_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest.model_validate(
                {
                    "messages": [{"role": "user", "content": "hi"}],
                    "skill": "vrl_gen",  # D1 only supports log_explain
                }
            )


class TestPageContext:
    def test_minimal_analyzer_context(self):
        ctx = PageContext(page="analyzer")
        assert ctx.page == "analyzer"
        assert ctx.vrl is None
        assert ctx.logs == []
        assert ctx.parse_results == []
        assert ctx.match_top_candidate is None

    def test_full_analyzer_context(self):
        ctx = PageContext.model_validate(
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
            PageContext.model_validate({"page": "library"})  # D1 only supports analyzer
