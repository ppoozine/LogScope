"""Pydantic schemas for llm_pipeline endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Doc
# =============================================================================

DocContentFormat = Literal["markdown"]
DocFetchedBy = Literal["manual", "crawler"]


class DocCreate(BaseModel):
    vendor_id: uuid.UUID
    url: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=500)
    content_format: DocContentFormat = "markdown"
    content: str = Field(min_length=1, max_length=200_000)


class DocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    url: str | None
    title: str | None
    content_format: DocContentFormat
    fetched_at: datetime
    fetched_by: DocFetchedBy
    created_at: datetime
    updated_at: datetime
    # NOTE: `content` intentionally omitted from list/read default; doc bodies are large.


class DocReadWithContent(DocRead):
    content: str


# =============================================================================
# Generate draft
# =============================================================================


class GenerateDraftRequest(BaseModel):
    doc_id: uuid.UUID
    product_id: uuid.UUID
    hint: str | None = Field(default=None, max_length=1000)


class GenerateDraftResponse(BaseModel):
    job_id: uuid.UUID
    log_type_id: uuid.UUID
    parse_rule_id: uuid.UUID


class GenerateDraftErrorPayload(BaseModel):
    """Body of 4xx/5xx response from generate endpoint."""

    job_id: uuid.UUID
    error_code: str
    error_message: str
