import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.common.exceptions import ConflictError
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.schemas import DocCreate


class DocService:
    def __init__(self, repo: DocRepository) -> None:
        self._repo = repo

    async def upload_doc(
        self, body: DocCreate, *, requested_by_user_id: uuid.UUID
    ) -> Doc:
        doc = Doc(
            id=uuid.uuid4(),
            vendor_id=body.vendor_id,
            url=body.url,
            title=body.title,
            content=body.content,
            content_format=body.content_format,
            fetched_at=datetime.now(UTC),
            fetched_by="manual",
        )
        try:
            return await self._repo.create(doc)
        except IntegrityError as e:
            raise ConflictError(
                "Doc with this vendor and url already exists"
            ) from e
