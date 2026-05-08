"""Real PG: promote endpoint correctly archives prior published and respects partial unique."""

import os
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return client


async def test_two_drafts_promote_simultaneously_only_one_wins(authenticated_client: AsyncClient):
    """Promote v2 archives v1; partial unique is respected."""
    unique = uuid.uuid4().hex[:8]

    # Build a log_type with two drafts via API
    r = await authenticated_client.post(
        "/api/v1/library/vendors", json={"name": f"VR {unique}", "slug": f"vr-{unique}"}
    )
    assert r.status_code == 201
    vendor = r.json()["data"]
    r = await authenticated_client.post(
        f"/api/v1/library/vendors/vr-{unique}/products", json={"name": "P", "slug": "p"}
    )
    assert r.status_code == 201
    product = r.json()["data"]
    r = await authenticated_client.post(
        f"/api/v1/library/products/{product['id']}/log_types",
        json={"name": "LT", "slug": "lt", "format": "csv"},
    )
    assert r.status_code == 201
    lt = r.json()["data"]

    # First draft
    r = await authenticated_client.post(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules",
        json={"vrl_code": ".x = 1", "engine_version": "0.32"},
    )
    assert r.status_code == 201
    draft_a = r.json()["data"]

    # Promote first draft → success, becomes published
    r = await authenticated_client.post(
        f"/api/v1/library/parse_rules/{draft_a['id']}/promote"
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "published"

    # Second draft (creating another draft should NOT auto-publish)
    r = await authenticated_client.post(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules",
        json={"vrl_code": ".x = 2", "engine_version": "0.32"},
    )
    assert r.status_code == 201
    draft_b = r.json()["data"]

    # Promote second draft → success, draft_a auto-archived
    r = await authenticated_client.post(
        f"/api/v1/library/parse_rules/{draft_b['id']}/promote"
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "published"

    # Confirm draft_a is archived
    r = await authenticated_client.get(
        f"/api/v1/library/log_types/{lt['id']}/parse_rules"
    )
    rules = {x["id"]: x["status"] for x in r.json()["data"]}
    assert rules[draft_a["id"]] == "archived"
    assert rules[draft_b["id"]] == "published"

    # Cleanup
    await authenticated_client.delete(f"/api/v1/library/log_types/{lt['id']}")
    await authenticated_client.delete(f"/api/v1/library/products/{product['id']}")
    await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")
