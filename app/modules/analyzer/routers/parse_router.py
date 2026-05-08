"""POST /api/v1/analyzer/parse — run a VRL program against raw logs."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.modules.analyzer.schemas import (
    CheckRequest,
    CheckResponse,
    FixtureListResponse,
    ParseRequest,
    ParseResponse,
)
from app.modules.analyzer.services import fixtures_service, parser_service
from app.modules.auth.models.user import User

router = APIRouter()


@router.post("/parse", response_model=DataResponse[ParseResponse])
async def parse(
    body: ParseRequest,
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseResponse]:
    response = parser_service.run(
        vrl=body.vrl_code,
        logs=body.logs,
        engine=body.engine_version,
    )
    return DataResponse(data=response)


@router.get("/fixtures", response_model=DataResponse[FixtureListResponse])
async def list_fixtures(
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[FixtureListResponse]:
    return DataResponse(data=FixtureListResponse(fixtures=fixtures_service.list_fixtures()))


@router.post("/check", response_model=DataResponse[CheckResponse])
async def check(
    body: CheckRequest,
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[CheckResponse]:
    response = parser_service.check(vrl=body.vrl_code, engine=body.engine_version)
    return DataResponse(data=response)
