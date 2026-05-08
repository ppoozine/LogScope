import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.field_schema_repository import FieldSchemaRepository
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.schemas import (
    FieldSchemaRead,
    LogFormat,
    LogTransport,
    LogTypeCreate,
    LogTypeDetail,
    LogTypeRead,
    LogTypeSource,
    LogTypeStatus,
    LogTypeUpdate,
    ParseRuleRead,
    SampleLogRead,
)
from app.modules.library.services.field_schema_service import FieldSchemaService
from app.modules.library.services.log_type_service import LogTypeService
from app.modules.library.services.parse_rule_service import ParseRuleService
from app.modules.library.services.sample_log_service import SampleLogService

router = APIRouter()


async def get_field_schema_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FieldSchemaService:
    return FieldSchemaService(
        FieldSchemaRepository(session),
        LogTypeRepository(session),
    )


async def get_parse_rule_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParseRuleService:
    return ParseRuleService(
        ParseRuleRepository(session),
        LogTypeRepository(session),
    )


async def get_sample_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SampleLogService:
    return SampleLogService(
        SampleLogRepository(session),
        LogTypeRepository(session),
    )


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
    response_model=DataResponse[LogTypeDetail],
)
async def get_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    field_schema_service: Annotated[FieldSchemaService, Depends(get_field_schema_service)],
    parse_rule_service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    sample_log_service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeDetail]:
    log_type = await service.get_by_id(log_type_id)
    fields = await field_schema_service.list_by_log_type(log_type.id)
    samples = await sample_log_service.list_by_log_type(log_type.id)
    current_rule = (
        await parse_rule_service.get_by_id(log_type.current_parse_rule_id) if log_type.current_parse_rule_id else None
    )
    detail = LogTypeDetail(
        id=log_type.id,
        product_id=log_type.product_id,
        name=log_type.name,
        slug=log_type.slug,
        format=cast(LogFormat, log_type.format),
        transport=cast(LogTransport | None, log_type.transport),
        status=cast(LogTypeStatus, log_type.status),
        source=cast(LogTypeSource, log_type.source),
        current_parse_rule_id=log_type.current_parse_rule_id,
        description=log_type.description,
        published_at=log_type.published_at,
        created_at=log_type.created_at,
        updated_at=log_type.updated_at,
        fields=[FieldSchemaRead.model_validate(f) for f in fields],
        current_parse_rule=(ParseRuleRead.model_validate(current_rule) if current_rule else None),
        samples=[SampleLogRead.model_validate(s) for s in samples],
    )
    return DataResponse(data=detail)


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
