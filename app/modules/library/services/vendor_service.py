import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import VendorCreate, VendorUpdate


class VendorService:
    def __init__(self, repo: VendorRepository) -> None:
        self._repo = repo

    async def list(self, *, status: str | None = None) -> list[Vendor]:
        return await self._repo.list(status=status)

    async def get_by_slug(self, slug: str) -> Vendor:
        vendor = await self._repo.get_by_slug(slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {slug}")
        return vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor:
        vendor = await self._repo.get_by_id(vendor_id)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_id}")
        return vendor

    async def create(self, data: VendorCreate, *, current_user_id: uuid.UUID) -> Vendor:
        slug = data.slug or slugify(data.name)
        existing = await self._repo.get_by_slug(slug)
        if existing is not None:
            raise ConflictError(f"vendor slug already exists: {slug}")

        vendor = Vendor()
        vendor.name = data.name
        vendor.slug = slug
        vendor.website_url = data.website_url
        vendor.logo_url = data.logo_url
        vendor.status = data.status
        vendor.created_by = current_user_id
        return await self._repo.create(vendor)

    async def update(self, vendor_id: uuid.UUID, data: VendorUpdate) -> Vendor:
        vendor = await self.get_by_id(vendor_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(vendor, field, value)
        return await self._repo.update(vendor)

    async def delete(self, vendor_id: uuid.UUID) -> None:
        vendor = await self.get_by_id(vendor_id)
        await self._repo.delete(vendor)
