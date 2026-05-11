import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.common.exceptions import ConflictError
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.schemas import DocCreate
from app.modules.llm_pipeline.services.doc_service import DocService


def _make_body(
    *,
    url: str | None = "https://example.com/doc",
    title: str | None = "Example",
) -> DocCreate:
    return DocCreate(
        vendor_id=uuid.uuid4(),
        url=url,
        title=title,
        content="# heading\nbody\n",
    )


class TestDocServiceUploadDoc:
    """Tests for DocService.upload_doc()."""

    async def test_creates_doc_with_defaults(self):
        """Should construct Doc with fetched_by='manual', content_format='markdown', fetched_at set."""
        # Arrange
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda d: d)
        service = DocService(repo)
        body = _make_body()

        # Act
        result = await service.upload_doc(body, requested_by_user_id=uuid.uuid4())

        # Assert
        assert isinstance(result, Doc)
        assert result.fetched_by == "manual"
        assert result.content_format == "markdown"
        assert result.fetched_at is not None
        repo.create.assert_awaited_once()

    async def test_passes_through_url_title(self):
        """Should pass body.vendor_id/url/title/content through to the constructed Doc."""
        # Arrange
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda d: d)
        service = DocService(repo)
        body = _make_body(url="https://vendor.io/log-format", title="Vendor Log Format")

        # Act
        result = await service.upload_doc(body, requested_by_user_id=uuid.uuid4())

        # Assert
        assert result.vendor_id == body.vendor_id
        assert result.url == body.url
        assert result.title == body.title
        assert result.content == body.content

    async def test_repo_integrity_error_raises_conflict(self):
        """IntegrityError from repo.create should be translated to ConflictError."""
        # Arrange
        repo = AsyncMock()
        repo.create = AsyncMock(
            side_effect=IntegrityError("stmt", {}, Exception("dup"))
        )
        service = DocService(repo)
        body = _make_body()

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.upload_doc(body, requested_by_user_id=uuid.uuid4())
