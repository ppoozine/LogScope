import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.schemas import LogTypeCreate, LogTypeUpdate
from app.modules.library.services.log_type_service import LogTypeService


def _make_product() -> Product:
    p = Product()
    p.id = uuid.uuid4()
    return p


def _make_log_type(
    *,
    product_id: uuid.UUID | None = None,
    current_parse_rule_id: uuid.UUID | None = None,
    status: str = "draft",
) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id or uuid.uuid4()
    lt.name = "Traffic"
    lt.slug = "traffic"
    lt.format = "csv"
    lt.status = status
    lt.source = "manual"
    lt.current_parse_rule_id = current_parse_rule_id
    return lt


def _make_parse_rule(
    *,
    log_type_id: uuid.UUID,
    status: str = "draft",
    version: int = 1,
) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = log_type_id
    pr.version = version
    pr.status = status
    pr.engine_version = "0.32"
    pr.vrl_code = "."
    return pr


def _make_service(
    *,
    log_type_get_by_id: LogType | None = None,
    log_type_get_by_product_slug: LogType | None = None,
    product_get_by_id: Product | None = None,
    parse_rule_get_by_id: ParseRule | None = None,
):
    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get_by_id)
    log_type_repo.get_by_product_and_slug = AsyncMock(return_value=log_type_get_by_product_slug)
    log_type_repo.list_by_product = AsyncMock(return_value=[])
    log_type_repo.create = AsyncMock(side_effect=lambda lt: lt)
    log_type_repo.update = AsyncMock(side_effect=lambda lt: lt)
    log_type_repo.delete = AsyncMock(return_value=None)

    product_repo = MagicMock()
    product_repo.get_by_id = AsyncMock(return_value=product_get_by_id)

    parse_rule_repo = MagicMock()
    parse_rule_repo.get_by_id = AsyncMock(return_value=parse_rule_get_by_id)
    parse_rule_repo.update = AsyncMock(side_effect=lambda pr: pr)

    return (
        LogTypeService(log_type_repo, product_repo, parse_rule_repo),
        log_type_repo,
        product_repo,
        parse_rule_repo,
    )


class TestLogTypeServiceCreate:
    """Tests for LogTypeService.create()."""

    async def test_create_under_existing_product(self):
        """Should attach to existing product."""
        # Arrange
        product = _make_product()
        service, _, _, _ = _make_service(product_get_by_id=product)
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act
        result = await service.create(product.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.product_id == product.id
        assert result.slug == "traffic"

    async def test_create_raises_when_product_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _, _ = _make_service(product_get_by_id=None)
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create(uuid.uuid4(), request, current_user_id=uuid.uuid4())

    async def test_create_raises_conflict_on_slug_collision(self):
        """Should raise ConflictError when product+slug already exists."""
        # Arrange
        product = _make_product()
        existing = _make_log_type(product_id=product.id)
        service, _, _, _ = _make_service(
            product_get_by_id=product,
            log_type_get_by_product_slug=existing,
        )
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(product.id, request, current_user_id=uuid.uuid4())


class TestLogTypeServicePublish:
    """Tests for LogTypeService.publish()."""

    async def test_publish_promotes_draft_rule(self):
        """Should promote current draft parse rule to published."""
        # Arrange
        log_type = _make_log_type()
        rule = _make_parse_rule(log_type_id=log_type.id, status="draft")
        log_type.current_parse_rule_id = rule.id
        service, log_type_repo, _, parse_rule_repo = _make_service(
            log_type_get_by_id=log_type,
            parse_rule_get_by_id=rule,
        )

        # Act
        result = await service.publish(log_type.id)

        # Assert
        assert result.status == "published"
        assert rule.status == "published"
        assert result.published_at is not None
        log_type_repo.update.assert_awaited_once()
        parse_rule_repo.update.assert_awaited_once()

    async def test_publish_raises_validation_when_no_current_rule(self):
        """Should raise ValidationError when log type has no current parse rule."""
        # Arrange
        log_type = _make_log_type(current_parse_rule_id=None)
        service, _, _, _ = _make_service(log_type_get_by_id=log_type)

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.publish(log_type.id)

    async def test_publish_raises_conflict_when_already_published(self):
        """Should raise ConflictError when current rule is already published."""
        # Arrange
        log_type = _make_log_type()
        rule = _make_parse_rule(log_type_id=log_type.id, status="published")
        log_type.current_parse_rule_id = rule.id
        service, _, _, _ = _make_service(
            log_type_get_by_id=log_type,
            parse_rule_get_by_id=rule,
        )

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.publish(log_type.id)


class TestLogTypeServiceUpdate:
    """Tests for LogTypeService.update()."""

    async def test_update_applies_changes(self):
        """Should apply provided fields."""
        # Arrange
        log_type = _make_log_type()
        service, _, _, _ = _make_service(log_type_get_by_id=log_type)
        request = LogTypeUpdate(name="New Name")

        # Act
        result = await service.update(log_type.id, request)

        # Assert
        assert result.name == "New Name"


class TestLogTypeServiceDelete:
    """Tests for LogTypeService.delete()."""

    async def test_deletes_log_type(self):
        """Should call repo.delete."""
        # Arrange
        log_type = _make_log_type()
        service, repo, _, _ = _make_service(log_type_get_by_id=log_type)

        # Act
        await service.delete(log_type.id)

        # Assert
        repo.delete.assert_awaited_once_with(log_type)
