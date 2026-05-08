import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.vendor import Vendor
from app.modules.library.schemas import VendorCreate, VendorUpdate
from app.modules.library.services.vendor_service import VendorService


def _make_vendor(slug: str = "acme", name: str = "Acme") -> Vendor:
    """Factory helper to create a Vendor instance for testing."""
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = name
    v.slug = slug
    v.status = "active"
    return v


def _make_service(
    *, get_by_slug_returns: Vendor | None = None, get_by_id_returns: Vendor | None = None
) -> tuple[VendorService, MagicMock]:
    """Factory helper to create a VendorService with a mocked repo."""
    repo = MagicMock()
    repo.get_by_slug = AsyncMock(return_value=get_by_slug_returns)
    repo.get_by_id = AsyncMock(return_value=get_by_id_returns)
    repo.list = AsyncMock(return_value=[])
    repo.create = AsyncMock(side_effect=lambda v: v)
    repo.update = AsyncMock(side_effect=lambda v: v)
    repo.delete = AsyncMock(return_value=None)
    return VendorService(repo), repo


class TestVendorServiceCreate:
    """Tests for VendorService.create()."""

    async def test_create_auto_generates_slug(self) -> None:
        """Should slugify name when slug omitted."""
        # Arrange
        service, repo = _make_service(get_by_slug_returns=None)
        request = VendorCreate(name="Palo Alto Networks")

        # Act
        result = await service.create(request, current_user_id=uuid.uuid4())

        # Assert
        assert result.slug == "palo-alto-networks"
        repo.create.assert_awaited_once()

    async def test_create_uses_provided_slug(self) -> None:
        """Should respect explicit slug."""
        # Arrange
        service, _ = _make_service(get_by_slug_returns=None)
        request = VendorCreate(name="Acme", slug="acme-corp")

        # Act
        result = await service.create(request, current_user_id=uuid.uuid4())

        # Assert
        assert result.slug == "acme-corp"

    async def test_create_raises_conflict_when_slug_exists(self) -> None:
        """Should raise ConflictError if slug already in DB."""
        # Arrange
        service, _ = _make_service(get_by_slug_returns=_make_vendor("acme"))
        request = VendorCreate(name="Acme")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(request, current_user_id=uuid.uuid4())


class TestVendorServiceUpdate:
    """Tests for VendorService.update()."""

    async def test_update_applies_changes(self) -> None:
        """Should apply provided fields to vendor."""
        # Arrange
        existing = _make_vendor("acme", "Old Name")
        service, _ = _make_service(get_by_id_returns=existing)
        request = VendorUpdate(name="New Name")

        # Act
        result = await service.update(existing.id, request)

        # Assert
        assert result.name == "New Name"

    async def test_update_raises_not_found(self) -> None:
        """Should raise NotFoundError when vendor missing."""
        # Arrange
        service, _ = _make_service(get_by_id_returns=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update(uuid.uuid4(), VendorUpdate(name="X"))


class TestVendorServiceDelete:
    """Tests for VendorService.delete()."""

    async def test_delete_calls_repo(self) -> None:
        """Should fetch then delete."""
        # Arrange
        existing = _make_vendor()
        service, repo = _make_service(get_by_id_returns=existing)

        # Act
        await service.delete(existing.id)

        # Assert
        repo.delete.assert_awaited_once_with(existing)

    async def test_delete_raises_not_found(self) -> None:
        """Should raise NotFoundError when missing."""
        # Arrange
        service, _ = _make_service(get_by_id_returns=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4())
