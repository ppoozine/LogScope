import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.schemas import SampleLogCreate, SampleLogRead
from app.modules.library.services.sample_log_service import SampleLogService

router = APIRouter()


async def get_sample_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SampleLogService:
    return SampleLogService(
        SampleLogRepository(session),
        LogTypeRepository(session),
    )


@router.get(
    "/log_types/{log_type_id}/samples",
    response_model=DataResponse[list[SampleLogRead]],
)
async def list_samples(
    log_type_id: uuid.UUID,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[SampleLogRead]]:
    samples = await service.list_by_log_type(log_type_id)
    return DataResponse(data=[SampleLogRead.model_validate(s) for s in samples])


@router.post(
    "/log_types/{log_type_id}/samples",
    response_model=DataResponse[SampleLogRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_sample(
    log_type_id: uuid.UUID,
    body: SampleLogCreate,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[SampleLogRead]:
    sample = await service.create(log_type_id, body, current_user_id=user.id)
    return DataResponse(data=SampleLogRead.model_validate(sample))


@router.delete(
    "/samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sample(
    sample_id: uuid.UUID,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(sample_id)
