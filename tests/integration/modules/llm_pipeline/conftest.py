"""llm_pipeline integration test fixtures.

Builds on tests/integration/conftest.py (which provides app, client,
db_session, db_session_factory). Adds:

- ``authenticated_client``: a logged-in admin client (mirrors library flow).
- ``seed_vendor_product``: a fresh Vendor + Product pair committed to DB.
- ``override_anthropic``: setter that installs a stub for
  ``get_anthropic_client`` returning a canned response or raising an
  exception. Cleans up after the test automatically.
"""
import os
import uuid
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Log in as admin and return client with session cookie.

    Mirrors tests/integration/modules/library/test_library_flow.py pattern.
    """
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    return client


@pytest.fixture
async def seed_vendor_product(
    db_session: AsyncSession,
) -> tuple[Vendor, Product]:
    """Insert a fresh Vendor + Product pair for the test."""
    unique = uuid.uuid4().hex[:6]
    vendor = Vendor(
        id=uuid.uuid4(),
        name=f"Acme-{unique}",
        slug=f"acme-{unique}",
        status="active",
    )
    db_session.add(vendor)
    await db_session.flush()
    product = Product(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        name="FW",
        slug=f"fw-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.commit()
    return vendor, product


@pytest.fixture
def override_anthropic(
    app: FastAPI,
) -> Generator[Callable[[Any], None]]:
    """Override ``get_anthropic_client`` to return a stub client.

    The stub's ``messages.create`` either returns a precomputed response or
    raises a precomputed exception, depending on what the test installs via
    the yielded setter:

        override_anthropic(canned_response_or_exception)

    Cleanup of ``app.dependency_overrides`` happens automatically.
    """
    from app.core.deps import get_anthropic_client

    captured: dict[str, Any] = {}

    def _override(target: Any) -> None:
        class _Stub:
            def __init__(self) -> None:
                self.messages = self

            async def create(self, **_kwargs: Any) -> Any:
                if isinstance(target, Exception):
                    raise target
                return target

        captured["stub"] = _Stub()
        app.dependency_overrides[get_anthropic_client] = lambda: captured["stub"]

    try:
        yield _override
    finally:
        app.dependency_overrides.pop(get_anthropic_client, None)
