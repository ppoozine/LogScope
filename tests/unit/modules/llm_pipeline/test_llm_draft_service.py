from types import SimpleNamespace

from app.modules.llm_pipeline.services.llm_draft_service import (
    _serialize_response,
    _truncate_response,
)


class TestTruncateResponse:
    def test_short_kept(self):
        assert _truncate_response("abc", 4) == "abc"

    def test_long_truncated(self):
        assert _truncate_response("a" * 100, 10) == "a" * 10

    def test_none_returns_none(self):
        assert _truncate_response(None, 10) is None


class TestSerializeResponse:
    def test_uses_model_dump_when_available(self):
        r = SimpleNamespace(model_dump=lambda: {"id": "x"})
        out = _serialize_response(r)
        assert '"id"' in out and '"x"' in out

    def test_uses_to_dict_when_available(self):
        r = SimpleNamespace(to_dict=lambda: {"id": "y"})
        out = _serialize_response(r)
        assert '"id"' in out and '"y"' in out

    def test_falls_back_to_str(self):
        r = "raw string"
        assert _serialize_response(r) == "raw string"
