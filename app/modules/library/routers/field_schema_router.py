import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import (
    FieldSchemaBulkReplace,
    FieldSchemaRead,
)
from app.modules.library.services.field_schema_service import FieldSchemaService

router = APIRouter()


async def get_field_schema_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FieldSchemaService:
    return FieldSchemaService(
        FieldSchemaRepository(session),
        LogTypeRepository(session),
    )


@router.put(
    "/log_types/{log_type_id}/fields",
    response_model=DataResponse[list[FieldSchemaRead]],
)
async def replace_log_type_fields(
    log_type_id: uuid.UUID,
    body: FieldSchemaBulkReplace,
    service: Annotated[FieldSchemaService, Depends(get_field_schema_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[FieldSchemaRead]]:
    fields = await service.replace_for_log_type(log_type_id, body)
    return DataResponse(data=[FieldSchemaRead.model_validate(f) for f in fields])
