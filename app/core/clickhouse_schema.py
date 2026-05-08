"""ClickHouse schema bootstrap. Run once at app startup."""

from clickhouse_connect.driver.asyncclient import AsyncClient

PARSE_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS parse_events (
  ts             DateTime64(3, 'UTC'),
  log_type_id    Nullable(UUID),
  parse_rule_id  Nullable(UUID),
  engine_version LowCardinality(String),
  total          UInt32,
  success        UInt32,
  error          UInt32,
  latency_ms     UInt32,
  user_id        Nullable(UUID),
  raw_log_hash   FixedString(16),
  vrl_hash       FixedString(16)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (log_type_id, ts)
TTL toDateTime(ts) + INTERVAL 90 DAY
SETTINGS allow_nullable_key = 1
""".strip()


async def ensure_parse_events_table(client: AsyncClient) -> None:
    await client.command(PARSE_EVENTS_DDL)
