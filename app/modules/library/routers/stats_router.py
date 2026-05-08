"""GET stats / coverage — backed by ClickHouse via StatsService."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.clickhouse import get_clickhouse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import LogTypeStats, ProductCoverage, StatsRange
from app.modules.library.services.stats_service import StatsService

router = APIRouter()


def get_stats_service() -> StatsService:
    return StatsService(client=get_clickhouse())


async def get_log_type_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogTypeRepository:
    return LogTypeRepository(session)


@router.get(
    "/log_types/{log_type_id}/stats",
    response_model=DataResponse[LogTypeStats],
)
async def log_type_stats(
    log_type_id: uuid.UUID,
    service: Annotated[StatsService, Depends(get_stats_service)],
    _user: Annotated[User, Depends(current_user)],
    range_: Annotated[StatsRange, Query(alias="range")] = "7d",
) -> DataResponse[LogTypeStats]:
    stats = await service.log_type_stats(log_type_id, range_)
    return DataResponse(data=stats)


@router.get(
    "/products/{vendor_slug}/{product_slug}/coverage",
    response_model=DataResponse[ProductCoverage],
)
async def product_coverage(
    vendor_slug: str,
    product_slug: str,
    repo: Annotated[LogTypeRepository, Depends(get_log_type_repository)],
    service: Annotated[StatsService, Depends(get_stats_service)],
    _user: Annotated[User, Depends(current_user)],
    range_: Annotated[StatsRange, Query(alias="range")] = "7d",
) -> DataResponse[ProductCoverage]:
    ids = await repo.list_ids_for_vendor_product(vendor_slug, product_slug)
    coverage = await service.product_coverage(ids, range_)
    return DataResponse(data=coverage)
