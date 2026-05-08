import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.schemas import (
    ParseRuleCreate,
    ParseRuleRead,
    ParseRuleUpdate,
)
from app.modules.library.services.parse_rule_service import ParseRuleService

router = APIRouter()


async def get_parse_rule_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParseRuleService:
    return ParseRuleService(
        ParseRuleRepository(session),
        LogTypeRepository(session),
    )


@router.get(
    "/log_types/{log_type_id}/parse_rules",
    response_model=DataResponse[list[ParseRuleRead]],
)
async def list_parse_rules(
    log_type_id: uuid.UUID,
    service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[ParseRuleRead]]:
    rules = await service.list_by_log_type(log_type_id)
    return DataResponse(data=[ParseRuleRead.model_validate(r) for r in rules])


@router.get(
    "/parse_rules/{rule_id}",
    response_model=DataResponse[ParseRuleRead],
)
async def get_parse_rule(
    rule_id: uuid.UUID,
    service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseRuleRead]:
    rule = await service.get_by_id(rule_id)
    return DataResponse(data=ParseRuleRead.model_validate(rule))


@router.post(
    "/log_types/{log_type_id}/parse_rules",
    response_model=DataResponse[ParseRuleRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_parse_rule_draft(
    log_type_id: uuid.UUID,
    body: ParseRuleCreate,
    service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseRuleRead]:
    rule = await service.create_draft(log_type_id, body, current_user_id=user.id)
    return DataResponse(data=ParseRuleRead.model_validate(rule))


@router.patch(
    "/parse_rules/{rule_id}",
    response_model=DataResponse[ParseRuleRead],
)
async def update_parse_rule(
    rule_id: uuid.UUID,
    body: ParseRuleUpdate,
    service: Annotated[ParseRuleService, Depends(get_parse_rule_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseRuleRead]:
    rule = await service.update(rule_id, body)
    return DataResponse(data=ParseRuleRead.model_validate(rule))
