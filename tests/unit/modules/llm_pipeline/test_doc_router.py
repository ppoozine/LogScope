import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.common.exceptions import ConflictError
from app.modules.auth.models.user import User
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.routers.doc_router import get_doc_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_doc(vendor_id: uuid.UUID | None = None) -> Doc:
    doc = Doc()
    doc.id = uuid.uuid4()
    doc.vendor_id = vendor_id or uuid.uuid4()
    doc.url = "https://example.com/doc"
    doc.title = "Example"
    doc.content = "# heading\n"
    doc.content_format = "markdown"
    doc.fetched_at = datetime.now(UTC)
    doc.fetched_by = "manual"
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


def _valid_body(vendor_id: uuid.UUID | None = None) -> dict:
    return {
        "vendor_id": str(vendor_id or uuid.uuid4()),
        "url": "https://example.com/doc",
        "title": "Example",
        "content_format": "markdown",
        "content": "# heading\nbody\n",
    }


class TestDocUpload:
    """Tests for POST /api/v1/llm-pipeline/docs."""

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 when no session cookie is present."""
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange: fake auth raises UnauthorizedError; override service stub so
        # the dep tree resolves without hitting the (uninitialized) DB.
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(
            side_effect=UnauthorizedError("missing session")
        )
        fake_service = AsyncMock()
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        app.dependency_overrides[get_doc_service] = lambda: fake_service

        # Act
        r = await client.post("/api/v1/llm-pipeline/docs", json=_valid_body())

        # Assert
        assert r.status_code == 401

    async def test_creates_doc(self, app: FastAPI, client: AsyncClient):
        """Should return 201 with DocRead payload on successful upload."""
        # Arrange
        vendor_id = uuid.uuid4()
        doc = _make_doc(vendor_id)
        fake = AsyncMock()
        fake.upload_doc = AsyncMock(return_value=doc)
        app.dependency_overrides[get_doc_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/llm-pipeline/docs", json=_valid_body(vendor_id)
        )

        # Assert
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["id"] == str(doc.id)
        assert data["vendor_id"] == str(vendor_id)
        assert data["url"] == doc.url
        assert data["title"] == doc.title
        assert data["content_format"] == "markdown"
        assert data["fetched_by"] == "manual"
        # `content` is intentionally omitted from DocRead
        assert "content" not in data

    async def test_409_on_dup_via_service_conflict_error(
        self, app: FastAPI, client: AsyncClient
    ):
        """Should map ConflictError raised by service to HTTP 409."""
        # Arrange
        fake = AsyncMock()
        fake.upload_doc = AsyncMock(
            side_effect=ConflictError("Doc with this vendor and url already exists")
        )
        app.dependency_overrides[get_doc_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post("/api/v1/llm-pipeline/docs", json=_valid_body())

        # Assert
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "conflict"
