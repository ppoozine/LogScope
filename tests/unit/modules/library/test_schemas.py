import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.library.schemas import LogTypeRead, ParseRuleRead


class TestStatusEnumExtensions:
    def test_log_type_status_accepts_llm_draft(self):
        lt = LogTypeRead.model_validate({
            "id": uuid.uuid4(), "product_id": uuid.uuid4(),
            "name": "x", "slug": "x", "format": "json", "transport": None,
            "status": "llm_draft", "source": "llm_generated",
            "current_parse_rule_id": None, "description": None,
            "published_at": None,
            "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
        })
        assert lt.status == "llm_draft"
        assert lt.source == "llm_generated"

    def test_log_type_source_rejects_unknown(self):
        with pytest.raises(ValidationError):
            LogTypeRead.model_validate({
                "id": uuid.uuid4(), "product_id": uuid.uuid4(),
                "name": "x", "slug": "x", "format": "json", "transport": None,
                "status": "draft", "source": "stolen",
                "current_parse_rule_id": None, "description": None,
                "published_at": None,
                "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
            })

    def test_parse_rule_status_accepts_llm_draft(self):
        pr = ParseRuleRead.model_validate({
            "id": uuid.uuid4(), "log_type_id": uuid.uuid4(), "version": 1,
            "vrl_code": ". = parse_json!(.message)",
            "engine_version": "0.32",
            "status": "llm_draft",
            "source": "llm_generated",
            "notes": None,
            "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
        })
        assert pr.status == "llm_draft"
        assert pr.source == "llm_generated"

    def test_parse_rule_source_literal_value_check(self):
        # Verify the new ParseRuleSource literal alias exists with both values
        from typing import get_args

        from app.modules.library.schemas import ParseRuleSource
        assert set(get_args(ParseRuleSource)) == {"manual", "llm_generated"}
