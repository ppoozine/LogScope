import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.product import Product
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    FieldSchemaRead,
    LogTypeDetail,
    ParseRuleRead,
    ProductCreate,
    ProductDetail,
    ProductUpdate,
    SampleLogRead,
)


class ProductService:
    def __init__(
        self,
        product_repo: ProductRepository,
        vendor_repo: VendorRepository,
        log_type_repo: LogTypeRepository | None = None,
        field_repo: FieldSchemaRepository | None = None,
        parse_rule_repo: ParseRuleRepository | None = None,
        sample_repo: SampleLogRepository | None = None,
    ) -> None:
        self._products = product_repo
        self._vendors = vendor_repo
        self._log_types = log_type_repo
        self._fields = field_repo
        self._parse_rules = parse_rule_repo
        self._samples = sample_repo

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

    async def get_detail(self, vendor_slug: str, product_slug: str) -> ProductDetail:
        """Return Product with full nested log_types / fields / parse_rule / samples.

        Spec §5.4: 詳情頁一次取完。
        """
        if (
            self._log_types is None
            or self._fields is None
            or self._parse_rules is None
            or self._samples is None
        ):
            raise RuntimeError(
                "get_detail requires all four child repos (log_type/field/parse_rule/sample) to be injected"
            )

        product = await self.get_by_vendor_and_slug(vendor_slug, product_slug)

        log_types = await self._log_types.list_by_product(product.id)
        log_type_details: list[LogTypeDetail] = []
        for lt in log_types:
            fields = await self._fields.list_by_log_type(lt.id)
            samples = await self._samples.list_by_log_type(lt.id)
            current_rule = (
                await self._parse_rules.get_by_id(lt.current_parse_rule_id)
                if lt.current_parse_rule_id
                else None
            )

            log_type_details.append(
                LogTypeDetail(
                    id=lt.id,
                    product_id=lt.product_id,
                    name=lt.name,
                    slug=lt.slug,
                    format=lt.format,  # type: ignore[arg-type]
                    transport=lt.transport,  # type: ignore[arg-type]
                    status=lt.status,  # type: ignore[arg-type]
                    source=lt.source,  # type: ignore[arg-type]
                    current_parse_rule_id=lt.current_parse_rule_id,
                    description=lt.description,
                    published_at=lt.published_at,
                    created_at=lt.created_at,
                    updated_at=lt.updated_at,
                    fields=[FieldSchemaRead.model_validate(f) for f in fields],
                    current_parse_rule=(
                        ParseRuleRead.model_validate(current_rule)
                        if current_rule
                        else None
                    ),
                    samples=[SampleLogRead.model_validate(s) for s in samples],
                )
            )

        return ProductDetail(
            id=product.id,
            vendor_id=product.vendor_id,
            name=product.name,
            slug=product.slug,
            version=product.version,
            description=product.description,
            deploy_type=product.deploy_type,  # type: ignore[arg-type]
            category=product.category,  # type: ignore[arg-type]
            doc_url=product.doc_url,
            status=product.status,  # type: ignore[arg-type]
            created_at=product.created_at,
            updated_at=product.updated_at,
            log_types=log_type_details,
        )

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
