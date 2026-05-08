import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EngineVersion = Literal["0.25", "0.32"]
ParseResultStatus = Literal["success", "error"]
ParseKind = Literal["ok", "compile_error", "empty"]
CheckKind = Literal["ok", "compile_error"]


class ParseRequest(BaseModel):
    vrl_code: str = Field(min_length=1)
    logs: list[str] = Field(max_length=500)
    engine_version: EngineVersion = "0.32"
    log_type_id: uuid.UUID | None = None
    parse_rule_id: uuid.UUID | None = None


class ParseResultItem(BaseModel):
    index: int
    input: str
    status: ParseResultStatus
    output: dict[str, Any] | None = None
    error: str | None = None


class ParseSummary(BaseModel):
    total: int
    success: int
    error: int


class ParseResponse(BaseModel):
    kind: ParseKind
    engine: EngineVersion
    compile_error: str | None = None
    summary: ParseSummary | None = None
    results: list[ParseResultItem] = []


class CheckRequest(BaseModel):
    vrl_code: str = Field(min_length=1)
    engine_version: EngineVersion = "0.32"


class CheckResponse(BaseModel):
    kind: CheckKind
    engine: EngineVersion
    compile_error: str | None = None


class MatchRequest(BaseModel):
    raw_log: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=3, ge=1, le=10)


class MatchCandidate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vendor_slug: str
    product_slug: str
    log_type_id: uuid.UUID
    log_type_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class MatchResponse(BaseModel):
    candidates: list[MatchCandidate]


class FixtureItem(BaseModel):
    id: str
    name: str
    description: str
    vrl: str
    logs: str
    engine_version: EngineVersion = Field(alias="engine")

    model_config = ConfigDict(populate_by_name=True)


class FixtureListResponse(BaseModel):
    fixtures: list[FixtureItem]


class MatchAvailabilityResponse(BaseModel):
    available: bool
