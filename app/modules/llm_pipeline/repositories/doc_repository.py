import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_pipeline.models import Doc


class DocRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, doc: Doc) -> Doc:
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Doc | None:
        return await self._session.get(Doc, doc_id)
