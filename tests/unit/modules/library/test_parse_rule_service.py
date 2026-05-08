import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.schemas import ParseRuleCreate, ParseRuleUpdate
from app.modules.library.services.parse_rule_service import ParseRuleService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.status = "draft"
    return lt


def _make_rule(*, status: str = "draft", version: int = 1) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = uuid.uuid4()
    pr.version = version
    pr.vrl_code = "."
    pr.engine_version = "0.32"
    pr.status = status
    return pr


def _make_service(
    *,
    log_type_get_by_id: LogType | None = None,
    rule_get_by_id: ParseRule | None = None,
    max_version: int = 0,
):
    parse_rule_repo = MagicMock()
    parse_rule_repo.get_by_id = AsyncMock(return_value=rule_get_by_id)
    parse_rule_repo.get_max_version = AsyncMock(return_value=max_version)
    parse_rule_repo.list_by_log_type = AsyncMock(return_value=[])
    parse_rule_repo.create = AsyncMock(side_effect=lambda r: r)
    parse_rule_repo.update = AsyncMock(side_effect=lambda r: r)

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get_by_id)
    log_type_repo.update = AsyncMock(side_effect=lambda lt: lt)

    return (
        ParseRuleService(parse_rule_repo, log_type_repo),
        parse_rule_repo,
        log_type_repo,
    )


class TestParseRuleServiceCreateDraft:
    """Tests for ParseRuleService.create_draft()."""

    async def test_create_first_version(self):
        """Should create version 1 when no existing rules."""
        # Arrange
        log_type = _make_log_type()
        service, _, log_type_repo = _make_service(
            log_type_get_by_id=log_type,
            max_version=0,
        )
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act
        result = await service.create_draft(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.version == 1
        assert result.status == "draft"
        log_type_repo.update.assert_awaited_once()
        assert log_type.current_parse_rule_id == result.id
        assert log_type.status == "draft"

    async def test_create_increments_version(self):
        """Should set version = max + 1."""
        # Arrange
        log_type = _make_log_type()
        service, _, _ = _make_service(
            log_type_get_by_id=log_type,
            max_version=2,
        )
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act
        result = await service.create_draft(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.version == 3

    async def test_create_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get_by_id=None)
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create_draft(uuid.uuid4(), request, current_user_id=uuid.uuid4())


class TestParseRuleServiceUpdate:
    """Tests for ParseRuleService.update()."""

    async def test_update_applies_changes_to_draft(self):
        """Should update vrl_code on draft rule."""
        # Arrange
        rule = _make_rule(status="draft")
        service, _, _ = _make_service(rule_get_by_id=rule)
        request = ParseRuleUpdate(vrl_code="new code")

        # Act
        result = await service.update(rule.id, request)

        # Assert
        assert result.vrl_code == "new code"

    async def test_update_raises_conflict_on_published_rule(self):
        """Should raise ConflictError when rule is published (immutable)."""
        # Arrange
        rule = _make_rule(status="published")
        service, _, _ = _make_service(rule_get_by_id=rule)
        request = ParseRuleUpdate(vrl_code="new code")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.update(rule.id, request)

    async def test_update_raises_not_found(self):
        """Should raise NotFoundError when rule missing."""
        # Arrange
        service, _, _ = _make_service(rule_get_by_id=None)
        request = ParseRuleUpdate(vrl_code="new")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update(uuid.uuid4(), request)
