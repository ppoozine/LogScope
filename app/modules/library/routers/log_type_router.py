import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.schemas import (
    LogTypeCreate,
    LogTypeRead,
    LogTypeUpdate,
)
from app.modules.library.services.log_type_service import LogTypeService

router = APIRouter()


async def get_log_type_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogTypeService:
    return LogTypeService(
        LogTypeRepository(session),
        ProductRepository(session),
        ParseRuleRepository(session),
    )


@router.get(
    "/products/{product_id}/log_types",
    response_model=DataResponse[list[LogTypeRead]],
)
async def list_log_types(
    product_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[LogTypeRead]]:
    log_types = await service.list_by_product(product_id)
    return DataResponse(data=[LogTypeRead.model_validate(lt) for lt in log_types])


@router.get(
    "/log_types/{log_type_id}",
    response_model=DataResponse[LogTypeRead],
)
async def get_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.get_by_id(log_type_id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.post(
    "/products/{product_id}/log_types",
    response_model=DataResponse[LogTypeRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_log_type(
    product_id: uuid.UUID,
    body: LogTypeCreate,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.create(product_id, body, current_user_id=user.id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.patch(
    "/log_types/{log_type_id}",
    response_model=DataResponse[LogTypeRead],
)
async def update_log_type(
    log_type_id: uuid.UUID,
    body: LogTypeUpdate,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.update(log_type_id, body)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.delete(
    "/log_types/{log_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(log_type_id)


@router.post(
    "/log_types/{log_type_id}/publish",
    response_model=DataResponse[LogTypeRead],
)
async def publish_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.publish(log_type_id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))
