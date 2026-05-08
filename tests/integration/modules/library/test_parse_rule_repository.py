"""Integration test for new repository helpers."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository

pytestmark = pytest.mark.integration


async def _seed_log_type(session: AsyncSession) -> LogType:
    unique = uuid.uuid4().hex[:8]
    vendor = Vendor()
    vendor.id = uuid.uuid4()
    vendor.name = f"V {unique}"
    vendor.slug = f"v-{unique}"
    session.add(vendor)
    await session.flush()

    product = Product()
    product.id = uuid.uuid4()
    product.vendor_id = vendor.id
    product.name = "P"
    product.slug = f"p-{unique}"
    session.add(product)
    await session.flush()

    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product.id
    lt.name = "LT"
    lt.slug = f"lt-{unique}"
    lt.format = "csv"
    session.add(lt)
    await session.flush()
    return lt


async def test_get_current_published_returns_none_when_no_published(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    rule = ParseRule()
    rule.log_type_id = lt.id
    rule.version = 1
    rule.vrl_code = "."
    rule.engine_version = "0.32"
    rule.status = "draft"
    db_session.add(rule)
    await db_session.flush()

    assert await repo.get_current_published(lt.id) is None


async def test_get_current_published_returns_published(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    pub = ParseRule()
    pub.log_type_id = lt.id
    pub.version = 1
    pub.vrl_code = "."
    pub.engine_version = "0.32"
    pub.status = "published"
    db_session.add(pub)
    await db_session.flush()

    found = await repo.get_current_published(lt.id)
    assert found is not None and found.id == pub.id


async def test_get_for_update_locks_row(db_session: AsyncSession):
    lt = await _seed_log_type(db_session)
    repo = ParseRuleRepository(db_session)

    rule = ParseRule()
    rule.log_type_id = lt.id
    rule.version = 1
    rule.vrl_code = "."
    rule.engine_version = "0.32"
    rule.status = "draft"
    db_session.add(rule)
    await db_session.flush()

    locked = await repo.get_for_update(rule.id)
    assert locked is not None and locked.id == rule.id
