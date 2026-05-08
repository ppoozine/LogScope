"""POST /api/v1/analyzer/parse — run a VRL program against raw logs."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.clickhouse import get_clickhouse
from app.core.config import Settings, get_settings
from app.modules.analyzer.schemas import (
    CheckRequest,
    CheckResponse,
    FixtureListResponse,
    MatchAvailabilityResponse,
    ParseRequest,
    ParseResponse,
)
from app.modules.analyzer.services import fixtures_service, parser_service
from app.modules.analyzer.services.stats_recorder import (
    ParseEvent,
    StatsRecorder,
    hash16,
)
from app.modules.auth.models.user import User

router = APIRouter()


def get_stats_recorder() -> StatsRecorder:
    """FastAPI dep: bind a StatsRecorder to the current ClickHouse client (or None)."""
    return StatsRecorder(client=get_clickhouse())


@router.post("/parse", response_model=DataResponse[ParseResponse])
async def parse(
    body: ParseRequest,
    background: BackgroundTasks,
    recorder: Annotated[StatsRecorder, Depends(get_stats_recorder)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ParseResponse]:
    started = perf_counter()
    response = parser_service.run(
        vrl=body.vrl_code,
        logs=body.logs,
        engine=body.engine_version,
    )
    latency_ms = int((perf_counter() - started) * 1000)

    summary = response.summary
    event = ParseEvent(
        ts=datetime.now(UTC),
        log_type_id=body.log_type_id,
        parse_rule_id=body.parse_rule_id,
        engine_version=body.engine_version,
        total=summary.total if summary else 0,
        success=summary.success if summary else 0,
        error=summary.error if summary else 0,
        latency_ms=latency_ms,
        user_id=user.id,
        raw_log_hash=hash16(body.logs[0] if body.logs else ""),
        vrl_hash=hash16(body.vrl_code),
    )
    background.add_task(recorder.record, event)
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


@router.get("/match-availability", response_model=DataResponse[MatchAvailabilityResponse])
async def match_availability(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[MatchAvailabilityResponse]:
    return DataResponse(
        data=MatchAvailabilityResponse(available=bool(settings.anthropic_api_key)),
    )
