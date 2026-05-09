import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.parse_rule import ParseRule


class ParseRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, rule_id: uuid.UUID) -> ParseRule | None:
        result = await self._session.execute(select(ParseRule).where(ParseRule.id == rule_id))
        return result.scalar_one_or_none()

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[ParseRule]:
        stmt = select(ParseRule).where(ParseRule.log_type_id == log_type_id).order_by(ParseRule.version.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_max_version(self, log_type_id: uuid.UUID) -> int:
        stmt = select(func.max(ParseRule.version)).where(ParseRule.log_type_id == log_type_id)
        result = await self._session.execute(stmt)
        max_version = result.scalar_one_or_none()
        return max_version or 0

    async def create(self, rule: ParseRule) -> ParseRule:
        self._session.add(rule)
        await self._session.flush()
        await self._session.refresh(rule)
        return rule

    async def update(self, rule: ParseRule) -> ParseRule:
        await self._session.flush()
        await self._session.refresh(rule)
        return rule

    async def get_for_update(self, rule_id: uuid.UUID) -> ParseRule | None:
        """SELECT ... FOR UPDATE — locks the row in current transaction."""
        stmt = select(ParseRule).where(ParseRule.id == rule_id).with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_current_published(self, log_type_id: uuid.UUID) -> ParseRule | None:
        stmt = select(ParseRule).where(
            ParseRule.log_type_id == log_type_id,
            ParseRule.status == "published",
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
