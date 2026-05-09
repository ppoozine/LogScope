import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Common literal types
# =============================================================================

VendorStatus = Literal["active", "inactive"]
ProductStatus = Literal["active", "inactive"]
DeployType = Literal["cloud", "on_prem", "hybrid"]
LogTypeStatus = Literal["draft", "published"]
LogTypeSource = Literal["manual"]
LogFormat = Literal["syslog", "json", "cef", "leef", "csv", "other"]
LogTransport = Literal["syslog_udp", "syslog_tcp", "http", "file", "other"]
FieldType = Literal["string", "int", "float", "bool", "timestamp", "ip", "object", "array"]
EngineVersion = Literal["0.25", "0.32"]
ParseRuleStatus = Literal["draft", "published", "archived"]
SampleLabel = Literal["normal", "edge_case", "error"]


# =============================================================================
# Vendor
# =============================================================================


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100)
    website_url: str | None = None
    logo_url: str | None = None
    status: VendorStatus = "active"


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website_url: str | None = None
    logo_url: str | None = None
    status: VendorStatus | None = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    website_url: str | None
    logo_url: str | None
    status: VendorStatus
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Product
# =============================================================================


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=50)
    description: str | None = None
    deploy_type: DeployType | None = None
    doc_url: str | None = None
    status: ProductStatus = "active"


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: str | None = None
    description: str | None = None
    deploy_type: DeployType | None = None
    doc_url: str | None = None
    status: ProductStatus | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    slug: str
    version: str | None
    description: str | None
    deploy_type: DeployType | None
    doc_url: str | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime


# =============================================================================
# FieldSchema
# =============================================================================


class FieldSchemaItem(BaseModel):
    field_name: str = Field(min_length=1, max_length=100)
    field_type: FieldType
    description: str | None = None
    is_required: bool = False
    is_identifier: bool = False
    example_value: str | None = None
    sort_order: int = 0


class FieldSchemaBulkReplace(BaseModel):
    fields: list[FieldSchemaItem]


class FieldSchemaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_type_id: uuid.UUID
    field_name: str
    field_type: FieldType
    description: str | None
    is_required: bool
    is_identifier: bool
    example_value: str | None
    sort_order: int


# =============================================================================
# ParseRule
# =============================================================================


class ParseRuleCreate(BaseModel):
    vrl_code: str = Field(min_length=1)
    engine_version: EngineVersion
    notes: str | None = None


class ParseRuleUpdate(BaseModel):
    vrl_code: str | None = Field(default=None, min_length=1)
    engine_version: EngineVersion | None = None
    notes: str | None = None


class ParseRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_type_id: uuid.UUID
    version: int
    vrl_code: str
    engine_version: EngineVersion
    status: ParseRuleStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# SampleLog
# =============================================================================


class SampleLogCreate(BaseModel):
    raw_log: str = Field(min_length=1)
    label: SampleLabel = "normal"
    description: str | None = None


class SampleLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_type_id: uuid.UUID
    raw_log: str
    label: SampleLabel
    description: str | None
    created_at: datetime


# =============================================================================
# LogType
# =============================================================================


class LogTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=100)
    format: LogFormat
    transport: LogTransport | None = None
    description: str | None = None


class LogTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    format: LogFormat | None = None
    transport: LogTransport | None = None
    description: str | None = None


class LogTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    slug: str
    format: LogFormat
    transport: LogTransport | None
    status: LogTypeStatus
    source: LogTypeSource
    current_parse_rule_id: uuid.UUID | None
    description: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LogTypeDetail(LogTypeRead):
    """LogType + 內嵌 fields / current_parse_rule / samples（用於 detail endpoint）。"""

    fields: list[FieldSchemaRead]
    current_parse_rule: ParseRuleRead | None
    samples: list[SampleLogRead]


# =============================================================================
# Product Detail（nested）
# =============================================================================


class ProductDetail(ProductRead):
    """Product + 內嵌全部 log_types（含 fields / parse_rule / samples）。"""

    log_types: list[LogTypeDetail]


# =============================================================================
# Library Overview
# =============================================================================


class LogTypeCounts(BaseModel):
    total: int
    published: int
    draft: int


class OverviewProduct(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: ProductStatus
    log_type_counts: LogTypeCounts
    is_empty: bool


class OverviewVendor(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None


class OverviewVendorGroup(BaseModel):
    vendor: OverviewVendor
    products: list[OverviewProduct]


# =============================================================================
# Stats / Coverage
# =============================================================================

StatsRange = Literal["7d", "14d", "30d", "90d"]


class StatsRangeQuery(BaseModel):
    range: StatsRange = "7d"


class TimelinePoint(BaseModel):
    day: str  # YYYY-MM-DD
    total: int
    success: int
    error: int
    success_rate: float  # 0..1


class EngineUsage(BaseModel):
    engine_version: EngineVersion
    count: int


class StatsTotals(BaseModel):
    total: int
    success: int
    error: int
    success_rate: float


class LogTypeStats(BaseModel):
    enabled: bool
    range_days: int
    timeline: list[TimelinePoint]
    engine_usage: list[EngineUsage]
    totals: StatsTotals


class CoverageLogType(BaseModel):
    log_type_id: uuid.UUID
    sparkline: list[float]
    success_rate_avg: float
    volume: int


class ProductCoverage(BaseModel):
    enabled: bool
    range_days: int
    log_types: list[CoverageLogType]
