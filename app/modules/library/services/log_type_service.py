import uuid
from datetime import UTC, datetime

from app.common.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.common.utils.slug import slugify
from app.modules.library.models.log_type import LogType
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.schemas import LogTypeCreate, LogTypeUpdate


class LogTypeService:
    def __init__(
        self,
        log_type_repo: LogTypeRepository,
        product_repo: ProductRepository,
        parse_rule_repo: ParseRuleRepository,
    ) -> None:
        self._log_types = log_type_repo
        self._products = product_repo
        self._parse_rules = parse_rule_repo

    async def list_by_product(self, product_id: uuid.UUID) -> list[LogType]:
        return await self._log_types.list_by_product(product_id)

    async def get_by_id(self, log_type_id: uuid.UUID) -> LogType:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return log_type

    async def create(
        self,
        product_id: uuid.UUID,
        data: LogTypeCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> LogType:
        product = await self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"product not found: {product_id}")

        slug = data.slug or slugify(data.name)
        existing = await self._log_types.get_by_product_and_slug(product_id, slug)
        if existing is not None:
            raise ConflictError(f"log type slug already exists in product: {slug}")

        log_type = LogType()
        log_type.product_id = product_id
        log_type.name = data.name
        log_type.slug = slug
        log_type.format = data.format
        log_type.transport = data.transport
        log_type.description = data.description
        log_type.status = "draft"
        log_type.source = "manual"
        log_type.created_by = current_user_id
        return await self._log_types.create(log_type)

    async def update(self, log_type_id: uuid.UUID, data: LogTypeUpdate) -> LogType:
        log_type = await self.get_by_id(log_type_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(log_type, field, value)
        return await self._log_types.update(log_type)

    async def delete(self, log_type_id: uuid.UUID) -> None:
        log_type = await self.get_by_id(log_type_id)
        await self._log_types.delete(log_type)

    async def publish(self, log_type_id: uuid.UUID) -> LogType:
        """Publish flow: promote current draft parse rule to published."""
        log_type = await self.get_by_id(log_type_id)
        if log_type.current_parse_rule_id is None:
            raise ValidationError("no parse rule to publish")

        rule = await self._parse_rules.get_by_id(log_type.current_parse_rule_id)
        if rule is None:
            raise ValidationError("no parse rule to publish")
        if rule.status == "published":
            raise ConflictError("already published")

        rule.status = "published"
        await self._parse_rules.update(rule)

        log_type.status = "published"
        log_type.published_at = datetime.now(UTC)
        return await self._log_types.update(log_type)
