"""Pydantic schemas for Copilot chat."""

from typing import Literal

from pydantic import BaseModel, Field

SkillName = Literal["log_explain", "vrl_generate"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ParseResult(BaseModel):
    index: int
    status: Literal["ok", "error"]
    message: str | None = None


class MatchHypothesis(BaseModel):
    vendor_slug: str
    product_slug: str
    log_type_name: str
    confidence: float


class PageContext(BaseModel):
    page: Literal["analyzer"]
    vrl: str | None = None
    vrl_engine: str | None = None
    logs: list[str] = Field(default_factory=list)
    parse_results: list[ParseResult] = Field(default_factory=list)
    match_top_candidate: MatchHypothesis | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    skill: SkillName | None = None
    page_context: PageContext | None = None
