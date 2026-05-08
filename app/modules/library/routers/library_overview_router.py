from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    OverviewVendorGroup,
    ProductCategory,
)
from app.modules.library.services.library_overview_service import (
    LibraryOverviewService,
)

router = APIRouter()


async def get_library_overview_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LibraryOverviewService:
    return LibraryOverviewService(
        VendorRepository(session),
        ProductRepository(session),
        LogTypeRepository(session),
    )


@router.get(
    "/overview",
    response_model=DataResponse[list[OverviewVendorGroup]],
)
async def overview(
    service: Annotated[LibraryOverviewService, Depends(get_library_overview_service)],
    _user: Annotated[User, Depends(current_user)],
    category: Annotated[ProductCategory | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> DataResponse[list[OverviewVendorGroup]]:
    groups = await service.overview(category=category, log_type_status=status_filter)
    return DataResponse(data=groups)
