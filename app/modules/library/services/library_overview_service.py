from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    LogTypeCounts,
    OverviewProduct,
    OverviewVendor,
    OverviewVendorGroup,
)


class LibraryOverviewService:
    def __init__(
        self,
        vendor_repo: VendorRepository,
        product_repo: ProductRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._vendors = vendor_repo
        self._products = product_repo
        self._log_types = log_type_repo

    async def overview(
        self,
        *,
        category: str | None = None,
        log_type_status: str | None = None,
    ) -> list[OverviewVendorGroup]:
        """Aggregate vendor → products → log_type counts."""
        vendors = await self._vendors.list()
        groups: list[OverviewVendorGroup] = []

        for vendor in vendors:
            products = await self._products.list_by_vendor(vendor.id)
            overview_products: list[OverviewProduct] = []

            for product in products:
                if category is not None and product.category != category:
                    continue

                log_types = await self._log_types.list_by_product(product.id)
                published = sum(1 for lt in log_types if lt.status == "published")
                draft = sum(1 for lt in log_types if lt.status == "draft")
                total = len(log_types)

                if log_type_status == "published" and published == 0:
                    continue
                if log_type_status == "draft" and draft == 0:
                    continue

                overview_products.append(
                    OverviewProduct(
                        id=product.id,
                        name=product.name,
                        slug=product.slug,
                        category=product.category,  # type: ignore[arg-type]
                        status=product.status,  # type: ignore[arg-type]
                        log_type_counts=LogTypeCounts(
                            total=total,
                            published=published,
                            draft=draft,
                        ),
                        is_empty=(total == 0),
                    )
                )

            groups.append(
                OverviewVendorGroup(
                    vendor=OverviewVendor(
                        id=vendor.id,
                        name=vendor.name,
                        slug=vendor.slug,
                        logo_url=vendor.logo_url,
                    ),
                    products=overview_products,
                )
            )

        return groups
