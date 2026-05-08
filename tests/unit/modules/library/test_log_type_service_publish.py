"""LogTypeService.publish() should now delegate to ParseRuleService.promote()."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.common.exceptions import ValidationError
from app.modules.library.models.log_type import LogType
from app.modules.library.services.log_type_service import LogTypeService


def _log_type(*, current_rule_id) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
    lt.name = "LT"
    lt.slug = "lt"
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = current_rule_id
    return lt


async def test_publish_no_current_rule_raises():
    log_types = AsyncMock()
    log_types.get_by_id = AsyncMock(return_value=_log_type(current_rule_id=None))
    svc = LogTypeService(log_types, AsyncMock(), AsyncMock())
    with pytest.raises(ValidationError):
        await svc.publish(uuid.uuid4())


async def test_publish_calls_parse_rule_service_promote(monkeypatch):
    rule_id = uuid.uuid4()
    lt = _log_type(current_rule_id=rule_id)

    log_types = AsyncMock()
    log_types.get_by_id = AsyncMock(return_value=lt)

    rules = AsyncMock()
    promote_mock = AsyncMock()
    monkeypatch.setattr(
        "app.modules.library.services.log_type_service.ParseRuleService",
        lambda *a, **kw: type("S", (), {"promote": promote_mock})(),
    )

    products = AsyncMock()
    svc = LogTypeService(log_types, products, rules)
    await svc.publish(lt.id)
    promote_mock.assert_awaited_once_with(rule_id)
