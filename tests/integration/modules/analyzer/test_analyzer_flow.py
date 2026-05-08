"""End-to-end Analyzer flow against real Postgres + real PyO3 engine.

LLM (match) is NOT exercised here — Anthropic key may not be set in CI.
"""

import os

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.fixture
async def authed(client: AsyncClient) -> AsyncClient:
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return client


class TestAnalyzerParse:
    """Parse endpoint with real PyO3 engine."""

    async def test_simple_vrl_runs(self, authed: AsyncClient):
        """Should run a trivial VRL against two log lines."""
        # Arrange / Act
        r = await authed.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": '.action = "allow"\n.',
                "logs": ["one", "two"],
                "engine_version": "0.32",
            },
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "ok"
        assert body["summary"]["success"] == 2

    async def test_v25_engine_also_works(self, authed: AsyncClient):
        """Engine 0.25 should run the same VRL."""
        # Arrange / Act
        r = await authed.post(
            "/api/v1/analyzer/parse",
            json={
                "vrl_code": '.action = "deny"\n.',
                "logs": ["x"],
                "engine_version": "0.25",
            },
        )

        # Assert
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["kind"] == "ok"
        assert body["engine"] == "0.25"


class TestAnalyzerMatchEmpty:
    """Match endpoint without an LLM key returns empty candidates."""

    async def test_match_returns_shape(self, authed: AsyncClient):
        """Should 200 with candidates field present (may be empty if no key)."""
        # Act
        r = await authed.post(
            "/api/v1/analyzer/match",
            json={"raw_log": "anything", "top_k": 3},
        )

        # Assert
        # NOTE: settings cache loads ANTHROPIC_API_KEY at startup; if a real
        # key is configured we'd actually hit Anthropic. The intent here is
        # to verify the endpoint shape — assert presence not length.
        assert r.status_code == 200
        assert "candidates" in r.json()["data"]
