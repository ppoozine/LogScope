"""POST /api/v1/llm-pipeline/docs — admin upload of vendor doc markdown."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.schemas import DocCreate, DocRead
from app.modules.llm_pipeline.services.doc_service import DocService

router = APIRouter()


async def get_doc_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocService:
    return DocService(DocRepository(session))


@router.post(
    "/docs",
    response_model=DataResponse[DocRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_doc(
    body: DocCreate,
    service: Annotated[DocService, Depends(get_doc_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[DocRead]:
    doc = await service.upload_doc(body, requested_by_user_id=user.id)
    return DataResponse(data=DocRead.model_validate(doc))
