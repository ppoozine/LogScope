"""ParseRequest accepts optional log_type_id / parse_rule_id."""

import uuid

from app.modules.analyzer.schemas import ParseRequest


def test_parse_request_accepts_no_context():
    req = ParseRequest(vrl_code=".x = 1", logs=["a"], engine_version="0.32")
    assert req.log_type_id is None
    assert req.parse_rule_id is None


def test_parse_request_accepts_log_type_and_rule_ids():
    lt = uuid.uuid4()
    rule = uuid.uuid4()
    req = ParseRequest(
        vrl_code=".x = 1",
        logs=["a"],
        engine_version="0.32",
        log_type_id=lt,
        parse_rule_id=rule,
    )
    assert req.log_type_id == lt
    assert req.parse_rule_id == rule
