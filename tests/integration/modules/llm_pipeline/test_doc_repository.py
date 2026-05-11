"""Integration tests for DocRepository — exercises real DB constraints."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository

pytestmark = pytest.mark.integration


async def _seed_vendor(session: AsyncSession) -> Vendor:
    unique = uuid.uuid4().hex[:8]
    vendor = Vendor()
    vendor.id = uuid.uuid4()
    vendor.name = f"V {unique}"
    vendor.slug = f"v-{unique}"
    session.add(vendor)
    await session.flush()
    return vendor


def _make_doc(vendor_id: uuid.UUID, url: str | None) -> Doc:
    doc = Doc()
    doc.id = uuid.uuid4()
    doc.vendor_id = vendor_id
    doc.url = url
    doc.title = "T"
    doc.content = "# c\n"
    doc.content_format = "markdown"
    doc.fetched_at = datetime.now(UTC)
    doc.fetched_by = "manual"
    return doc


async def test_unique_vendor_url_conflict(db_session: AsyncSession):
    """Two docs with same (vendor_id, url) must violate the partial unique index."""
    vendor = await _seed_vendor(db_session)
    repo = DocRepository(db_session)

    url = f"https://example.com/{uuid.uuid4().hex[:8]}"
    await repo.create(_make_doc(vendor.id, url))

    with pytest.raises(IntegrityError):
        await repo.create(_make_doc(vendor.id, url))


async def test_null_url_allows_duplicates(db_session: AsyncSession):
    """The unique index is partial (WHERE url IS NOT NULL); NULL urls don't conflict."""
    vendor = await _seed_vendor(db_session)
    repo = DocRepository(db_session)

    first = await repo.create(_make_doc(vendor.id, None))
    second = await repo.create(_make_doc(vendor.id, None))

    assert first.id != second.id
