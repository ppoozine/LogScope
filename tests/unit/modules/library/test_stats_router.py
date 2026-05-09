"""Router tests for /library/log_types/{id}/stats and /library/products/.../coverage."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.routers import stats_router as sr
from app.modules.library.schemas import (
    CoverageLogType,
    LogTypeStats,
    ProductCoverage,
    StatsTotals,
)


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestLogTypeStatsRoute:
    async def test_returns_disabled_when_clickhouse_off(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.log_type_stats = AsyncMock(
            return_value=LogTypeStats(
                enabled=False,
                range_days=7,
                timeline=[],
                engine_usage=[],
                totals=StatsTotals(total=0, success=0, error=0, success_rate=0.0),
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["enabled"] is False
        assert body["range_days"] == 7

    async def test_invalid_range_returns_422(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user
        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats?range=bad")
        assert r.status_code == 422

    async def test_passes_range_to_service(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_service = AsyncMock()
        fake_service.log_type_stats = AsyncMock(
            return_value=LogTypeStats(
                enabled=True,
                range_days=14,
                timeline=[],
                engine_usage=[],
                totals=StatsTotals(total=0, success=0, error=0, success_rate=0.0),
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        lt = uuid.uuid4()
        r = await client.get(f"/api/v1/library/log_types/{lt}/stats?range=14d")
        assert r.status_code == 200
        fake_service.log_type_stats.assert_awaited_once()
        assert fake_service.log_type_stats.await_args.args[1] == "14d"


class TestProductCoverageRoute:
    async def test_routes_through_pg_then_ch(self, app: FastAPI, client: AsyncClient):
        app.dependency_overrides[current_user] = _user

        fake_lt_repo = AsyncMock()
        ids = [uuid.uuid4(), uuid.uuid4()]
        fake_lt_repo.list_ids_for_vendor_product = AsyncMock(return_value=ids)
        app.dependency_overrides[sr.get_log_type_repository] = lambda: fake_lt_repo

        fake_service = AsyncMock()
        fake_service.product_coverage = AsyncMock(
            return_value=ProductCoverage(
                enabled=True,
                range_days=7,
                log_types=[
                    CoverageLogType(log_type_id=ids[0], sparkline=[0.0] * 7, success_rate_avg=0.0, volume=0),
                    CoverageLogType(log_type_id=ids[1], sparkline=[0.0] * 7, success_rate_avg=0.0, volume=0),
                ],
            )
        )
        app.dependency_overrides[sr.get_stats_service] = lambda: fake_service

        r = await client.get("/api/v1/library/products/v1/p1/coverage")
        assert r.status_code == 200
        body = r.json()["data"]
        assert len(body["log_types"]) == 2
        fake_lt_repo.list_ids_for_vendor_product.assert_awaited_once_with("v1", "p1")
        fake_service.product_coverage.assert_awaited_once()
