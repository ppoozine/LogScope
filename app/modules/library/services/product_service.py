import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.product import Product
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import ProductCreate, ProductUpdate


class ProductService:
    def __init__(
        self,
        product_repo: ProductRepository,
        vendor_repo: VendorRepository,
    ) -> None:
        self._products = product_repo
        self._vendors = vendor_repo

    async def list_by_vendor_slug(self, vendor_slug: str) -> list[Product]:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")
        return await self._products.list_by_vendor(vendor.id)

    async def get_by_vendor_and_slug(self, vendor_slug: str, product_slug: str) -> Product:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")
        product = await self._products.get_by_vendor_and_slug(vendor.id, product_slug)
        if product is None:
            raise NotFoundError(f"product not found: {vendor_slug}/{product_slug}")
        return product

    async def get_by_id(self, product_id: uuid.UUID) -> Product:
        product = await self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"product not found: {product_id}")
        return product

    async def create(
        self,
        vendor_slug: str,
        data: ProductCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> Product:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")

        slug = data.slug or slugify(data.name)
        existing = await self._products.get_by_vendor_and_slug(vendor.id, slug)
        if existing is not None:
            raise ConflictError(f"product slug already exists in vendor: {slug}")

        product = Product()
        product.vendor_id = vendor.id
        product.name = data.name
        product.slug = slug
        product.version = data.version
        product.description = data.description
        product.deploy_type = data.deploy_type
        product.category = data.category
        product.doc_url = data.doc_url
        product.status = data.status
        product.created_by = current_user_id
        return await self._products.create(product)

    async def update(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_by_id(product_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(product, field, value)
        return await self._products.update(product)

    async def delete(self, product_id: uuid.UUID) -> None:
        product = await self.get_by_id(product_id)
        await self._products.delete(product)
