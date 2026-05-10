"""Pydantic schemas for Copilot chat."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

SkillName = Literal["log_explain", "vrl_generate", "vrl_optimize", "anomaly"]


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


class FieldSummary(BaseModel):
    name: str
    type: str
    required: bool


class ActiveLogTypeContext(BaseModel):
    name: str
    fields: list[FieldSummary] = Field(default_factory=list)
    samples_count: int = 0
    parse_rule_head: str | None = None


class VersionDiffContext(BaseModel):
    base_version: str
    head_version: str
    base_vrl: str | None = None
    head_vrl: str | None = None


class AnalyzerPageContext(BaseModel):
    page: Literal["analyzer"]
    vrl: str | None = None
    vrl_engine: str | None = None
    logs: list[str] = Field(default_factory=list)
    parse_results: list[ParseResult] = Field(default_factory=list)
    match_top_candidate: MatchHypothesis | None = None


class LibraryOverviewPageContext(BaseModel):
    page: Literal["library_overview"]
    filters: dict[str, str | None] = Field(default_factory=dict)
    vendor_count: int
    product_count: int
    # Front end derives this from existing OverviewProduct shape:
    #   is_empty=true OR log_type_counts.published===0
    products_missing_parse_rule: list[str] = Field(default_factory=list)


class LibraryProductPageContext(BaseModel):
    page: Literal["library_product"]
    vendor_slug: str
    product_slug: str
    product_status: str
    active_log_type: ActiveLogTypeContext | None = None


class LibraryVersionsPageContext(BaseModel):
    page: Literal["library_versions"]
    vendor_slug: str
    product_slug: str
    log_type_name: str
    diff: VersionDiffContext | None = None


PageContext = Annotated[
    AnalyzerPageContext
    | LibraryOverviewPageContext
    | LibraryProductPageContext
    | LibraryVersionsPageContext,
    Field(discriminator="page"),
]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    skill: SkillName | None = None
    page_context: PageContext | None = None


InlineMode = Literal["insert", "replace"]


class InlineVrlRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2_000)
    mode: InlineMode
    current_vrl: str = Field(default="", max_length=50_000)
    cursor_offset: int | None = Field(default=None, ge=0)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)
    vrl_engine: Literal["0.25", "0.32"] = "0.32"
    logs: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_offsets(self) -> "InlineVrlRequest":
        if self.mode == "insert":
            if self.cursor_offset is None or self.cursor_offset > len(self.current_vrl):
                raise ValueError("insert mode requires valid cursor_offset")
        else:  # replace
            if (
                self.selection_start is None
                or self.selection_end is None
                or self.selection_start >= self.selection_end
                or self.selection_end > len(self.current_vrl)
            ):
                raise ValueError("replace mode requires valid selection range")
        return self
