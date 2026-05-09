"""Unit tests for ParseRuleService.promote() — covers 4 state transitions."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.services.parse_rule_service import ParseRuleService


def _rule(*, status: str, log_type_id=None, rid=None) -> ParseRule:
    r = ParseRule()
    r.id = rid or uuid.uuid4()
    r.log_type_id = log_type_id or uuid.uuid4()
    r.version = 1
    r.vrl_code = "."
    r.engine_version = "0.32"
    r.status = status
    return r


def _log_type(rule_id) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
    lt.name = "LT"
    lt.slug = "lt"
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = rule_id
    return lt


async def test_promote_not_found_raises():
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=None)
    log_types_repo = AsyncMock()
    svc = ParseRuleService(rules_repo, log_types_repo)
    with pytest.raises(NotFoundError):
        await svc.promote(uuid.uuid4())


async def test_promote_archived_raises_conflict():
    target = _rule(status="archived")
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    svc = ParseRuleService(rules_repo, AsyncMock())
    with pytest.raises(ConflictError):
        await svc.promote(target.id)


async def test_promote_already_published_returns_idempotent():
    target = _rule(status="published")
    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    svc = ParseRuleService(rules_repo, AsyncMock())
    out = await svc.promote(target.id)
    assert out is target
    rules_repo.update.assert_not_awaited()


async def test_promote_draft_with_no_existing_published_sets_log_type():
    lt_id = uuid.uuid4()
    target = _rule(status="draft", log_type_id=lt_id)
    lt = _log_type(rule_id=target.id)
    lt.id = lt_id

    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    rules_repo.get_current_published = AsyncMock(return_value=None)

    log_types_repo = AsyncMock()
    log_types_repo.get_by_id = AsyncMock(return_value=lt)

    svc = ParseRuleService(rules_repo, log_types_repo)
    out = await svc.promote(target.id)

    assert out.status == "published"
    rules_repo.update.assert_awaited_once_with(target)
    assert lt.current_parse_rule_id == target.id
    assert lt.status == "published"
    assert lt.published_at is not None
    log_types_repo.update.assert_awaited_once_with(lt)


async def test_promote_draft_archives_previous_published():
    lt_id = uuid.uuid4()
    target = _rule(status="draft", log_type_id=lt_id)
    old = _rule(status="published", log_type_id=lt_id)
    lt = _log_type(rule_id=target.id)
    lt.id = lt_id
    lt.status = "published"

    rules_repo = AsyncMock()
    rules_repo.get_for_update = AsyncMock(return_value=target)
    rules_repo.get_current_published = AsyncMock(return_value=old)

    log_types_repo = AsyncMock()
    log_types_repo.get_by_id = AsyncMock(return_value=lt)

    svc = ParseRuleService(rules_repo, log_types_repo)
    out = await svc.promote(target.id)

    assert out.status == "published"
    assert old.status == "archived"
    # both updates called: archive old and publish target
    assert rules_repo.update.await_count == 2
    assert lt.current_parse_rule_id == target.id
