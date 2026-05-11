import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    SchemaMismatchError,
    VrlCompileError,
)
from app.modules.llm_pipeline.routers.draft_router import get_draft_service
from app.modules.llm_pipeline.routers.throttle import (
    InMemoryThrottle,
    get_throttle,
)
from app.modules.llm_pipeline.services.llm_draft_service import GenerationResult


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


pytestmark = pytest.mark.asyncio


class TestPostGenerateDraft:
    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        from app.common.auth import get_auth_service
        from app.common.exceptions import UnauthorizedError

        # Arrange: fake auth raises UnauthorizedError; override service stub
        # so the dep tree resolves without hitting the (uninitialized) DB.
        fake_auth = AsyncMock()
        fake_auth.get_current_user_from_session = AsyncMock(
            side_effect=UnauthorizedError("missing session")
        )
        fake_service = AsyncMock()
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        app.dependency_overrides[get_draft_service] = lambda: fake_service

        r = await client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={
                "doc_id": str(uuid.uuid4()),
                "product_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code in (401, 403)

    async def test_happy_path(self, app: FastAPI, client: AsyncClient):
        fake_service = AsyncMock()
        result = GenerationResult(
            job_id=uuid.uuid4(),
            log_type_id=uuid.uuid4(),
            parse_rule_id=uuid.uuid4(),
        )
        fake_service.generate_draft = AsyncMock(return_value=result)
        app.dependency_overrides[get_draft_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={
                "doc_id": str(uuid.uuid4()),
                "product_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["job_id"] == str(result.job_id)
        assert body["log_type_id"] == str(result.log_type_id)
        assert body["parse_rule_id"] == str(result.parse_rule_id)

    async def test_schema_mismatch_returns_422(
        self, app: FastAPI, client: AsyncClient
    ):
        fake_service = AsyncMock()
        e = SchemaMismatchError("bad shape")
        e.job_id = uuid.uuid4()  # type: ignore[attr-defined]
        fake_service.generate_draft = AsyncMock(side_effect=e)
        app.dependency_overrides[get_draft_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={
                "doc_id": str(uuid.uuid4()),
                "product_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["error_code"] == "schema_mismatch"

    async def test_anthropic_failed_returns_502(
        self, app: FastAPI, client: AsyncClient
    ):
        fake_service = AsyncMock()
        e = AnthropicCallError("rate limit")
        e.job_id = uuid.uuid4()  # type: ignore[attr-defined]
        fake_service.generate_draft = AsyncMock(side_effect=e)
        app.dependency_overrides[get_draft_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={
                "doc_id": str(uuid.uuid4()),
                "product_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 502

    async def test_vrl_compile_failed_returns_422(
        self, app: FastAPI, client: AsyncClient
    ):
        fake_service = AsyncMock()
        e = VrlCompileError("compile bomb")
        e.job_id = uuid.uuid4()  # type: ignore[attr-defined]
        fake_service.generate_draft = AsyncMock(side_effect=e)
        app.dependency_overrides[get_draft_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _user

        r = await client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={
                "doc_id": str(uuid.uuid4()),
                "product_id": str(uuid.uuid4()),
            },
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error_code"] == "vrl_compile_failed"

    async def test_throttle_returns_429(self, app: FastAPI, client: AsyncClient):
        # tight throttle just for this test
        tiny = InMemoryThrottle(max_calls=1, window_seconds=60)
        app.dependency_overrides[get_throttle] = lambda: tiny
        # Pin the user so both requests share user_id (throttle keyed by user.id)
        fixed_user = _user()
        app.dependency_overrides[current_user] = lambda: fixed_user
        # also override service so auth+throttle pass first call
        fake_service = AsyncMock()
        fake_service.generate_draft = AsyncMock(
            return_value=GenerationResult(
                job_id=uuid.uuid4(),
                log_type_id=uuid.uuid4(),
                parse_rule_id=uuid.uuid4(),
            )
        )
        app.dependency_overrides[get_draft_service] = lambda: fake_service

        body = {
            "doc_id": str(uuid.uuid4()),
            "product_id": str(uuid.uuid4()),
        }
        r1 = await client.post("/api/v1/llm-pipeline/drafts/generate", json=body)
        assert r1.status_code == 200
        r2 = await client.post("/api/v1/llm-pipeline/drafts/generate", json=body)
        assert r2.status_code == 429
