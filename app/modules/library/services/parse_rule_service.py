import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.schemas import ParseRuleCreate, ParseRuleUpdate


class ParseRuleService:
    def __init__(
        self,
        parse_rule_repo: ParseRuleRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._rules = parse_rule_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[ParseRule]:
        return await self._rules.list_by_log_type(log_type_id)

    async def get_by_id(self, rule_id: uuid.UUID) -> ParseRule:
        rule = await self._rules.get_by_id(rule_id)
        if rule is None:
            raise NotFoundError(f"parse rule not found: {rule_id}")
        return rule

    async def create_draft(
        self,
        log_type_id: uuid.UUID,
        data: ParseRuleCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> ParseRule:
        """Create a new draft parse rule version and point log_type.current at it."""
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        max_version = await self._rules.get_max_version(log_type_id)
        rule = ParseRule()
        rule.log_type_id = log_type_id
        rule.version = max_version + 1
        rule.vrl_code = data.vrl_code
        rule.engine_version = data.engine_version
        rule.notes = data.notes
        rule.status = "draft"
        rule.created_by = current_user_id
        rule = await self._rules.create(rule)

        log_type.current_parse_rule_id = rule.id
        log_type.status = "draft"
        await self._log_types.update(log_type)

        return rule

    async def update(self, rule_id: uuid.UUID, data: ParseRuleUpdate) -> ParseRule:
        rule = await self.get_by_id(rule_id)
        if rule.status == "published":
            raise ConflictError("cannot edit published parse rule")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)
        return await self._rules.update(rule)
