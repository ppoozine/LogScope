# E2 LLM Draft Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an LLM-powered "library builder" — given a vendor doc + product context, call Anthropic with structured tool-use to produce one log_type + fields + parse_rule draft (status=`llm_draft`), with full audit trail and VRL compile validation.

**Architecture:** New `app/modules/llm_pipeline/` module (parallel to library / analyzer / copilot). Single sync HTTP endpoint blocks ~20s on Anthropic call → tool-use parses to typed payload → VRL compile-validate → 3-table transaction insert. 3-transaction pattern (pending job ➜ library writes + success ➜ failed-finish) keeps audit complete on any failure path. Refactors out shared `AsyncAnthropic` client to `app/core/deps.py` and VRL cheatsheet to `app/modules/copilot/services/_vrl_cheatsheet.py` for reuse.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, Pydantic v2, anthropic SDK ≥0.40, pyvrl-playground (engine 0.25 / 0.32), pytest + pytest-asyncio (auto mode).

**Spec:** `docs/superpowers/specs/2026-05-10-e2-llm-draft-generation-design.md` (commit `fb0ee46`).

---

## File structure

### New files (create)

```
app/core/
  deps.py                                            # get_anthropic_client() singleton

app/modules/copilot/services/
  _vrl_cheatsheet.py                                 # extracted VRL_CHEATSHEET str

app/modules/llm_pipeline/
  __init__.py
  exceptions.py                                      # LlmDraftError + 5 subclasses
  schemas.py                                         # Doc / GenerateDraft Pydantic
  models/
    __init__.py
    doc.py                                           # Doc ORM model
    llm_generation_job.py                            # LlmGenerationJob ORM model
  repositories/
    __init__.py
    doc_repository.py                                # insert / get / unique
    llm_generation_job_repository.py                 # 3-tx methods
  services/
    __init__.py
    doc_service.py                                   # upload + dedup
    vrl_validator.py                                 # wrapper over analyzer.vrl_runtime
    prompt_builder.py                                # tool schema + Block 1 + Block 2
    tool_use_parser.py                               # parse_tool_use + check_self_consistency
    llm_draft_service.py                             # orchestration
  routers/
    __init__.py
    doc_router.py                                    # POST /llm-pipeline/docs
    draft_router.py                                  # POST /llm-pipeline/drafts/generate
    throttle.py                                      # in-memory rate limit dep

app/alembic/versions/
  0006_add_docs_table.py
  0007_add_llm_generation_jobs_table.py
  0008_extend_log_types_for_llm.py
  0009_extend_parse_rules_for_llm.py
  0010_add_llm_lineage_fk_constraints.py

tests/unit/modules/llm_pipeline/
  __init__.py
  test_doc_repository.py
  test_doc_service.py
  test_doc_router.py
  test_exceptions.py
  test_vrl_validator.py
  test_llm_generation_job_repository.py
  test_prompt_builder.py
  test_tool_use_parser.py
  test_llm_draft_service.py
  test_draft_router.py
  test_throttle.py

tests/unit/core/
  test_deps.py                                       # get_anthropic_client singleton

tests/integration/modules/llm_pipeline/
  __init__.py
  test_e2_flow.py                                    # full happy + failure flows
```

### Existing files (modify)

```
app/core/config.py                                   # + llm_pipeline_draft_model setting
app/modules/copilot/services/prompt_builder.py       # import VRL_CHEATSHEET (no behavior change)
app/modules/copilot/routers/chat_router.py           # use deps.get_anthropic_client
app/modules/analyzer/routers/match_router.py         # use deps.get_anthropic_client
app/modules/library/schemas.py                       # extend status/source Literals
app/modules/library/models/log_type.py               # + source_job_id col
app/modules/library/models/parse_rule.py             # + source + source_job_id cols
app/api/v1/__init__.py                               # mount llm_pipeline routers
.env.example                                         # + LLM_PIPELINE_DRAFT_MODEL
```

---

## Milestone 0 — Settings + shared refactors

These are prerequisites: no new behavior, but unblock everything below. Each task should keep all existing tests green.

### Task 0.1: Add `llm_pipeline_draft_model` setting

**Files:**
- Modify: `app/core/config.py`
- Modify: `.env.example`
- Test: `tests/unit/core/test_config.py` (existing — augment)

- [ ] **Step 1: Read existing settings to find LLM-related fields**

```bash
grep -n "llm_copilot\|anthropic_api_key" app/core/config.py
```
Expected: list of existing `llm_copilot_*` settings with defaults.

- [ ] **Step 2: Add failing test**

In `tests/unit/core/test_config.py` add (or in equivalent existing test file):

```python
def test_llm_pipeline_draft_model_default() -> None:
    s = Settings(_env_file=None)  # no env loading
    assert s.llm_pipeline_draft_model == "claude-opus-4-7"


def test_llm_pipeline_draft_model_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PIPELINE_DRAFT_MODEL", "claude-sonnet-4-6")
    s = Settings(_env_file=None)
    assert s.llm_pipeline_draft_model == "claude-sonnet-4-6"
```

- [ ] **Step 3: Run, verify FAIL**

```bash
uv run pytest tests/unit/core/test_config.py -v -k llm_pipeline_draft_model
```
Expected: AttributeError or no attribute named `llm_pipeline_draft_model`.

- [ ] **Step 4: Add field to Settings**

In `app/core/config.py`, with the other `llm_copilot_*` fields, add:

```python
    llm_pipeline_draft_model: str = "claude-opus-4-7"
```

- [ ] **Step 5: Run tests pass**

```bash
uv run pytest tests/unit/core/test_config.py -v -k llm_pipeline_draft_model
```
Expected: 2 passed.

- [ ] **Step 6: Update `.env.example`**

Append:

```
# E2 LLM Pipeline draft model
LLM_PIPELINE_DRAFT_MODEL=claude-opus-4-7
```

- [ ] **Step 7: Commit**

```bash
git add app/core/config.py tests/unit/core/test_config.py .env.example
git commit -m "feat(llm-pipeline): add LLM_PIPELINE_DRAFT_MODEL setting"
```

---

### Task 0.2: Create `app/core/deps.py` with `get_anthropic_client()`

**Files:**
- Create: `app/core/deps.py`
- Test: `tests/unit/core/test_deps.py`

- [ ] **Step 1: Write failing test**

`tests/unit/core/test_deps.py`:

```python
from unittest.mock import patch

from app.core.deps import get_anthropic_client


class TestGetAnthropicClient:
    def test_returns_async_anthropic_instance(self):
        client = get_anthropic_client()
        assert client is not None
        assert hasattr(client, "messages")

    def test_singleton_returns_same_instance(self):
        c1 = get_anthropic_client()
        c2 = get_anthropic_client()
        assert c1 is c2

    def test_uses_settings_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-xyz")
        get_anthropic_client.cache_clear()  # type: ignore[attr-defined]
        client = get_anthropic_client()
        assert client.api_key == "test-key-xyz"
        get_anthropic_client.cache_clear()  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run, verify FAIL**

```bash
uv run pytest tests/unit/core/test_deps.py -v
```
Expected: ImportError (no module `app.core.deps`).

- [ ] **Step 3: Implement `app/core/deps.py`**

```python
"""Shared FastAPI dependencies / client singletons."""
from functools import lru_cache

import anthropic

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Singleton AsyncAnthropic client. Uses placeholder when api key unset
    so endpoints can short-circuit gracefully (see chat_service / draft_service)."""
    settings = get_settings()
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or "placeholder")
```

- [ ] **Step 4: Run, verify PASS**

```bash
uv run pytest tests/unit/core/test_deps.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/core/deps.py tests/unit/core/test_deps.py
git commit -m "feat(core): add get_anthropic_client singleton in deps"
```

---

### Task 0.3: Refactor copilot/chat_router to use `get_anthropic_client`

**Files:**
- Modify: `app/modules/copilot/routers/chat_router.py:33-59`
- Test: `tests/unit/modules/copilot/test_chat_router.py` (existing)

- [ ] **Step 1: Read current router DI**

```bash
sed -n '33,60p' app/modules/copilot/routers/chat_router.py
```

- [ ] **Step 2: Confirm existing tests pass before change**

```bash
uv run pytest tests/unit/modules/copilot/test_chat_router.py -v
```
Expected: all green (baseline).

- [ ] **Step 3: Modify router to inject anthropic client**

Replace `app/modules/copilot/routers/chat_router.py:33-59`:

```python
async def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[anthropic.AsyncAnthropic, Depends(get_anthropic_client)],
) -> ChatService:
    """Construct ChatService. Service short-circuits to error event when api
    key is unset, so the placeholder client is never actually called."""

    skill_models: dict[str, str] = {}
    if settings.llm_copilot_vrl_model:
        skill_models["vrl_generate"] = settings.llm_copilot_vrl_model
        skill_models["vrl_optimize"] = settings.llm_copilot_vrl_model
        skill_models["vrl_inline"] = settings.llm_copilot_vrl_model
        skill_models["vrl_fix"] = settings.llm_copilot_vrl_model
        skill_models["vrl_runtime_fix"] = settings.llm_copilot_vrl_model

    return ChatService(
        anthropic_client=cast(Any, client),
        anthropic_api_key=settings.anthropic_api_key,
        default_model=settings.llm_copilot_model,
        skill_models=skill_models,
        max_history=settings.llm_copilot_max_history,
        max_log_lines_in_context=settings.llm_copilot_max_log_lines_in_context,
        max_vrl_chars_in_context=settings.llm_copilot_max_vrl_chars_in_context,
        max_library_products_in_context=settings.llm_copilot_max_library_products_in_context,
    )
```

Add import at top:

```python
from app.core.deps import get_anthropic_client
```

- [ ] **Step 4: Run copilot tests**

```bash
uv run pytest tests/unit/modules/copilot/test_chat_router.py tests/integration/modules/copilot/ -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add app/modules/copilot/routers/chat_router.py
git commit -m "refactor(copilot): use shared get_anthropic_client dep"
```

---

### Task 0.4: Refactor analyzer/match_router to use `get_anthropic_client`

**Files:**
- Modify: `app/modules/analyzer/routers/match_router.py:25-40`
- Test: `tests/unit/modules/analyzer/test_match_router.py` (existing)

- [ ] **Step 1: Read existing match_router**

```bash
sed -n '20,45p' app/modules/analyzer/routers/match_router.py
```

- [ ] **Step 2: Modify analogous to Task 0.3**

Replace the `client = anthropic.AsyncAnthropic(...)` construction with `Depends(get_anthropic_client)` injection. Add `from app.core.deps import get_anthropic_client` to imports. Drop the now-unused `import anthropic` if it has no other uses in the file.

- [ ] **Step 3: Run analyzer tests**

```bash
uv run pytest tests/unit/modules/analyzer/ tests/integration/modules/analyzer/ -v
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add app/modules/analyzer/routers/match_router.py
git commit -m "refactor(analyzer): use shared get_anthropic_client dep"
```

---

### Task 0.5: Extract VRL cheatsheet from copilot prompt_builder

**Files:**
- Create: `app/modules/copilot/services/_vrl_cheatsheet.py`
- Modify: `app/modules/copilot/services/prompt_builder.py` (replace inline cheatsheet block with import)
- Test: `tests/unit/modules/copilot/test_prompt_builder.py` (existing snapshot tests catch drift)

- [ ] **Step 1: Locate the cheatsheet block**

The cheatsheet lives inside `_BLOCK1_VRL_GENERATE` in `app/modules/copilot/services/prompt_builder.py`. It is the section starting with `## VRL function cheatsheet (engine 0.32)` and ending just before `## Process (follow in order)`.

```bash
sed -n '92,130p' app/modules/copilot/services/prompt_builder.py
```

- [ ] **Step 2: Run baseline tests**

```bash
uv run pytest tests/unit/modules/copilot/test_prompt_builder.py -v
```
Expected: all green.

- [ ] **Step 3: Create cheatsheet module**

`app/modules/copilot/services/_vrl_cheatsheet.py`:

```python
"""Shared VRL function cheatsheet — used by copilot vrl_generate and llm_pipeline draft prompts.

Keep this string byte-identical with what shipped in copilot D2 (commit 589b0d3) so
downstream prompt-cache hits remain valid.
"""

VRL_CHEATSHEET = """## VRL function cheatsheet (engine 0.32)

These are the functions you should reach for first. Do NOT invent
function names — if it's not here and you're not sure, say so.

- `parse_syslog!(.message)` — parses RFC 5424/3164 header into root.
  Sets `.appname`, `.hostname`, `.severity`, `.facility`, `.timestamp`,
  and leaves the body as `.message`.
- `parse_json!(.message)` — parses a JSON object; fields become root
  fields. Use `??` if some logs aren't JSON.
- `parse_key_value!(.message, key_value_delimiter: "=", field_delimiter: " ")`
  — k=v pairs (CEF, many SIEM formats).
- `parse_regex!(string, r'(?P<name>regex)')` — named capture groups
  return a map. Use for vendor-specific layouts.
- `parse_csv!(string)` — string array; index `[0]`, `[1]`...
- `split(string, ",")` — same shape as parse_csv but no quoting rules.
- Conversion: `to_int!`, `to_float!`, `to_bool!`, `to_string!`,
  `to_timestamp!(s, "%Y-%m-%d %H:%M:%S")` (strptime format).
- `del(.field)` — remove a field (use for redaction or cleanup).
- `if exists(.field) { ... }` — conditional on optional fields.
- `string!(.x)` — coerce/assert a value is string (use before `split`).

### Suffixes — get this right or it won't compile

- `!` — fail-fast: aborts the whole event if the call errors. Use when
  the input is structurally guaranteed (e.g., `parse_json!` after you've
  established the log IS json).
- `??` — fallback: returns the right-hand value on error.
  `parse_json(.x) ?? {}` never aborts; you can then check fields.
- Functions that return a `Result` (almost all parse_* and to_*) MUST
  use `!` or `??`. Bare calls are compile errors.

### 0.25 vs 0.32 syntax

Default to 0.32 unless `<facts><vrl_engine>` says otherwise.
- 0.32 added `parse_key_value`; on 0.25 use `parse_kv` instead.
- Both support `parse_syslog`, `parse_json`, `parse_regex`, `split`."""
```

(Copy text byte-for-byte from `prompt_builder._BLOCK1_VRL_GENERATE`. The existing snapshot tests will catch drift.)

- [ ] **Step 4: Replace inline block in prompt_builder.py**

In `app/modules/copilot/services/prompt_builder.py`, replace the inline cheatsheet section of `_BLOCK1_VRL_GENERATE` with an interpolation:

```python
from app.modules.copilot.services._vrl_cheatsheet import VRL_CHEATSHEET

_BLOCK1_VRL_GENERATE = f"""
# Skill: vrl_generate

You are generating VRL (Vector Remap Language) parse rules. The user has
raw logs in <logs> and possibly partial VRL in <current_vrl>.

{VRL_CHEATSHEET}

## Process (follow in order)
... (rest unchanged) ...
"""
```

(Keep the rest of the file identical. Move only the cheatsheet section into the imported constant.)

- [ ] **Step 5: Run snapshot tests**

```bash
uv run pytest tests/unit/modules/copilot/test_prompt_builder.py -v
```
Expected: all green (string output unchanged byte-for-byte).

If snapshot test compares hashes/strings, ensure the f-string produces identical output (no extra leading/trailing newline). If a snapshot diff appears, do not regenerate snapshots — fix the f-string until it matches.

- [ ] **Step 6: Commit**

```bash
git add app/modules/copilot/services/_vrl_cheatsheet.py app/modules/copilot/services/prompt_builder.py
git commit -m "refactor(copilot): extract VRL cheatsheet to shared module"
```

---

## Milestone 1 — Library Pydantic schema extensions

No DB migration; just widen the `Literal` types.

### Task 1.1: Extend library schemas with `llm_draft` / `llm_generated` / `ParseRuleSource`

**Files:**
- Modify: `app/modules/library/schemas.py:14-21`
- Test: `tests/unit/modules/library/test_schemas.py` (create or extend)

- [ ] **Step 1: Write failing test**

In `tests/unit/modules/library/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.modules.library.schemas import (
    FieldSchemaItem,
    LogTypeRead,
    ParseRuleRead,
)


class TestStatusEnumExtensions:
    def test_log_type_status_accepts_llm_draft(self):
        # build minimal LogTypeRead instance with status='llm_draft'
        from datetime import datetime, UTC
        from uuid import uuid4

        lt = LogTypeRead.model_validate({
            "id": uuid4(), "product_id": uuid4(),
            "name": "x", "slug": "x", "format": "json", "transport": None,
            "status": "llm_draft", "source": "llm_generated",
            "current_parse_rule_id": None, "description": None,
            "published_at": None,
            "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
        })
        assert lt.status == "llm_draft"
        assert lt.source == "llm_generated"

    def test_parse_rule_status_accepts_llm_draft(self):
        from datetime import datetime, UTC
        from uuid import uuid4

        pr = ParseRuleRead.model_validate({
            "id": uuid4(), "log_type_id": uuid4(), "version": 1,
            "vrl_code": ". = parse_json!(.message)",
            "engine_version": "0.32",
            "status": "llm_draft", "source": "llm_generated",
            "notes": None,
            "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
        })
        assert pr.status == "llm_draft"
        assert pr.source == "llm_generated"

    def test_parse_rule_source_rejects_unknown(self):
        from datetime import datetime, UTC
        from uuid import uuid4

        with pytest.raises(ValidationError):
            ParseRuleRead.model_validate({
                "id": uuid4(), "log_type_id": uuid4(), "version": 1,
                "vrl_code": "x", "engine_version": "0.32",
                "status": "draft", "source": "stolen",
                "notes": None,
                "created_at": datetime.now(UTC), "updated_at": datetime.now(UTC),
            })
```

- [ ] **Step 2: Run, verify FAIL**

```bash
uv run pytest tests/unit/modules/library/test_schemas.py -v -k Status
```
Expected: ValidationError on `llm_draft` / `llm_generated` (not in current Literal).

- [ ] **Step 3: Modify `app/modules/library/schemas.py`**

Replace lines 14-21 (the literal type aliases):

```python
LogTypeStatus = Literal["draft", "llm_draft", "published"]
LogTypeSource = Literal["manual", "llm_generated"]
DeployType = Literal["cloud", "on_prem", "hybrid"]
LogFormat = Literal["syslog", "json", "cef", "leef", "csv", "other"]
LogTransport = Literal["syslog_udp", "syslog_tcp", "http", "file", "other"]
FieldType = Literal["string", "int", "float", "bool", "timestamp", "ip", "object", "array"]
EngineVersion = Literal["0.25", "0.32"]
ParseRuleStatus = Literal["draft", "llm_draft", "published", "archived"]
ParseRuleSource = Literal["manual", "llm_generated"]
SampleLabel = Literal["normal", "edge_case", "error"]
VendorStatus = Literal["active", "inactive"]
ProductStatus = Literal["active", "inactive"]
```

Add `source: ParseRuleSource` to `ParseRuleRead`:

```python
class ParseRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_type_id: uuid.UUID
    version: int
    vrl_code: str
    engine_version: EngineVersion
    status: ParseRuleStatus
    source: ParseRuleSource           # NEW
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/unit/modules/library/test_schemas.py -v -k Status
uv run pytest tests/unit/modules/library/ tests/integration/modules/library/ -v
```
Expected: new tests pass; existing library tests still pass.

If integration tests construct `ParseRuleRead` from a model that doesn't have `source` yet — they will fail. **That's expected**; Task 3.4 adds the column. For now, mark this milestone as "schemas extended; model migration in M3". To keep tests green now: defer the `source` field on `ParseRuleRead` to Task 3.4 step where the column also lands. Until then, only widen the existing Literals.

**Action:** at this step, only widen Literals. Hold off on adding `source: ParseRuleSource` to `ParseRuleRead` until Task 3.4.

- [ ] **Step 5: Commit**

```bash
git add app/modules/library/schemas.py tests/unit/modules/library/test_schemas.py
git commit -m "feat(library): allow llm_draft status and llm_generated source literals"
```

---

## Milestone 2 — Database migrations

5 sequential migrations. Each migration must have working `upgrade()` AND `downgrade()`. After each migration, run `uv run alembic upgrade head` then `uv run alembic downgrade -1` then `uv run alembic upgrade head` to confirm round-trip.

### Task 2.1: Migration 0006 — `add_docs_table`

**Files:**
- Create: `app/alembic/versions/0006_add_docs_table.py`

- [ ] **Step 1: Read 0005 for style reference**

```bash
cat app/alembic/versions/0005_parse_rule_archived_status.py
```

- [ ] **Step 2: Write migration**

`app/alembic/versions/0006_add_docs_table.py`:

```python
"""add docs table

Revision ID: 0006_add_docs_table
Revises: 0005_parse_rule_archived_status
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import add_updated_at_trigger, drop_updated_at_trigger

revision: str = "0006_add_docs_table"
down_revision: str | None = "0005_parse_rule_archived_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "content_format",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'markdown'"),
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "fetched_by",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "docs_content_format_check",
        "docs",
        "content_format IN ('markdown')",
    )
    op.create_check_constraint(
        "docs_fetched_by_check",
        "docs",
        "fetched_by IN ('manual', 'crawler')",
    )
    op.create_index("ix_docs_vendor_id_created_at", "docs", ["vendor_id", sa.text("created_at DESC")])
    op.create_index(
        "uq_docs_vendor_url",
        "docs",
        ["vendor_id", "url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL"),
    )
    add_updated_at_trigger("docs")


def downgrade() -> None:
    drop_updated_at_trigger("docs")
    op.drop_index("uq_docs_vendor_url", table_name="docs")
    op.drop_index("ix_docs_vendor_id_created_at", table_name="docs")
    op.drop_table("docs")
```

- [ ] **Step 3: Apply / round-trip**

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: clean upgrade/downgrade with no errors.

- [ ] **Step 4: Verify table exists**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from app.core.database import async_engine

async def main():
    async with async_engine().connect() as conn:
        r = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name='docs'\"))
        print(r.fetchall())

asyncio.run(main())
"
```
Expected: `[('docs',)]`.

- [ ] **Step 5: Commit**

```bash
git add app/alembic/versions/0006_add_docs_table.py
git commit -m "feat(llm-pipeline): add docs table migration"
```

---

### Task 2.2: Migration 0007 — `add_llm_generation_jobs_table`

**Files:**
- Create: `app/alembic/versions/0007_add_llm_generation_jobs_table.py`

- [ ] **Step 1: Write migration**

```python
"""add llm_generation_jobs table (FK constraints to log_types/parse_rules added in 0010)

Revision ID: 0007_add_llm_generation_jobs_table
Revises: 0006_add_docs_table
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import add_updated_at_trigger, drop_updated_at_trigger

revision: str = "0007_add_llm_generation_jobs_table"
down_revision: str | None = "0006_add_docs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("docs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("raw_response", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cache_read_tokens", sa.Integer, nullable=True),
        # FK constraints added in 0010 to break circular dep
        sa.Column("log_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parse_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "llm_generation_jobs_status_check",
        "llm_generation_jobs",
        "status IN ('pending', 'succeeded', 'failed')",
    )
    op.create_index(
        "ix_llm_generation_jobs_product_status_started",
        "llm_generation_jobs",
        ["product_id", "status", sa.text("started_at DESC")],
    )
    add_updated_at_trigger("llm_generation_jobs")


def downgrade() -> None:
    drop_updated_at_trigger("llm_generation_jobs")
    op.drop_index(
        "ix_llm_generation_jobs_product_status_started",
        table_name="llm_generation_jobs",
    )
    op.drop_table("llm_generation_jobs")
```

- [ ] **Step 2: Apply / round-trip**

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add app/alembic/versions/0007_add_llm_generation_jobs_table.py
git commit -m "feat(llm-pipeline): add llm_generation_jobs audit table migration"
```

---

### Task 2.3: Migration 0008 — `extend_log_types_for_llm`

**Files:**
- Create: `app/alembic/versions/0008_extend_log_types_for_llm.py`

- [ ] **Step 1: Write migration**

```python
"""extend log_types: status/source CHECKs include llm_draft/llm_generated; add source_job_id

Revision ID: 0008_extend_log_types_for_llm
Revises: 0007_add_llm_generation_jobs_table
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_extend_log_types_for_llm"
down_revision: str | None = "0007_add_llm_generation_jobs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop existing CHECKs if any (init migration didn't add them; defensive)
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_status_check"
    )
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_source_check"
    )

    op.create_check_constraint(
        "log_types_status_check",
        "log_types",
        "status IN ('draft', 'llm_draft', 'published')",
    )
    op.create_check_constraint(
        "log_types_source_check",
        "log_types",
        "source IN ('manual', 'llm_generated')",
    )

    # source_job_id — FK constraint added in 0010
    op.add_column(
        "log_types",
        sa.Column("source_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("log_types", "source_job_id")
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_status_check"
    )
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_source_check"
    )
    # Restore narrower CHECKs
    op.create_check_constraint(
        "log_types_status_check",
        "log_types",
        "status IN ('draft', 'published')",
    )
    op.create_check_constraint(
        "log_types_source_check",
        "log_types",
        "source IN ('manual')",
    )
```

- [ ] **Step 2: Apply / round-trip**

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add app/alembic/versions/0008_extend_log_types_for_llm.py
git commit -m "feat(library): extend log_types CHECKs for llm_draft and add source_job_id"
```

---

### Task 2.4: Migration 0009 — `extend_parse_rules_for_llm`

**Files:**
- Create: `app/alembic/versions/0009_extend_parse_rules_for_llm.py`

- [ ] **Step 1: Write migration**

```python
"""extend parse_rules: status CHECK includes llm_draft; add source + source_job_id

Revision ID: 0009_extend_parse_rules_for_llm
Revises: 0008_extend_log_types_for_llm
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_extend_parse_rules_for_llm"
down_revision: str | None = "0008_extend_log_types_for_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'llm_draft', 'published', 'archived')",
    )

    op.add_column(
        "parse_rules",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
    )
    op.create_check_constraint(
        "parse_rules_source_check",
        "parse_rules",
        "source IN ('manual', 'llm_generated')",
    )
    op.add_column(
        "parse_rules",
        sa.Column("source_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parse_rules", "source_job_id")
    op.drop_constraint("parse_rules_source_check", "parse_rules", type_="check")
    op.drop_column("parse_rules", "source")
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published', 'archived')",
    )
```

- [ ] **Step 2: Apply / round-trip**

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add app/alembic/versions/0009_extend_parse_rules_for_llm.py
git commit -m "feat(library): extend parse_rules with llm_draft status, source col, source_job_id"
```

---

### Task 2.5: Migration 0010 — `add_llm_lineage_fk_constraints`

**Files:**
- Create: `app/alembic/versions/0010_add_llm_lineage_fk_constraints.py`

- [ ] **Step 1: Write migration**

```python
"""add 4 FK constraints to break circular dep between llm_generation_jobs and library tables

Revision ID: 0010_add_llm_lineage_fk_constraints
Revises: 0009_extend_parse_rules_for_llm
Create Date: 2026-05-10
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010_add_llm_lineage_fk_constraints"
down_revision: str | None = "0009_extend_parse_rules_for_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_log_types_source_job",
        "log_types",
        "llm_generation_jobs",
        ["source_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_parse_rules_source_job",
        "parse_rules",
        "llm_generation_jobs",
        ["source_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_jobs_log_type",
        "llm_generation_jobs",
        "log_types",
        ["log_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_jobs_parse_rule",
        "llm_generation_jobs",
        "parse_rules",
        ["parse_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_llm_jobs_parse_rule", "llm_generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_llm_jobs_log_type", "llm_generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_parse_rules_source_job", "parse_rules", type_="foreignkey")
    op.drop_constraint("fk_log_types_source_job", "log_types", type_="foreignkey")
```

- [ ] **Step 2: Apply / round-trip**

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add app/alembic/versions/0010_add_llm_lineage_fk_constraints.py
git commit -m "feat(llm-pipeline): add 4 FK constraints for log_types/parse_rules/jobs lineage"
```

---

## Milestone 3 — ORM models

### Task 3.1: Doc model

**Files:**
- Create: `app/modules/llm_pipeline/__init__.py` (empty)
- Create: `app/modules/llm_pipeline/models/__init__.py` (empty)
- Create: `app/modules/llm_pipeline/models/doc.py`
- Test: `tests/unit/modules/llm_pipeline/__init__.py` (empty)
- Test: `tests/unit/modules/llm_pipeline/test_models.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p app/modules/llm_pipeline/models app/modules/llm_pipeline/repositories app/modules/llm_pipeline/services app/modules/llm_pipeline/routers
mkdir -p tests/unit/modules/llm_pipeline tests/integration/modules/llm_pipeline
touch app/modules/llm_pipeline/__init__.py
touch app/modules/llm_pipeline/models/__init__.py
touch app/modules/llm_pipeline/repositories/__init__.py
touch app/modules/llm_pipeline/services/__init__.py
touch app/modules/llm_pipeline/routers/__init__.py
touch tests/unit/modules/llm_pipeline/__init__.py
touch tests/integration/modules/llm_pipeline/__init__.py
```

- [ ] **Step 2: Write Doc model**

`app/modules/llm_pipeline/models/doc.py`:

```python
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class Doc(Base, TimestampMixin):
    __tablename__ = "docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="markdown"
    )
    fetched_at: Mapped["datetime"] = mapped_column(
        nullable=False
    )
    fetched_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
```

(Pydantic-style import for `datetime`: add `from datetime import datetime` and `from sqlalchemy import DateTime`; `fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)`. Match style of other models in `app/modules/library/models/`.)

Final correct version:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class Doc(Base, TimestampMixin):
    __tablename__ = "docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="markdown"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fetched_by: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
```

- [ ] **Step 3: Re-export in `models/__init__.py`**

`app/modules/llm_pipeline/models/__init__.py`:

```python
from app.modules.llm_pipeline.models.doc import Doc

__all__ = ["Doc"]
```

- [ ] **Step 4: Smoke test the model**

`tests/unit/modules/llm_pipeline/test_models.py`:

```python
from app.modules.llm_pipeline.models import Doc


def test_doc_table_name():
    assert Doc.__tablename__ == "docs"


def test_doc_columns_exist():
    cols = {c.name for c in Doc.__table__.columns}
    expected = {
        "id", "vendor_id", "url", "title", "content",
        "content_format", "fetched_at", "fetched_by",
        "created_at", "updated_at",
    }
    assert expected.issubset(cols)
```

- [ ] **Step 5: Run**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_models.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add app/modules/llm_pipeline/ tests/unit/modules/llm_pipeline/__init__.py tests/unit/modules/llm_pipeline/test_models.py tests/integration/modules/llm_pipeline/__init__.py
git commit -m "feat(llm-pipeline): scaffold module + Doc ORM model"
```

---

### Task 3.2: LlmGenerationJob model

**Files:**
- Create: `app/modules/llm_pipeline/models/llm_generation_job.py`
- Modify: `app/modules/llm_pipeline/models/__init__.py`
- Modify: `tests/unit/modules/llm_pipeline/test_models.py`

- [ ] **Step 1: Write model**

`app/modules/llm_pipeline/models/llm_generation_job.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class LlmGenerationJob(Base, TimestampMixin):
    __tablename__ = "llm_generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("docs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    parse_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parse_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: Re-export**

Update `app/modules/llm_pipeline/models/__init__.py`:

```python
from app.modules.llm_pipeline.models.doc import Doc
from app.modules.llm_pipeline.models.llm_generation_job import LlmGenerationJob

__all__ = ["Doc", "LlmGenerationJob"]
```

- [ ] **Step 3: Smoke tests**

Append to `tests/unit/modules/llm_pipeline/test_models.py`:

```python
from app.modules.llm_pipeline.models import LlmGenerationJob


def test_llm_generation_job_table_name():
    assert LlmGenerationJob.__tablename__ == "llm_generation_jobs"


def test_llm_generation_job_columns_exist():
    cols = {c.name for c in LlmGenerationJob.__table__.columns}
    expected = {
        "id", "doc_id", "product_id", "requested_by", "status", "model",
        "error_code", "error_message", "raw_response",
        "input_tokens", "output_tokens", "cache_read_tokens",
        "log_type_id", "parse_rule_id",
        "started_at", "finished_at", "created_at", "updated_at",
    }
    assert expected.issubset(cols)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_models.py -v
git add app/modules/llm_pipeline/models/llm_generation_job.py app/modules/llm_pipeline/models/__init__.py tests/unit/modules/llm_pipeline/test_models.py
git commit -m "feat(llm-pipeline): add LlmGenerationJob ORM model"
```

---

### Task 3.3: Update LogType model — add `source_job_id`

**Files:**
- Modify: `app/modules/library/models/log_type.py`

- [ ] **Step 1: Add column to model**

After the existing `source` column line, add:

```python
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "llm_generation_jobs.id",
            use_alter=True,
            name="fk_log_types_source_job",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
```

(`use_alter=True` because the FK is added in migration 0010 separately. SQLAlchemy uses this hint when emitting CREATE TABLE in tests via `Base.metadata.create_all`.)

- [ ] **Step 2: Run library tests**

```bash
uv run pytest tests/unit/modules/library/ tests/integration/modules/library/ -v
```
Expected: all green (column is nullable, default NULL — no test breaks).

- [ ] **Step 3: Commit**

```bash
git add app/modules/library/models/log_type.py
git commit -m "feat(library): add log_types.source_job_id FK to llm_generation_jobs"
```

---

### Task 3.4: Update ParseRule model — add `source` + `source_job_id`

**Files:**
- Modify: `app/modules/library/models/parse_rule.py`
- Modify: `app/modules/library/schemas.py` (add `source` to `ParseRuleRead`)
- Test: `tests/unit/modules/library/test_schemas.py` (add the test deferred from Task 1.1)

- [ ] **Step 1: Add columns to model**

After the `status` column line in `ParseRule`:

```python
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "llm_generation_jobs.id",
            use_alter=True,
            name="fk_parse_rules_source_job",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
```

- [ ] **Step 2: Add `source` field to `ParseRuleRead` schema**

In `app/modules/library/schemas.py`, in `ParseRuleRead`, add `source: ParseRuleSource` (after `status`).

- [ ] **Step 3: Add the deferred test from Task 1.1**

(See Task 1.1 step 3 — add the `test_parse_rule_status_accepts_llm_draft` test to `tests/unit/modules/library/test_schemas.py`.)

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/unit/modules/library/ tests/integration/modules/library/ -v
```
Expected: green. If any fixture creates `ParseRule()` without `source`, the default kicks in. If any creates `ParseRuleRead.model_validate(parse_rule_orm)`, the column reads from DB and is `'manual'` by default.

- [ ] **Step 5: Commit**

```bash
git add app/modules/library/models/parse_rule.py app/modules/library/schemas.py tests/unit/modules/library/test_schemas.py
git commit -m "feat(library): add parse_rules.source and source_job_id"
```

---

## Milestone 4 — llm_pipeline Pydantic schemas

### Task 4.1: `schemas.py` — Doc + GenerateDraft

**Files:**
- Create: `app/modules/llm_pipeline/schemas.py`
- Test: `tests/unit/modules/llm_pipeline/test_schemas.py`

- [ ] **Step 1: Write tests**

`tests/unit/modules/llm_pipeline/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.modules.llm_pipeline.schemas import (
    DocCreate,
    GenerateDraftRequest,
)


class TestDocCreate:
    def test_minimal(self):
        d = DocCreate(
            vendor_id="00000000-0000-0000-0000-000000000001",
            content="# hello\nworld",
        )
        assert d.content_format == "markdown"

    def test_rejects_unknown_format(self):
        with pytest.raises(ValidationError):
            DocCreate(
                vendor_id="00000000-0000-0000-0000-000000000001",
                content="x",
                content_format="pdf",
            )

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            DocCreate(
                vendor_id="00000000-0000-0000-0000-000000000001",
                content="x" * 200001,
            )


class TestGenerateDraftRequest:
    def test_minimal(self):
        r = GenerateDraftRequest(
            doc_id="00000000-0000-0000-0000-000000000001",
            product_id="00000000-0000-0000-0000-000000000002",
        )
        assert r.hint is None

    def test_hint_max_length(self):
        with pytest.raises(ValidationError):
            GenerateDraftRequest(
                doc_id="00000000-0000-0000-0000-000000000001",
                product_id="00000000-0000-0000-0000-000000000002",
                hint="x" * 1001,
            )
```

- [ ] **Step 2: Run, verify FAIL (ImportError)**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_schemas.py -v
```

- [ ] **Step 3: Write `schemas.py`**

`app/modules/llm_pipeline/schemas.py`:

```python
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
```

- [ ] **Step 4: Run, verify PASS + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_schemas.py -v
git add app/modules/llm_pipeline/schemas.py tests/unit/modules/llm_pipeline/test_schemas.py
git commit -m "feat(llm-pipeline): add Pydantic schemas for Doc and GenerateDraft"
```

---

## Milestone 5 — Doc upload (smallest E2E slice)

### Task 5.1: `doc_repository`

**Files:**
- Create: `app/modules/llm_pipeline/repositories/doc_repository.py`
- Test: `tests/unit/modules/llm_pipeline/test_doc_repository.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/modules/llm_pipeline/test_doc_repository.py
import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository


pytestmark = pytest.mark.asyncio


async def _seed_vendor(session) -> Vendor:
    v = Vendor(
        id=uuid.uuid4(), name="acme", slug=f"acme-{uuid.uuid4().hex[:8]}",
        status="active",
    )
    session.add(v)
    await session.flush()
    return v


class TestDocRepository:
    async def test_create_and_get(self, db_session):
        v = await _seed_vendor(db_session)
        repo = DocRepository(db_session)
        doc = Doc(
            id=uuid.uuid4(), vendor_id=v.id, url="https://x/a",
            title="t", content="# h", content_format="markdown",
            fetched_at=datetime.now(UTC), fetched_by="manual",
        )
        created = await repo.create(doc)
        assert created.id == doc.id
        fetched = await repo.get_by_id(doc.id)
        assert fetched is not None
        assert fetched.content == "# h"

    async def test_unique_vendor_url_conflict(self, db_session):
        v = await _seed_vendor(db_session)
        repo = DocRepository(db_session)
        d1 = Doc(
            id=uuid.uuid4(), vendor_id=v.id, url="https://x/dup",
            content="1", content_format="markdown",
            fetched_at=datetime.now(UTC), fetched_by="manual",
        )
        await repo.create(d1)
        d2 = Doc(
            id=uuid.uuid4(), vendor_id=v.id, url="https://x/dup",
            content="2", content_format="markdown",
            fetched_at=datetime.now(UTC), fetched_by="manual",
        )
        with pytest.raises(IntegrityError):
            await repo.create(d2)

    async def test_null_url_allows_duplicates(self, db_session):
        v = await _seed_vendor(db_session)
        repo = DocRepository(db_session)
        for _ in range(2):
            d = Doc(
                id=uuid.uuid4(), vendor_id=v.id, url=None,
                content="x", content_format="markdown",
                fetched_at=datetime.now(UTC), fetched_by="manual",
            )
            await repo.create(d)
        # no exception expected
```

(`db_session` fixture — confirm name in `tests/conftest.py`. If named differently — e.g. `session` — adjust uniformly.)

- [ ] **Step 2: Run, verify FAIL**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_doc_repository.py -v
```

- [ ] **Step 3: Implement repo**

`app/modules/llm_pipeline/repositories/doc_repository.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_pipeline.models import Doc


class DocRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, doc: Doc) -> Doc:
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Doc | None:
        return await self._session.get(Doc, doc_id)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_doc_repository.py -v
git add app/modules/llm_pipeline/repositories/doc_repository.py tests/unit/modules/llm_pipeline/test_doc_repository.py
git commit -m "feat(llm-pipeline): add DocRepository with create/get_by_id"
```

---

### Task 5.2: `doc_service.upload_doc`

**Files:**
- Create: `app/modules/llm_pipeline/services/doc_service.py`
- Create: `app/common/exceptions.py` if `ConflictError` doesn't yet exist (else reuse)
- Test: `tests/unit/modules/llm_pipeline/test_doc_service.py`

- [ ] **Step 1: Inspect existing exception types**

```bash
grep -n "class.*Error\|class.*Exception" app/common/exceptions.py
```

If `ConflictError` (or similar 409) already exists, reuse. Else add a new subclass.

- [ ] **Step 2: Write tests**

```python
# tests/unit/modules/llm_pipeline/test_doc_service.py
import uuid
from datetime import UTC, datetime

import pytest

from app.common.exceptions import AppException  # or specific 409 subclass
from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.schemas import DocCreate
from app.modules.llm_pipeline.services.doc_service import DocService

pytestmark = pytest.mark.asyncio


async def _vendor(session) -> Vendor:
    v = Vendor(
        id=uuid.uuid4(), name="acme", slug=f"a-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    session.add(v)
    await session.flush()
    return v


class TestUploadDoc:
    async def test_creates_doc_with_defaults(self, db_session):
        v = await _vendor(db_session)
        svc = DocService(DocRepository(db_session))
        doc = await svc.upload_doc(
            DocCreate(vendor_id=v.id, content="# x"),
            requested_by_user_id=uuid.uuid4(),
        )
        assert doc.fetched_by == "manual"
        assert doc.content_format == "markdown"
        assert doc.fetched_at is not None

    async def test_duplicate_vendor_url_conflicts(self, db_session):
        v = await _vendor(db_session)
        svc = DocService(DocRepository(db_session))
        await svc.upload_doc(
            DocCreate(vendor_id=v.id, url="https://x/a", content="1"),
            requested_by_user_id=uuid.uuid4(),
        )
        with pytest.raises(AppException) as exc:
            await svc.upload_doc(
                DocCreate(vendor_id=v.id, url="https://x/a", content="2"),
                requested_by_user_id=uuid.uuid4(),
            )
        assert exc.value.status_code == 409
```

- [ ] **Step 3: Implement service**

`app/modules/llm_pipeline/services/doc_service.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.common.exceptions import AppException
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.schemas import DocCreate


class DocService:
    def __init__(self, repo: DocRepository) -> None:
        self._repo = repo

    async def upload_doc(
        self, body: DocCreate, *, requested_by_user_id: uuid.UUID
    ) -> Doc:
        doc = Doc(
            id=uuid.uuid4(),
            vendor_id=body.vendor_id,
            url=body.url,
            title=body.title,
            content=body.content,
            content_format=body.content_format,
            fetched_at=datetime.now(UTC),
            fetched_by="manual",
        )
        try:
            return await self._repo.create(doc)
        except IntegrityError as e:
            raise AppException(
                status_code=409,
                code="doc_already_exists",
                message=f"Doc with this vendor+url already exists",
            ) from e
```

(Inspect `app/common/exceptions.py` for the actual `AppException` constructor signature; adjust args if it's `(message, status_code=...)` etc.)

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_doc_service.py -v
git add app/modules/llm_pipeline/services/doc_service.py tests/unit/modules/llm_pipeline/test_doc_service.py
git commit -m "feat(llm-pipeline): add DocService.upload_doc with conflict handling"
```

---

### Task 5.3: `doc_router` — POST `/llm-pipeline/docs`

**Files:**
- Create: `app/modules/llm_pipeline/routers/doc_router.py`
- Test: `tests/unit/modules/llm_pipeline/test_doc_router.py`
- Modify: `app/api/v1/__init__.py` — mount router

- [ ] **Step 1: Write router test**

```python
# tests/unit/modules/llm_pipeline/test_doc_router.py
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestPostDoc:
    async def test_requires_auth(self, async_client: AsyncClient):
        r = await async_client.post(
            "/api/v1/llm-pipeline/docs",
            json={"vendor_id": str(uuid.uuid4()), "content": "# x"},
        )
        assert r.status_code in (401, 403)

    async def test_creates_doc(self, async_client_authed: AsyncClient, seed_vendor):
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/docs",
            json={
                "vendor_id": str(seed_vendor.id),
                "url": "https://example.com/a",
                "title": "A",
                "content_format": "markdown",
                "content": "# Hello",
            },
        )
        assert r.status_code == 201
        body = r.json()["data"]
        assert body["vendor_id"] == str(seed_vendor.id)
        assert body["url"] == "https://example.com/a"

    async def test_409_on_dup(self, async_client_authed, seed_vendor):
        body = {
            "vendor_id": str(seed_vendor.id),
            "url": "https://example.com/dup",
            "content": "x",
        }
        r1 = await async_client_authed.post("/api/v1/llm-pipeline/docs", json=body)
        assert r1.status_code == 201
        r2 = await async_client_authed.post("/api/v1/llm-pipeline/docs", json=body)
        assert r2.status_code == 409
```

(Confirm the names of fixtures `async_client`, `async_client_authed`, `seed_vendor` against `tests/conftest.py`. If `seed_vendor` doesn't exist as a fixture, inline the vendor creation via dependency.)

- [ ] **Step 2: Run, verify FAIL**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_doc_router.py -v
```

- [ ] **Step 3: Implement router**

`app/modules/llm_pipeline/routers/doc_router.py`:

```python
"""POST /api/v1/llm-pipeline/docs — admin upload of vendor doc markdown."""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.schemas import DocCreate, DocRead
from app.modules.llm_pipeline.services.doc_service import DocService

router = APIRouter()


def _doc_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocService:
    return DocService(DocRepository(session))


@router.post(
    "/docs",
    response_model=DataResponse[DocRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_doc(
    body: DocCreate,
    service: Annotated[DocService, Depends(_doc_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[DocRead]:
    doc = await service.upload_doc(body, requested_by_user_id=user.id)
    return DataResponse(data=DocRead.model_validate(doc))
```

(Verify dependency names: `get_db_session`, `current_user`, `DataResponse` — should match how library routers import them.)

- [ ] **Step 4: Mount router in `app/api/v1/__init__.py`**

Add import + include:

```python
from app.modules.llm_pipeline.routers.doc_router import router as llm_pipeline_doc_router
...
router.include_router(llm_pipeline_doc_router, prefix="/llm-pipeline", tags=["llm-pipeline:docs"])
```

- [ ] **Step 5: Run tests + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_doc_router.py -v
git add app/modules/llm_pipeline/routers/doc_router.py app/api/v1/__init__.py tests/unit/modules/llm_pipeline/test_doc_router.py
git commit -m "feat(llm-pipeline): POST /llm-pipeline/docs admin upload"
```

---

## Milestone 6 — Exceptions + VRL validator

### Task 6.1: `exceptions.py`

**Files:**
- Create: `app/modules/llm_pipeline/exceptions.py`
- Test: `tests/unit/modules/llm_pipeline/test_exceptions.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/modules/llm_pipeline/test_exceptions.py
from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    DbWriteError,
    LlmDraftError,
    SchemaMismatchError,
    VrlCompileError,
    VrlFieldsDisjointError,
)


def test_all_subclass_base():
    for cls in (
        SchemaMismatchError, VrlFieldsDisjointError,
        VrlCompileError, AnthropicCallError, DbWriteError,
    ):
        assert issubclass(cls, LlmDraftError)


def test_each_has_unique_error_code():
    codes = {
        SchemaMismatchError("x").error_code,
        VrlFieldsDisjointError("x").error_code,
        VrlCompileError("x").error_code,
        AnthropicCallError("x").error_code,
        DbWriteError("x").error_code,
    }
    assert codes == {
        "schema_mismatch", "vrl_fields_disjoint",
        "vrl_compile_failed", "anthropic_failed", "db_write_failed",
    }
```

- [ ] **Step 2: Implement**

`app/modules/llm_pipeline/exceptions.py`:

```python
"""Exception classes used by llm_pipeline. Each carries a stable error_code
that is forwarded to the audit job row and the HTTP error response body."""


class LlmDraftError(Exception):
    """Base for errors raised during draft generation. Subclasses set error_code."""

    error_code: str = "llm_draft_error"


class SchemaMismatchError(LlmDraftError):
    error_code = "schema_mismatch"


class VrlFieldsDisjointError(LlmDraftError):
    error_code = "vrl_fields_disjoint"


class VrlCompileError(LlmDraftError):
    error_code = "vrl_compile_failed"


class AnthropicCallError(LlmDraftError):
    error_code = "anthropic_failed"


class DbWriteError(LlmDraftError):
    error_code = "db_write_failed"
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_exceptions.py -v
git add app/modules/llm_pipeline/exceptions.py tests/unit/modules/llm_pipeline/test_exceptions.py
git commit -m "feat(llm-pipeline): add domain exceptions with stable error_codes"
```

---

### Task 6.2: `vrl_validator`

**Files:**
- Create: `app/modules/llm_pipeline/services/vrl_validator.py`
- Test: `tests/unit/modules/llm_pipeline/test_vrl_validator.py`

- [ ] **Step 1: Examine existing analyzer vrl_runtime API**

```bash
grep -n "def compile_program\|def compile" app/modules/analyzer/services/vrl_runtime.py
```

Take note of the function signature, what exception types it raises, and what arguments it accepts (engine version etc.).

- [ ] **Step 2: Write tests**

```python
# tests/unit/modules/llm_pipeline/test_vrl_validator.py
import pytest

from app.modules.llm_pipeline.exceptions import VrlCompileError
from app.modules.llm_pipeline.services.vrl_validator import validate_vrl


class TestValidateVrl:
    def test_valid_vrl_032_returns_none(self):
        # any compilable program; this one assigns a constant
        validate_vrl(". = parse_json!(.message)", engine_version="0.32")

    def test_invalid_vrl_raises(self):
        with pytest.raises(VrlCompileError) as exc:
            validate_vrl("???not vrl???", engine_version="0.32")
        assert "compile" in str(exc.value).lower() or len(str(exc.value)) > 0

    def test_engine_025(self):
        validate_vrl(". = parse_json!(.message)", engine_version="0.25")
```

- [ ] **Step 3: Implement validator**

`app/modules/llm_pipeline/services/vrl_validator.py`:

```python
"""Thin wrapper over analyzer.vrl_runtime to validate VRL compiles."""
from app.modules.analyzer.services import vrl_runtime
from app.modules.llm_pipeline.exceptions import VrlCompileError


def validate_vrl(vrl_code: str, *, engine_version: str) -> None:
    """Compile-validate VRL. Raises VrlCompileError on any compile failure."""
    try:
        vrl_runtime.compile_program(vrl_code, engine_version)
    except Exception as e:  # noqa: BLE001 — wrap whatever PyO3 throws
        raise VrlCompileError(str(e)) from e
```

(Adjust the call to match the actual vrl_runtime function name/signature you confirmed in step 1.)

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_vrl_validator.py -v
git add app/modules/llm_pipeline/services/vrl_validator.py tests/unit/modules/llm_pipeline/test_vrl_validator.py
git commit -m "feat(llm-pipeline): add VRL compile validator wrapping analyzer.vrl_runtime"
```

---

## Milestone 7 — Job repository (3-tx pattern)

### Task 7.1: `llm_generation_job_repository`

**Files:**
- Create: `app/modules/llm_pipeline/repositories/llm_generation_job_repository.py`
- Test: `tests/unit/modules/llm_pipeline/test_llm_generation_job_repository.py`

The repository is constructed with a `sessionmaker` (not a session). Each public method opens its own session+transaction so the 3-transaction pattern from §3.4 of the spec works.

- [ ] **Step 1: Write tests**

```python
# tests/unit/modules/llm_pipeline/test_llm_generation_job_repository.py
import uuid
from datetime import UTC, datetime

import pytest

from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.llm_pipeline.models import Doc, LlmGenerationJob
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)

pytestmark = pytest.mark.asyncio


async def _seed(session) -> tuple[Vendor, Product, Doc]:
    v = Vendor(id=uuid.uuid4(), name="x", slug=f"v-{uuid.uuid4().hex[:6]}", status="active")
    session.add(v)
    await session.flush()
    p = Product(id=uuid.uuid4(), vendor_id=v.id, name="p", slug=f"p-{uuid.uuid4().hex[:6]}", status="active")
    session.add(p)
    await session.flush()
    d = Doc(id=uuid.uuid4(), vendor_id=v.id, content="x", content_format="markdown",
            fetched_at=datetime.now(UTC), fetched_by="manual")
    session.add(d)
    await session.flush()
    await session.commit()
    return v, p, d


class TestJobRepository:
    async def test_create_pending_returns_id_and_persists(self, db_session, db_session_factory):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id, product_id=p.id,
            requested_by=uuid.uuid4(), model="claude-opus-4-7",
        )
        # fetch in a fresh session
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job is not None
            assert job.status == "pending"
            assert job.model == "claude-opus-4-7"

    async def test_finish_succeeded_sets_lineage(
        self, db_session, db_session_factory,
    ):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id, product_id=p.id, requested_by=uuid.uuid4(),
            model="m",
        )
        await repo.finish_succeeded(
            job_id, log_type_id=None, parse_rule_id=None,
            input_tokens=100, output_tokens=50, cache_read_tokens=10,
        )
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job.status == "succeeded"
            assert job.input_tokens == 100
            assert job.finished_at is not None

    async def test_finish_failed_records_error(self, db_session, db_session_factory):
        _, p, d = await _seed(db_session)
        repo = LlmGenerationJobRepository(db_session_factory)
        job_id = await repo.create_pending(
            doc_id=d.id, product_id=p.id, requested_by=uuid.uuid4(),
            model="m",
        )
        await repo.finish_failed(
            job_id,
            error_code="schema_mismatch",
            error_message="missing log_type",
            raw_response="<truncated 30 chars>",
        )
        async with db_session_factory() as s:
            job = await s.get(LlmGenerationJob, job_id)
            assert job.status == "failed"
            assert job.error_code == "schema_mismatch"
            assert job.raw_response == "<truncated 30 chars>"
```

(Verify `db_session_factory` fixture exists in conftest. If only `db_session` exists, augment conftest to also expose the sessionmaker; OR have repo accept a session and document that the caller wraps it in a fresh transaction.)

**Alternate:** If conftest only exposes `db_session` (test-scoped session), the simpler design is:

```python
class LlmGenerationJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(...): ...   # caller commits
    async def finish_succeeded(...): ...
    async def finish_failed(...): ...
```

— and have the *service* manage the 3 transactions by reaching into `app.core.database` directly. Pick the option matching existing repository conventions.

- [ ] **Step 2: Implement**

`app/modules/llm_pipeline/repositories/llm_generation_job_repository.py`:

```python
"""Job repository implementing the 3-transaction pattern from spec §3.4.

Each public method commits independently so audit rows persist regardless
of caller transaction state."""
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.llm_pipeline.models import LlmGenerationJob


class LlmGenerationJobRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def create_pending(
        self,
        *,
        doc_id: uuid.UUID,
        product_id: uuid.UUID,
        requested_by: uuid.UUID | None,
        model: str,
    ) -> uuid.UUID:
        job = LlmGenerationJob(
            id=uuid.uuid4(),
            doc_id=doc_id,
            product_id=product_id,
            requested_by=requested_by,
            status="pending",
            model=model,
            started_at=datetime.now(UTC),
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(job)
        return job.id

    async def finish_succeeded(
        self,
        job_id: uuid.UUID,
        *,
        log_type_id: uuid.UUID | None,
        parse_rule_id: uuid.UUID | None,
        input_tokens: int | None,
        output_tokens: int | None,
        cache_read_tokens: int | None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(LlmGenerationJob, job_id)
                if job is None:
                    return
                job.status = "succeeded"
                job.log_type_id = log_type_id
                job.parse_rule_id = parse_rule_id
                job.input_tokens = input_tokens
                job.output_tokens = output_tokens
                job.cache_read_tokens = cache_read_tokens
                job.finished_at = datetime.now(UTC)

    async def finish_failed(
        self,
        job_id: uuid.UUID,
        *,
        error_code: str,
        error_message: str,
        raw_response: str | None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await session.get(LlmGenerationJob, job_id)
                if job is None:
                    return
                job.status = "failed"
                job.error_code = error_code
                job.error_message = error_message
                job.raw_response = raw_response
                job.finished_at = datetime.now(UTC)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_llm_generation_job_repository.py -v
git add app/modules/llm_pipeline/repositories/llm_generation_job_repository.py tests/unit/modules/llm_pipeline/test_llm_generation_job_repository.py
git commit -m "feat(llm-pipeline): add LlmGenerationJobRepository with 3-tx methods"
```

---

## Milestone 8 — Prompt builder

### Task 8.1: `DRAFT_TOOL_SCHEMA` constant

**Files:**
- Create initial body of: `app/modules/llm_pipeline/services/prompt_builder.py`
- Test: `tests/unit/modules/llm_pipeline/test_prompt_builder.py`

- [ ] **Step 1: Write test**

```python
# tests/unit/modules/llm_pipeline/test_prompt_builder.py
from app.modules.llm_pipeline.services.prompt_builder import DRAFT_TOOL_SCHEMA


class TestDraftToolSchema:
    def test_top_level(self):
        assert DRAFT_TOOL_SCHEMA["name"] == "submit_draft"
        assert "input_schema" in DRAFT_TOOL_SCHEMA

    def test_required_top_level_keys(self):
        req = set(DRAFT_TOOL_SCHEMA["input_schema"]["required"])
        assert req == {"log_type", "fields", "vrl_code", "engine_version", "notes"}

    def test_log_type_subschema(self):
        lt = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["log_type"]
        assert "name" in lt["properties"]
        assert "format" in lt["properties"]
        assert "json" in lt["properties"]["format"]["enum"]

    def test_field_type_enum(self):
        fields = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["fields"]
        item = fields["items"]
        assert "ip" in item["properties"]["field_type"]["enum"]
        assert fields["minItems"] == 1
        assert fields["maxItems"] == 50

    def test_engine_version_enum(self):
        ev = DRAFT_TOOL_SCHEMA["input_schema"]["properties"]["engine_version"]
        assert ev["enum"] == ["0.25", "0.32"]
```

- [ ] **Step 2: Write minimal `prompt_builder.py`**

```python
# app/modules/llm_pipeline/services/prompt_builder.py
"""Prompt construction for E2 draft generation."""

DRAFT_TOOL_SCHEMA: dict = {
    "name": "submit_draft",
    "description": (
        "Submit a single LogType draft (metadata + fields + VRL parse rule) "
        "extracted from the vendor doc. Call this exactly once per request."
    ),
    "input_schema": {
        "type": "object",
        "required": ["log_type", "fields", "vrl_code", "engine_version", "notes"],
        "properties": {
            "log_type": {
                "type": "object",
                "required": ["name", "format"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 200},
                    "format": {
                        "type": "string",
                        "enum": ["syslog", "json", "cef", "leef", "csv", "other"],
                    },
                    "transport": {
                        "type": "string",
                        "enum": ["syslog_udp", "syslog_tcp", "http", "file", "other"],
                    },
                    "description": {"type": "string", "maxLength": 1000},
                },
            },
            "fields": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "required": ["field_name", "field_type"],
                    "properties": {
                        "field_name": {"type": "string", "minLength": 1, "maxLength": 100},
                        "field_type": {
                            "type": "string",
                            "enum": ["string", "int", "float", "bool", "timestamp", "ip", "object", "array"],
                        },
                        "description": {"type": "string"},
                        "is_required": {"type": "boolean", "default": False},
                        "is_identifier": {"type": "boolean", "default": False},
                        "example_value": {"type": "string"},
                    },
                },
            },
            "vrl_code": {"type": "string", "minLength": 1},
            "engine_version": {"type": "string", "enum": ["0.25", "0.32"], "default": "0.32"},
            "notes": {
                "type": "string",
                "description": "Reviewer-facing notes — what was uncertain, alternative interpretations, fields not extracted",
                "maxLength": 2000,
            },
        },
    },
}
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_prompt_builder.py -v
git add app/modules/llm_pipeline/services/prompt_builder.py tests/unit/modules/llm_pipeline/test_prompt_builder.py
git commit -m "feat(llm-pipeline): add submit_draft tool schema"
```

---

### Task 8.2: Block 1 (persona + skill instructions + cheatsheet + example)

**Files:**
- Modify: `app/modules/llm_pipeline/services/prompt_builder.py`
- Modify: `tests/unit/modules/llm_pipeline/test_prompt_builder.py`

- [ ] **Step 1: Add tests**

```python
class TestBlock1:
    def test_block1_imports_cheatsheet(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "VRL function cheatsheet" in BLOCK1_TEXT

    def test_block1_persona(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "library builder" in BLOCK1_TEXT.lower()

    def test_block1_warns_against_invented_fields(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "do not invent" in BLOCK1_TEXT.lower() or "don't invent" in BLOCK1_TEXT.lower()

    def test_block1_includes_example(self):
        from app.modules.llm_pipeline.services.prompt_builder import BLOCK1_TEXT
        assert "PAN-OS" in BLOCK1_TEXT or "Example" in BLOCK1_TEXT
```

- [ ] **Step 2: Add `BLOCK1_TEXT` constant**

In `app/modules/llm_pipeline/services/prompt_builder.py`, append:

```python
from app.modules.copilot.services._vrl_cheatsheet import VRL_CHEATSHEET


BLOCK1_TEXT = f"""You are LogScope's library builder.

Your job: read a vendor doc and propose ONE LogType draft via the `submit_draft` tool.

# Output rules
- No prose response. Submit only via the `submit_draft` tool.
- Do NOT invent fields not described in the doc.
- snake_case field names matching the convention in <existing_log_types>.
- For each field whose meaning you inferred (rather than the doc stated literally),
  end its `description` with one of: 〔依據：明確〕〔依據：推測〕〔依據：未知〕
  (sourced from D-series Copilot conventions).

# Process (follow in order)
1. Identify the LogType in the doc. If the doc covers multiple subtypes, pick
   the one matching <hint>. Otherwise pick the first / most prominent.
2. List fields with: source position in doc / VRL extraction strategy / type.
3. Write VRL targeting `engine_version` (default 0.32; if doc indicates older
   syntax or hint specifies, use 0.25).
4. Cross-check: every field in `fields[]` must be assigned in `vrl_code`
   OR the VRL must use a splat-style assign (`. = parse_json!(...)`,
   `. = parse_syslog!(...)`, `. = parse_key_value!(...)`); every field assigned
   in `vrl_code` must appear in `fields[]`.

{VRL_CHEATSHEET}

# You must NOT
- Invent fields not visibly described in the doc.
- Invent VRL function names. Stick to the cheatsheet above.
- Hard-code secrets / tokens / production hostnames into the VRL.
- Split the same conceptual field into two `fields[]` entries.

# Uncertainty handling
If the doc is ambiguous about a field, write `notes` like
"無法確定 X：<原因>" — submit a smaller fields[] rather than guessing.

# Example — PAN-OS TRAFFIC log

INPUT (excerpt of <doc>):
> PAN-OS TRAFFIC log format (CSV after syslog header):
>   FUTURE_USE,Receive Time,Serial Number,Type,Threat/Content Type,FUTURE_USE,
>   Source IP,Destination IP,...

OUTPUT (tool call):
{{
  "log_type": {{
    "name": "PAN-OS TRAFFIC",
    "format": "syslog",
    "transport": "syslog_udp",
    "description": "Palo Alto traffic logs (CSV body inside syslog)"
  }},
  "fields": [
    {{"field_name": "serial",   "field_type": "string", "is_identifier": true,  "description": "PAN serial 〔依據：明確〕"}},
    {{"field_name": "log_type", "field_type": "string", "description": "PAN log subtype 〔依據：明確〕"}},
    {{"field_name": "src_ip",   "field_type": "ip", "is_required": true, "description": "source IP 〔依據：明確〕"}},
    {{"field_name": "dst_ip",   "field_type": "ip", "is_required": true, "description": "destination IP 〔依據：明確〕"}}
  ],
  "vrl_code": ". = parse_syslog!(.message)\\nparts = split(string!(.message), \\",\\")\\n.serial   = parts[2] ?? null\\n.log_type = parts[3] ?? null\\n.src_ip   = parts[6] ?? null\\n.dst_ip   = parts[7] ?? null",
  "engine_version": "0.32",
  "notes": "PAN CSV column count varies by subtype — used `?? null` fallback."
}}
"""
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_prompt_builder.py -v
git add app/modules/llm_pipeline/services/prompt_builder.py tests/unit/modules/llm_pipeline/test_prompt_builder.py
git commit -m "feat(llm-pipeline): add Block 1 persona/skill/example for draft prompt"
```

---

### Task 8.3: Block 2 — XML rendering with truncation

**Files:**
- Modify: `app/modules/llm_pipeline/services/prompt_builder.py`
- Modify: `tests/unit/modules/llm_pipeline/test_prompt_builder.py`

The Block 2 input is a typed `DraftPromptContext` dataclass holding vendor / product / existing log types / doc / hint. Truncation is to 20000 chars.

- [ ] **Step 1: Add tests**

```python
class TestRenderBlock2:
    def _ctx(self, **overrides):
        from app.modules.llm_pipeline.services.prompt_builder import (
            DraftPromptContext, ExistingLogTypeView, FieldView,
        )
        return DraftPromptContext(
            vendor_name="Acme", vendor_slug="acme",
            product_name="FW", product_slug="fw",
            product_version=None, product_deploy_type="cloud",
            existing_log_types=[
                ExistingLogTypeView(
                    name="PAN-OS TRAFFIC", format="syslog", transport="syslog_udp",
                    fields=[FieldView(name="src_ip", type="ip", required=True)],
                ),
            ],
            doc_title="A", doc_url="https://x", doc_content="# hi",
            hint=None,
            **overrides,
        )

    def test_renders_vendor_product(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx())
        assert '<vendor name="Acme" slug="acme" />' in x
        assert '<product name="FW" slug="fw"' in x

    def test_renders_existing_log_types(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx())
        assert '<existing_log_types count="1">' in x
        assert 'PAN-OS TRAFFIC' in x
        assert 'src_ip' in x

    def test_existing_log_types_count_zero(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(existing_log_types=[]))
        assert '<existing_log_types count="0">' in x

    def test_doc_truncation(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        long = "A" * 30000
        x = render_block2_xml(self._ctx(doc_content=long))
        assert 'truncated_to="20000"' in x
        assert "A" * 20000 in x
        assert "A" * 20001 not in x

    def test_hint_omitted_when_none(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(hint=None))
        assert "<hint>" not in x

    def test_hint_rendered_when_present(self):
        from app.modules.llm_pipeline.services.prompt_builder import render_block2_xml
        x = render_block2_xml(self._ctx(hint="focus on subtype X"))
        assert "<hint>" in x
        assert "focus on subtype X" in x
```

- [ ] **Step 2: Implement Block 2 dataclasses + renderer**

Append to `app/modules/llm_pipeline/services/prompt_builder.py`:

```python
from dataclasses import dataclass


# Reuse copilot's CDATA escape — same convention.
def _safe_cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")


DOC_TRUNCATE_CHARS = 20_000


@dataclass(frozen=True)
class FieldView:
    name: str
    type: str
    required: bool = False


@dataclass(frozen=True)
class ExistingLogTypeView:
    name: str
    format: str
    transport: str | None
    fields: list[FieldView]


@dataclass(frozen=True)
class DraftPromptContext:
    vendor_name: str
    vendor_slug: str
    product_name: str
    product_slug: str
    product_version: str | None
    product_deploy_type: str | None
    existing_log_types: list[ExistingLogTypeView]
    doc_title: str | None
    doc_url: str | None
    doc_content: str
    hint: str | None


def render_block2_xml(ctx: DraftPromptContext) -> str:
    from xml.sax.saxutils import quoteattr

    lines: list[str] = []
    lines.append(
        f'<vendor name={quoteattr(ctx.vendor_name)} '
        f'slug={quoteattr(ctx.vendor_slug)} />'
    )
    product_attrs = [
        f'name={quoteattr(ctx.product_name)}',
        f'slug={quoteattr(ctx.product_slug)}',
    ]
    if ctx.product_version:
        product_attrs.append(f'version={quoteattr(ctx.product_version)}')
    if ctx.product_deploy_type:
        product_attrs.append(f'deploy_type={quoteattr(ctx.product_deploy_type)}')
    lines.append(f'<product {" ".join(product_attrs)} />')

    lines.append("")
    lines.append(f'<existing_log_types count="{len(ctx.existing_log_types)}">')
    for elt in ctx.existing_log_types:
        attrs = [f'name={quoteattr(elt.name)}', f'format={quoteattr(elt.format)}']
        if elt.transport:
            attrs.append(f'transport={quoteattr(elt.transport)}')
        lines.append(f'  <log_type {" ".join(attrs)}>')
        lines.append("    <fields>")
        for f in elt.fields:
            lines.append(
                f'      <field name={quoteattr(f.name)} '
                f'type={quoteattr(f.type)} required="{str(f.required).lower()}" />'
            )
        lines.append("    </fields>")
        lines.append("  </log_type>")
    lines.append("</existing_log_types>")

    lines.append("")
    doc_attrs = []
    if ctx.doc_title:
        doc_attrs.append(f'title={quoteattr(ctx.doc_title)}')
    if ctx.doc_url:
        doc_attrs.append(f'url={quoteattr(ctx.doc_url)}')
    content = ctx.doc_content
    if len(content) > DOC_TRUNCATE_CHARS:
        content = content[:DOC_TRUNCATE_CHARS]
        doc_attrs.append(f'truncated_to="{DOC_TRUNCATE_CHARS}"')
    lines.append(f"<doc {' '.join(doc_attrs)}>" if doc_attrs else "<doc>")
    lines.append(f"  <![CDATA[{_safe_cdata(content)}]]>")
    lines.append("</doc>")

    if ctx.hint:
        lines.append("")
        lines.append(f"<hint><![CDATA[{_safe_cdata(ctx.hint)}]]></hint>")

    return "\n".join(lines)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_prompt_builder.py -v
git add app/modules/llm_pipeline/services/prompt_builder.py tests/unit/modules/llm_pipeline/test_prompt_builder.py
git commit -m "feat(llm-pipeline): add Block 2 XML renderer with doc truncation"
```

---

### Task 8.4: `build_system_blocks` — assemble Block 1 + Block 2

**Files:**
- Modify: `app/modules/llm_pipeline/services/prompt_builder.py`
- Modify: `tests/unit/modules/llm_pipeline/test_prompt_builder.py`

- [ ] **Step 1: Add tests**

```python
class TestBuildSystemBlocks:
    def test_two_blocks_block1_cached(self):
        from app.modules.llm_pipeline.services.prompt_builder import (
            build_system_blocks, DraftPromptContext,
        )
        ctx = DraftPromptContext(
            vendor_name="x", vendor_slug="x",
            product_name="p", product_slug="p",
            product_version=None, product_deploy_type=None,
            existing_log_types=[], doc_title=None, doc_url=None,
            doc_content="x", hint=None,
        )
        blocks = build_system_blocks(ctx)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "text"
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert blocks[1]["type"] == "text"
        assert "cache_control" not in blocks[1]
        assert "library builder" in blocks[0]["text"].lower()
        assert "<vendor" in blocks[1]["text"]
```

- [ ] **Step 2: Add function**

Append:

```python
def build_system_blocks(ctx: DraftPromptContext) -> list[dict]:
    """Return Anthropic `system` parameter as 2 TextBlockParam dicts.

    Block 1: cached persona+skill+cheatsheet+example.
    Block 2: per-request XML context.
    """
    return [
        {
            "type": "text",
            "text": BLOCK1_TEXT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": render_block2_xml(ctx),
        },
    ]
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_prompt_builder.py -v
git add app/modules/llm_pipeline/services/prompt_builder.py tests/unit/modules/llm_pipeline/test_prompt_builder.py
git commit -m "feat(llm-pipeline): add build_system_blocks combining Block 1 + Block 2"
```

---

## Milestone 9 — Tool-use parsing + self-consistency

### Task 9.1: `parse_tool_use`

**Files:**
- Create: `app/modules/llm_pipeline/services/tool_use_parser.py`
- Test: `tests/unit/modules/llm_pipeline/test_tool_use_parser.py`

- [ ] **Step 1: Test**

```python
# tests/unit/modules/llm_pipeline/test_tool_use_parser.py
from types import SimpleNamespace

import pytest

from app.modules.llm_pipeline.exceptions import SchemaMismatchError
from app.modules.llm_pipeline.services.tool_use_parser import (
    DraftPayload,
    parse_tool_use,
)


def _resp_with_tool_use(tool_input: dict) -> SimpleNamespace:
    """Build a fake Anthropic Message-like object with one tool_use block."""
    block = SimpleNamespace(
        type="tool_use", name="submit_draft", id="t1", input=tool_input,
    )
    return SimpleNamespace(content=[block], stop_reason="tool_use")


class TestParseToolUse:
    def _payload(self):
        return {
            "log_type": {
                "name": "PAN-OS TRAFFIC",
                "format": "syslog",
                "transport": "syslog_udp",
                "description": None,
            },
            "fields": [
                {"field_name": "src_ip", "field_type": "ip",
                 "is_required": True, "is_identifier": False,
                 "description": "src", "example_value": "10.0.0.1"},
            ],
            "vrl_code": ". = parse_syslog!(.message)\n.src_ip = parts[6] ?? null",
            "engine_version": "0.32",
            "notes": "ok",
        }

    def test_happy_path(self):
        resp = _resp_with_tool_use(self._payload())
        d = parse_tool_use(resp)
        assert isinstance(d, DraftPayload)
        assert d.log_type.name == "PAN-OS TRAFFIC"
        assert len(d.fields) == 1
        assert d.engine_version == "0.32"

    def test_missing_tool_use_block_raises(self):
        # response with only a text block, no tool use
        resp = SimpleNamespace(content=[
            SimpleNamespace(type="text", text="hello"),
        ], stop_reason="end_turn")
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_wrong_tool_name_raises(self):
        block = SimpleNamespace(
            type="tool_use", name="other_tool", id="t1", input={},
        )
        resp = SimpleNamespace(content=[block], stop_reason="tool_use")
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)

    def test_invalid_payload_shape_raises(self):
        bad = self._payload()
        del bad["fields"]
        resp = _resp_with_tool_use(bad)
        with pytest.raises(SchemaMismatchError):
            parse_tool_use(resp)
```

- [ ] **Step 2: Implement parser**

`app/modules/llm_pipeline/services/tool_use_parser.py`:

```python
"""Parse Anthropic tool_use response into typed DraftPayload."""
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.modules.llm_pipeline.exceptions import (
    SchemaMismatchError,
    VrlFieldsDisjointError,
)


# Pydantic models for input_schema validation (mirrors DRAFT_TOOL_SCHEMA)


class _LogTypeMeta(BaseModel):
    name: str
    format: Literal["syslog", "json", "cef", "leef", "csv", "other"]
    transport: Literal[
        "syslog_udp", "syslog_tcp", "http", "file", "other"
    ] | None = None
    description: str | None = None


class _Field(BaseModel):
    field_name: str
    field_type: Literal[
        "string", "int", "float", "bool", "timestamp", "ip", "object", "array"
    ]
    description: str | None = None
    is_required: bool = False
    is_identifier: bool = False
    example_value: str | None = None


class _ToolInput(BaseModel):
    log_type: _LogTypeMeta
    fields: list[_Field]
    vrl_code: str
    engine_version: Literal["0.25", "0.32"] = "0.32"
    notes: str = ""


@dataclass(frozen=True)
class DraftPayload:
    log_type: _LogTypeMeta
    fields: list[_Field]
    vrl_code: str
    engine_version: str
    notes: str


def parse_tool_use(response: Any) -> DraftPayload:
    """Extract the single submit_draft tool call from an Anthropic response.

    Raises SchemaMismatchError if structure is wrong; the caller should
    record the error and stop processing.
    """
    blocks = getattr(response, "content", None) or []
    tool_blocks = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
    if len(tool_blocks) != 1:
        raise SchemaMismatchError(
            f"expected 1 tool_use block, got {len(tool_blocks)}"
        )
    block = tool_blocks[0]
    if getattr(block, "name", None) != "submit_draft":
        raise SchemaMismatchError(
            f"expected tool name 'submit_draft', got '{getattr(block, 'name', None)}'"
        )
    raw_input = getattr(block, "input", None) or {}
    try:
        validated = _ToolInput.model_validate(raw_input)
    except ValidationError as e:
        raise SchemaMismatchError(str(e)) from e
    return DraftPayload(
        log_type=validated.log_type,
        fields=validated.fields,
        vrl_code=validated.vrl_code,
        engine_version=validated.engine_version,
        notes=validated.notes,
    )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_tool_use_parser.py -v
git add app/modules/llm_pipeline/services/tool_use_parser.py tests/unit/modules/llm_pipeline/test_tool_use_parser.py
git commit -m "feat(llm-pipeline): parse Anthropic tool_use into typed DraftPayload"
```

---

### Task 9.2: `check_self_consistency` (with splat-assign exception)

**Files:**
- Modify: `app/modules/llm_pipeline/services/tool_use_parser.py`
- Modify: `tests/unit/modules/llm_pipeline/test_tool_use_parser.py`

- [ ] **Step 1: Tests**

```python
class TestCheckSelfConsistency:
    def _draft(self, vrl: str, field_names: list[str]):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            DraftPayload, _Field, _LogTypeMeta,
        )
        return DraftPayload(
            log_type=_LogTypeMeta(name="x", format="json"),
            fields=[
                _Field(field_name=n, field_type="string") for n in field_names
            ],
            vrl_code=vrl,
            engine_version="0.32",
            notes="",
        )

    def test_field_name_in_vrl_passes(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        d = self._draft(".src_ip = parts[6] ?? null", ["src_ip"])
        check_self_consistency(d)  # no raise

    def test_no_field_in_vrl_raises(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        from app.modules.llm_pipeline.exceptions import VrlFieldsDisjointError
        d = self._draft("x = 1", ["src_ip", "dst_ip"])
        with pytest.raises(VrlFieldsDisjointError):
            check_self_consistency(d)

    def test_splat_parse_json_passes_even_without_field_names(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        d = self._draft(". = parse_json!(.message)", ["src_ip", "dst_ip"])
        check_self_consistency(d)  # no raise — splat handles it

    def test_splat_parse_syslog_passes(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        d = self._draft(". = parse_syslog!(.message)", ["timestamp"])
        check_self_consistency(d)

    def test_splat_parse_key_value_passes(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        d = self._draft(". = parse_key_value!(.message)", ["timestamp"])
        check_self_consistency(d)

    def test_inline_marker_raises_schema_mismatch(self):
        from app.modules.llm_pipeline.services.tool_use_parser import (
            check_self_consistency,
        )
        from app.modules.llm_pipeline.exceptions import SchemaMismatchError
        d = self._draft(".src_ip = <|cursor|> null", ["src_ip"])
        with pytest.raises(SchemaMismatchError):
            check_self_consistency(d)
```

- [ ] **Step 2: Implement function**

Append to `tool_use_parser.py`:

```python
_SPLAT_PATTERNS = (
    ". = parse_json!",
    ". = parse_syslog!",
    ". = parse_key_value!",
    ". = parse_kv!",
)
_INLINE_SENTINELS = ("<|cursor|>", "<|sel_start|>", "<|sel_end|>")


def check_self_consistency(draft: DraftPayload) -> None:
    """Run service-layer checks before VRL compile.

    Raises:
        SchemaMismatchError if vrl_code contains inline sentinels.
        VrlFieldsDisjointError if no field_name appears in vrl_code AND
            vrl_code does not use splat-style assignment.
    """
    vrl = draft.vrl_code
    for sentinel in _INLINE_SENTINELS:
        if sentinel in vrl:
            raise SchemaMismatchError(
                f"vrl_code contains inline sentinel: {sentinel}"
            )
    has_splat = any(p in vrl for p in _SPLAT_PATTERNS)
    if has_splat:
        return
    field_names = {f.field_name for f in draft.fields}
    if not any(name in vrl for name in field_names):
        raise VrlFieldsDisjointError(
            "no field_name appears in vrl_code and no splat-assign is used"
        )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_tool_use_parser.py -v
git add app/modules/llm_pipeline/services/tool_use_parser.py tests/unit/modules/llm_pipeline/test_tool_use_parser.py
git commit -m "feat(llm-pipeline): add check_self_consistency with splat-assign handling"
```

---

## Milestone 10 — Draft service orchestration

### Task 10.1: Helpers (truncate, GenerationResult)

**Files:**
- Create: `app/modules/llm_pipeline/services/llm_draft_service.py` (initial helpers only)
- Test: `tests/unit/modules/llm_pipeline/test_llm_draft_service.py`

- [ ] **Step 1: Tests for truncate helper**

```python
# tests/unit/modules/llm_pipeline/test_llm_draft_service.py
from app.modules.llm_pipeline.services.llm_draft_service import (
    GenerationResult,
    _truncate_response,
)


class TestTruncateResponse:
    def test_short_kept(self):
        assert _truncate_response("abc", 4) == "abc"

    def test_long_truncated(self):
        assert _truncate_response("a" * 100, 10) == "a" * 10

    def test_none_returns_none(self):
        assert _truncate_response(None, 10) is None
```

- [ ] **Step 2: Add helpers**

`app/modules/llm_pipeline/services/llm_draft_service.py`:

```python
"""Orchestrates LLM draft generation per spec §3.4.

Responsible for:
- creating a pending job (TX-1)
- calling Anthropic
- parsing tool_use + self-consistency check + VRL compile
- writing log_type / fields / parse_rule + finishing job as succeeded (TX-2)
- on any failure, finishing job as failed in independent transaction (TX-3)
"""
import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.llm_pipeline.exceptions import LlmDraftError


_RAW_RESPONSE_MAX = 4096


@dataclass(frozen=True)
class GenerationResult:
    job_id: uuid.UUID
    log_type_id: uuid.UUID
    parse_rule_id: uuid.UUID


def _truncate_response(text: str | None, limit: int = _RAW_RESPONSE_MAX) -> str | None:
    if text is None:
        return None
    return text[:limit]


def _serialize_response(response: Any) -> str:
    """Best-effort serialize an Anthropic response for audit storage."""
    try:
        # Anthropic SDK objects often expose .model_dump() / .to_dict()
        if hasattr(response, "model_dump"):
            return json.dumps(response.model_dump(), default=str)
        if hasattr(response, "to_dict"):
            return json.dumps(response.to_dict(), default=str)
    except Exception:  # noqa: BLE001
        pass
    return str(response)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_llm_draft_service.py -v -k Truncate
git add app/modules/llm_pipeline/services/llm_draft_service.py tests/unit/modules/llm_pipeline/test_llm_draft_service.py
git commit -m "feat(llm-pipeline): add LlmDraftService helpers (truncate, GenerationResult)"
```

---

### Task 10.2: `generate_draft` happy path

**Files:**
- Modify: `app/modules/llm_pipeline/services/llm_draft_service.py`
- Modify: `tests/unit/modules/llm_pipeline/test_llm_draft_service.py`

- [ ] **Step 1: Write happy-path test**

```python
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.llm_pipeline.models import Doc
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.services.llm_draft_service import LlmDraftService

pytestmark = pytest.mark.asyncio


def _fake_anthropic_response(tool_input: dict, *, usage_input=100, usage_output=50, cache_read=10):
    block = SimpleNamespace(
        type="tool_use", name="submit_draft", id="t1", input=tool_input,
    )
    usage = SimpleNamespace(
        input_tokens=usage_input, output_tokens=usage_output,
        cache_read_input_tokens=cache_read,
    )
    return SimpleNamespace(
        content=[block], stop_reason="tool_use",
        usage=usage,
        model_dump=lambda: {"id": "msg1"},
    )


class _FakeAnthropic:
    def __init__(self, response):
        self._response = response
        self.messages = self
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


async def _seed_minimal(session) -> tuple[Vendor, Product, Doc]:
    v = Vendor(id=uuid.uuid4(), name="Acme",
               slug=f"acme-{uuid.uuid4().hex[:6]}", status="active")
    session.add(v)
    await session.flush()
    p = Product(id=uuid.uuid4(), vendor_id=v.id, name="FW",
                slug=f"fw-{uuid.uuid4().hex[:6]}", status="active")
    session.add(p)
    await session.flush()
    d = Doc(id=uuid.uuid4(), vendor_id=v.id, content="# example",
            content_format="markdown", fetched_at=datetime.now(UTC),
            fetched_by="manual")
    session.add(d)
    await session.flush()
    await session.commit()
    return v, p, d


_GOOD_TOOL_INPUT = {
    "log_type": {
        "name": "PAN-OS TRAFFIC", "format": "syslog",
        "transport": "syslog_udp", "description": None,
    },
    "fields": [
        {"field_name": "src_ip", "field_type": "ip", "is_required": True,
         "is_identifier": False, "description": None, "example_value": None},
    ],
    "vrl_code": ". = parse_syslog!(.message)\n.src_ip = parts[6] ?? null",
    "engine_version": "0.32",
    "notes": "ok",
}


class TestGenerateDraftHappy:
    async def test_writes_three_tables_and_finishes_job(
        self, db_session, db_session_factory,
    ):
        v, p, d = await _seed_minimal(db_session)
        anthropic = _FakeAnthropic(_fake_anthropic_response(_GOOD_TOOL_INPUT))
        svc = LlmDraftService(
            session_factory=db_session_factory,
            anthropic_client=anthropic,
            model="claude-opus-4-7",
            doc_repo_factory=lambda s: DocRepository(s),
            vendor_repo_factory=lambda s: VendorRepository(s),
            product_repo_factory=lambda s: ProductRepository(s),
            log_type_repo_factory=lambda s: LogTypeRepository(s),
            parse_rule_repo_factory=lambda s: ParseRuleRepository(s),
            field_schema_repo_factory=lambda s: FieldSchemaRepository(s),
            job_repo=LlmGenerationJobRepository(db_session_factory),
            vrl_validator=lambda code, engine_version: None,  # skip real compile in unit
        )
        result = await svc.generate_draft(
            doc_id=d.id, product_id=p.id,
            requested_by=uuid.uuid4(), hint=None,
        )
        # row checks in fresh session
        async with db_session_factory() as s:
            lt = await s.get(LogType, result.log_type_id)
            pr = await s.get(ParseRule, result.parse_rule_id)
            assert lt.status == "llm_draft"
            assert lt.source == "llm_generated"
            assert lt.source_job_id == result.job_id
            assert pr.status == "llm_draft"
            assert pr.source == "llm_generated"
            assert pr.source_job_id == result.job_id
            # field schema row exists
            from app.modules.library.models.field_schema import FieldSchema
            from sqlalchemy import select
            res = await s.execute(
                select(FieldSchema).where(FieldSchema.log_type_id == lt.id)
            )
            assert len(res.scalars().all()) == 1
```

- [ ] **Step 2: Implement `LlmDraftService.generate_draft` happy path**

Append to `llm_draft_service.py`:

```python
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.common.exceptions import AppException
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    DbWriteError,
    LlmDraftError,
)
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.services.prompt_builder import (
    DRAFT_TOOL_SCHEMA,
    DraftPromptContext,
    ExistingLogTypeView,
    FieldView,
    build_system_blocks,
)
from app.modules.llm_pipeline.services.tool_use_parser import (
    DraftPayload,
    check_self_consistency,
    parse_tool_use,
)


class LlmDraftService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        anthropic_client,
        model: str,
        doc_repo_factory,
        vendor_repo_factory,
        product_repo_factory,
        log_type_repo_factory,
        parse_rule_repo_factory,
        field_schema_repo_factory,
        job_repo: LlmGenerationJobRepository,
        vrl_validator,  # callable(vrl_code, engine_version) -> None or raise VrlCompileError
    ) -> None:
        self._session_factory = session_factory
        self._anthropic = anthropic_client
        self._model = model
        self._doc_repo_factory = doc_repo_factory
        self._vendor_repo_factory = vendor_repo_factory
        self._product_repo_factory = product_repo_factory
        self._log_type_repo_factory = log_type_repo_factory
        self._parse_rule_repo_factory = parse_rule_repo_factory
        self._field_schema_repo_factory = field_schema_repo_factory
        self._job_repo = job_repo
        self._vrl_validator = vrl_validator

    async def generate_draft(
        self,
        *,
        doc_id: uuid.UUID,
        product_id: uuid.UUID,
        requested_by: uuid.UUID,
        hint: str | None,
    ) -> GenerationResult:
        # Pre-flight reads (no transaction needed; all reads)
        async with self._session_factory() as session:
            doc = await self._doc_repo_factory(session).get_by_id(doc_id)
            if doc is None:
                raise AppException(status_code=404, code="doc_not_found",
                                   message="doc not found")
            product = await self._product_repo_factory(session).get_by_id(product_id)
            if product is None:
                raise AppException(status_code=404, code="product_not_found",
                                   message="product not found")
            vendor = await self._vendor_repo_factory(session).get_by_id(product.vendor_id)
            existing = await self._log_type_repo_factory(session).list_by_product(product_id)
            existing_views: list[ExistingLogTypeView] = []
            for elt in existing:
                fields = await self._field_schema_repo_factory(session).list_by_log_type(elt.id)
                existing_views.append(ExistingLogTypeView(
                    name=elt.name, format=elt.format, transport=elt.transport,
                    fields=[FieldView(name=f.field_name, type=f.field_type, required=f.is_required) for f in fields],
                ))

        # TX-1: pending job
        job_id = await self._job_repo.create_pending(
            doc_id=doc_id, product_id=product_id,
            requested_by=requested_by, model=self._model,
        )

        response = None
        try:
            ctx = DraftPromptContext(
                vendor_name=vendor.name, vendor_slug=vendor.slug,
                product_name=product.name, product_slug=product.slug,
                product_version=product.version, product_deploy_type=product.deploy_type,
                existing_log_types=existing_views,
                doc_title=doc.title, doc_url=doc.url, doc_content=doc.content,
                hint=hint,
            )
            system_blocks = build_system_blocks(ctx)
            try:
                response = await self._anthropic.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=system_blocks,
                    messages=[{"role": "user", "content": "Generate draft."}],
                    tools=[DRAFT_TOOL_SCHEMA],
                    tool_choice={"type": "tool", "name": "submit_draft"},
                )
            except Exception as e:  # noqa: BLE001
                raise AnthropicCallError(str(e)) from e

            draft = parse_tool_use(response)            # SchemaMismatchError
            check_self_consistency(draft)               # VrlFieldsDisjointError / SchemaMismatchError
            self._vrl_validator(draft.vrl_code, engine_version=draft.engine_version)  # VrlCompileError

            # TX-2: library writes + job.finish_succeeded
            log_type_id, parse_rule_id = await self._write_drafts(
                product_id=product_id, draft=draft, job_id=job_id,
            )
            usage = getattr(response, "usage", None)
            await self._job_repo.finish_succeeded(
                job_id,
                log_type_id=log_type_id,
                parse_rule_id=parse_rule_id,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
            )
            return GenerationResult(
                job_id=job_id, log_type_id=log_type_id, parse_rule_id=parse_rule_id,
            )

        except LlmDraftError as e:
            await self._job_repo.finish_failed(
                job_id,
                error_code=e.error_code,
                error_message=str(e),
                raw_response=_truncate_response(_serialize_response(response)) if response is not None else None,
            )
            raise

    async def _write_drafts(
        self,
        *,
        product_id: uuid.UUID,
        draft: DraftPayload,
        job_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    lt = LogType(
                        id=uuid.uuid4(),
                        product_id=product_id,
                        name=draft.log_type.name,
                        slug=_slugify(draft.log_type.name),
                        format=draft.log_type.format,
                        transport=draft.log_type.transport,
                        status="llm_draft",
                        source="llm_generated",
                        source_job_id=job_id,
                        description=draft.log_type.description,
                    )
                    session.add(lt)
                    await session.flush()

                    fs_repo = self._field_schema_repo_factory(session)
                    field_rows = [
                        FieldSchema(
                            id=uuid.uuid4(), log_type_id=lt.id,
                            field_name=f.field_name, field_type=f.field_type,
                            description=f.description,
                            is_required=f.is_required, is_identifier=f.is_identifier,
                            example_value=f.example_value, sort_order=i,
                        )
                        for i, f in enumerate(draft.fields)
                    ]
                    await fs_repo.replace_for_log_type(lt.id, field_rows)

                    pr = ParseRule(
                        id=uuid.uuid4(),
                        log_type_id=lt.id,
                        version=1,
                        vrl_code=draft.vrl_code,
                        engine_version=draft.engine_version,
                        status="llm_draft",
                        source="llm_generated",
                        source_job_id=job_id,
                        notes=draft.notes,
                    )
                    session.add(pr)
                    await session.flush()
                    return lt.id, pr.id
        except Exception as e:  # noqa: BLE001
            raise DbWriteError(f"library write failed: {type(e).__name__}: {e}") from e


def _slugify(name: str) -> str:
    """Project-internal slug. Mirror app/common/utils/slug.py if it exists."""
    from app.common.utils.slug import slugify  # use existing helper
    return slugify(name)
```

(Inspect the actual `field_schema_repository.replace_for_log_type` signature in step 6.2; the call must match. Also verify `app/common/utils/slug.py:slugify` exists.)

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_llm_draft_service.py -v -k Happy
git add app/modules/llm_pipeline/services/llm_draft_service.py tests/unit/modules/llm_pipeline/test_llm_draft_service.py
git commit -m "feat(llm-pipeline): LlmDraftService.generate_draft happy path"
```

---

### Task 10.3: Failure paths

**Files:**
- Modify: `tests/unit/modules/llm_pipeline/test_llm_draft_service.py`

- [ ] **Step 1: Add tests for each failure path**

```python
class TestGenerateDraftFailures:
    async def test_schema_mismatch_records_failed_job(
        self, db_session, db_session_factory,
    ):
        # response with NO tool_use blocks
        v, p, d = await _seed_minimal(db_session)
        bad_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello")],
            stop_reason="end_turn",
            model_dump=lambda: {"id": "x"},
        )
        anthropic = _FakeAnthropic(bad_resp)
        svc = _make_svc(anthropic, db_session_factory, vrl_validator=lambda c, engine_version: None)
        from app.modules.llm_pipeline.exceptions import SchemaMismatchError
        with pytest.raises(SchemaMismatchError):
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=uuid.uuid4(), hint=None,
            )
        # assert job is failed with right error_code
        async with db_session_factory() as s:
            from app.modules.llm_pipeline.models import LlmGenerationJob
            from sqlalchemy import select
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            jobs = res.scalars().all()
            assert len(jobs) == 1
            assert jobs[0].status == "failed"
            assert jobs[0].error_code == "schema_mismatch"

    async def test_vrl_compile_failed_records_failed_job(
        self, db_session, db_session_factory,
    ):
        v, p, d = await _seed_minimal(db_session)
        anthropic = _FakeAnthropic(_fake_anthropic_response(_GOOD_TOOL_INPUT))
        from app.modules.llm_pipeline.exceptions import VrlCompileError
        def bad_validator(code, *, engine_version):
            raise VrlCompileError("compile bomb")
        svc = _make_svc(anthropic, db_session_factory, vrl_validator=bad_validator)
        with pytest.raises(VrlCompileError):
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=uuid.uuid4(), hint=None,
            )
        async with db_session_factory() as s:
            from app.modules.llm_pipeline.models import LlmGenerationJob
            from sqlalchemy import select
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            assert res.scalars().first().error_code == "vrl_compile_failed"
        # ensure NO library row leaked
        async with db_session_factory() as s:
            from app.modules.library.models.log_type import LogType
            from sqlalchemy import select
            r = await s.execute(select(LogType).where(LogType.product_id == p.id))
            assert r.scalars().all() == []

    async def test_anthropic_failure_records_failed_job(
        self, db_session, db_session_factory,
    ):
        v, p, d = await _seed_minimal(db_session)
        class BoomAnthropic:
            messages = None
            async def _boom(self, **_): raise RuntimeError("api 500")
        boom = BoomAnthropic()
        boom.messages = boom
        boom.create = boom._boom
        svc = _make_svc(boom, db_session_factory, vrl_validator=lambda c, engine_version: None)
        from app.modules.llm_pipeline.exceptions import AnthropicCallError
        with pytest.raises(AnthropicCallError):
            await svc.generate_draft(
                doc_id=d.id, product_id=p.id,
                requested_by=uuid.uuid4(), hint=None,
            )
        async with db_session_factory() as s:
            from app.modules.llm_pipeline.models import LlmGenerationJob
            from sqlalchemy import select
            res = await s.execute(
                select(LlmGenerationJob).where(LlmGenerationJob.product_id == p.id)
            )
            assert res.scalars().first().error_code == "anthropic_failed"


def _make_svc(anthropic, factory, vrl_validator):
    from app.modules.library.repositories.field_schema_repository import FieldSchemaRepository
    from app.modules.library.repositories.log_type_repository import LogTypeRepository
    from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
    from app.modules.library.repositories.product_repository import ProductRepository
    from app.modules.library.repositories.vendor_repository import VendorRepository
    from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
    from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
        LlmGenerationJobRepository,
    )
    return LlmDraftService(
        session_factory=factory,
        anthropic_client=anthropic,
        model="m",
        doc_repo_factory=lambda s: DocRepository(s),
        vendor_repo_factory=lambda s: VendorRepository(s),
        product_repo_factory=lambda s: ProductRepository(s),
        log_type_repo_factory=lambda s: LogTypeRepository(s),
        parse_rule_repo_factory=lambda s: ParseRuleRepository(s),
        field_schema_repo_factory=lambda s: FieldSchemaRepository(s),
        job_repo=LlmGenerationJobRepository(factory),
        vrl_validator=vrl_validator,
    )
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_llm_draft_service.py -v
git add tests/unit/modules/llm_pipeline/test_llm_draft_service.py
git commit -m "test(llm-pipeline): cover schema_mismatch / vrl_compile_failed / anthropic_failed paths"
```

---

## Milestone 11 — Generate endpoint

### Task 11.1: In-memory throttle dependency

**Files:**
- Create: `app/modules/llm_pipeline/routers/throttle.py`
- Test: `tests/unit/modules/llm_pipeline/test_throttle.py`

- [ ] **Step 1: Test**

```python
# tests/unit/modules/llm_pipeline/test_throttle.py
import time
import uuid

import pytest

from app.modules.llm_pipeline.routers.throttle import (
    InMemoryThrottle,
    ThrottleExceeded,
)


def test_under_limit_allowed():
    t = InMemoryThrottle(max_calls=3, window_seconds=60)
    uid = uuid.uuid4()
    for _ in range(3):
        t.check(uid)


def test_over_limit_raises():
    t = InMemoryThrottle(max_calls=2, window_seconds=60)
    uid = uuid.uuid4()
    t.check(uid)
    t.check(uid)
    with pytest.raises(ThrottleExceeded):
        t.check(uid)


def test_window_expiry_resets(monkeypatch):
    t = InMemoryThrottle(max_calls=1, window_seconds=1)
    uid = uuid.uuid4()
    t.check(uid)
    # advance "time"
    monkeypatch.setattr(time, "monotonic", lambda: time.monotonic() + 2)
    t.check(uid)  # no raise
```

- [ ] **Step 2: Implement throttle**

```python
# app/modules/llm_pipeline/routers/throttle.py
"""In-memory per-user rate limiter for /drafts/generate.

Per spec §7.2 — 10 calls per 60 sec per requested_by user. In-memory means
the limit is per worker; multi-worker deployments may exceed it, accepted
trade-off for v1.
"""
import threading
import time
import uuid
from collections import defaultdict, deque


class ThrottleExceeded(Exception):
    pass


class InMemoryThrottle:
    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._calls: dict[uuid.UUID, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: uuid.UUID) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._calls[user_id]
            while q and q[0] < now - self._window:
                q.popleft()
            if len(q) >= self._max:
                raise ThrottleExceeded(
                    f"max {self._max} calls per {self._window}s exceeded"
                )
            q.append(now)


_DEFAULT_THROTTLE = InMemoryThrottle(max_calls=10, window_seconds=60)


def get_throttle() -> InMemoryThrottle:
    return _DEFAULT_THROTTLE
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_throttle.py -v
git add app/modules/llm_pipeline/routers/throttle.py tests/unit/modules/llm_pipeline/test_throttle.py
git commit -m "feat(llm-pipeline): add in-memory per-user throttle for generate endpoint"
```

---

### Task 11.2: `draft_router` POST `/drafts/generate`

**Files:**
- Create: `app/modules/llm_pipeline/routers/draft_router.py`
- Test: `tests/unit/modules/llm_pipeline/test_draft_router.py`
- Modify: `app/api/v1/__init__.py`

- [ ] **Step 1: Implement router**

`app/modules/llm_pipeline/routers/draft_router.py`:

```python
"""POST /api/v1/llm-pipeline/drafts/generate."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.config import Settings, get_settings
from app.core.database import get_db_session_factory
from app.core.deps import get_anthropic_client
from app.modules.auth.models.user import User
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.llm_pipeline.exceptions import LlmDraftError
from app.modules.llm_pipeline.repositories.doc_repository import DocRepository
from app.modules.llm_pipeline.repositories.llm_generation_job_repository import (
    LlmGenerationJobRepository,
)
from app.modules.llm_pipeline.routers.throttle import (
    InMemoryThrottle,
    ThrottleExceeded,
    get_throttle,
)
from app.modules.llm_pipeline.schemas import (
    GenerateDraftErrorPayload,
    GenerateDraftRequest,
    GenerateDraftResponse,
)
from app.modules.llm_pipeline.services.llm_draft_service import LlmDraftService
from app.modules.llm_pipeline.services.vrl_validator import validate_vrl

router = APIRouter()


_HTTP_FOR_CODE = {
    "schema_mismatch":      422,
    "vrl_fields_disjoint":  422,
    "vrl_compile_failed":   422,
    "anthropic_failed":     502,
    "db_write_failed":      500,
}


def _draft_service(
    settings: Annotated[Settings, Depends(get_settings)],
    anthropic_client: Annotated[Any, Depends(get_anthropic_client)],
    session_factory: Annotated[async_sessionmaker, Depends(get_db_session_factory)],
) -> LlmDraftService:
    return LlmDraftService(
        session_factory=session_factory,
        anthropic_client=anthropic_client,
        model=settings.llm_pipeline_draft_model,
        doc_repo_factory=lambda s: DocRepository(s),
        vendor_repo_factory=lambda s: VendorRepository(s),
        product_repo_factory=lambda s: ProductRepository(s),
        log_type_repo_factory=lambda s: LogTypeRepository(s),
        parse_rule_repo_factory=lambda s: ParseRuleRepository(s),
        field_schema_repo_factory=lambda s: FieldSchemaRepository(s),
        job_repo=LlmGenerationJobRepository(session_factory),
        vrl_validator=validate_vrl,
    )


@router.post(
    "/drafts/generate",
    response_model=DataResponse[GenerateDraftResponse],
)
async def generate_draft(
    body: GenerateDraftRequest,
    service: Annotated[LlmDraftService, Depends(_draft_service)],
    throttle: Annotated[InMemoryThrottle, Depends(get_throttle)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[GenerateDraftResponse]:
    try:
        throttle.check(user.id)
    except ThrottleExceeded as e:
        raise HTTPException(status_code=429, detail=str(e)) from e

    try:
        result = await service.generate_draft(
            doc_id=body.doc_id, product_id=body.product_id,
            requested_by=user.id, hint=body.hint,
        )
    except LlmDraftError as e:
        http = _HTTP_FOR_CODE.get(e.error_code, 500)
        raise HTTPException(
            status_code=http,
            detail=GenerateDraftErrorPayload(
                job_id=getattr(e, "job_id", None) or "00000000-0000-0000-0000-000000000000",
                error_code=e.error_code,
                error_message=str(e),
            ).model_dump(mode="json"),
        ) from e

    return DataResponse(
        data=GenerateDraftResponse(
            job_id=result.job_id,
            log_type_id=result.log_type_id,
            parse_rule_id=result.parse_rule_id,
        )
    )
```

(`get_db_session_factory` may not exist yet — verify in `app/core/database.py`. If only `get_db_session` exists, add a sibling that returns the underlying `async_sessionmaker`. Document any new dep in this task.)

- [ ] **Step 2: Surface job_id on raised LlmDraftError**

For the error response to include the real `job_id`, the service must attach it before re-raising. Modify `llm_draft_service.generate_draft` `except LlmDraftError` block:

```python
        except LlmDraftError as e:
            await self._job_repo.finish_failed(
                job_id,
                error_code=e.error_code,
                error_message=str(e),
                raw_response=_truncate_response(_serialize_response(response)) if response is not None else None,
            )
            e.job_id = job_id  # type: ignore[attr-defined]  # consumed by router
            raise
```

- [ ] **Step 3: Mount router**

In `app/api/v1/__init__.py`:

```python
from app.modules.llm_pipeline.routers.draft_router import router as llm_pipeline_draft_router
...
router.include_router(llm_pipeline_draft_router, prefix="/llm-pipeline", tags=["llm-pipeline:drafts"])
```

- [ ] **Step 4: Router-level test (auth + throttle wiring)**

`tests/unit/modules/llm_pipeline/test_draft_router.py`:

```python
import pytest


pytestmark = pytest.mark.asyncio


class TestPostGenerateDraft:
    async def test_requires_auth(self, async_client):
        r = await async_client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": "00000000-0000-0000-0000-000000000001",
                  "product_id": "00000000-0000-0000-0000-000000000002"},
        )
        assert r.status_code in (401, 403)

    async def test_404_when_doc_missing(self, async_client_authed):
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": "00000000-0000-0000-0000-000000000001",
                  "product_id": "00000000-0000-0000-0000-000000000002"},
        )
        # may be 422 if product_id validation fires first; pin to 404 by seeding product
        assert r.status_code in (404, 422)
```

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/unit/modules/llm_pipeline/test_draft_router.py -v
git add app/modules/llm_pipeline/routers/draft_router.py app/modules/llm_pipeline/services/llm_draft_service.py app/api/v1/__init__.py tests/unit/modules/llm_pipeline/test_draft_router.py
git commit -m "feat(llm-pipeline): POST /llm-pipeline/drafts/generate endpoint"
```

---

## Milestone 12 — End-to-end integration tests

### Task 12.1: Happy flow integration test

**Files:**
- Create: `tests/integration/modules/llm_pipeline/test_e2_flow.py`

- [ ] **Step 1: Write integration test**

```python
"""End-to-end happy + failure flows for E2 pipeline.

Real Postgres + Redis + alembic-migrated schema. Anthropic is mocked at
the dep-override boundary so no real network calls happen.
"""
import uuid
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _good_response(field_name="src_ip"):
    return SimpleNamespace(
        content=[SimpleNamespace(
            type="tool_use", name="submit_draft", id="t1",
            input={
                "log_type": {"name": "PAN-OS TRAFFIC", "format": "syslog",
                             "transport": "syslog_udp", "description": None},
                "fields": [{"field_name": field_name, "field_type": "ip",
                            "is_required": True, "is_identifier": False,
                            "description": None, "example_value": None}],
                "vrl_code": f". = parse_syslog!(.message)\n.{field_name} = parts[6] ?? null",
                "engine_version": "0.32",
                "notes": "ok",
            },
        )],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=10),
        model_dump=lambda: {"id": "x"},
    )


class TestE2HappyFlow:
    async def test_upload_doc_then_generate_writes_three_tables(
        self, app, async_client_authed, override_anthropic, seed_vendor_product,
    ):
        vendor, product = seed_vendor_product
        # 1. upload doc
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/docs",
            json={"vendor_id": str(vendor.id), "url": "https://x/a", "content": "# hi"},
        )
        assert r.status_code == 201, r.text
        doc_id = r.json()["data"]["id"]

        # 2. override anthropic to return canned response
        override_anthropic(_good_response())

        # 3. generate draft
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert "log_type_id" in body
        assert "parse_rule_id" in body
        assert "job_id" in body
```

(`override_anthropic` and `seed_vendor_product` fixtures need to exist in conftest. If not present, add them in `tests/integration/modules/llm_pipeline/conftest.py`.)

- [ ] **Step 2: Add conftest with fixtures**

`tests/integration/modules/llm_pipeline/conftest.py`:

```python
import uuid

import pytest

from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor


@pytest.fixture
async def seed_vendor_product(db_session):
    v = Vendor(id=uuid.uuid4(), name="Acme",
               slug=f"acme-{uuid.uuid4().hex[:6]}", status="active")
    db_session.add(v)
    await db_session.flush()
    p = Product(id=uuid.uuid4(), vendor_id=v.id, name="FW",
                slug=f"fw-{uuid.uuid4().hex[:6]}", status="active")
    db_session.add(p)
    await db_session.flush()
    await db_session.commit()
    return v, p


@pytest.fixture
def override_anthropic(app):
    """Override get_anthropic_client to return a stub that returns a canned message."""
    from app.core.deps import get_anthropic_client

    captured = {}

    def _override(canned_response):
        class _Stub:
            def __init__(self):
                self.messages = self
            async def create(self, **_):
                return canned_response
        captured["stub"] = _Stub()
        app.dependency_overrides[get_anthropic_client] = lambda: captured["stub"]

    yield _override
    app.dependency_overrides.pop(get_anthropic_client, None)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/integration/modules/llm_pipeline/ -v -m integration
git add tests/integration/modules/llm_pipeline/test_e2_flow.py tests/integration/modules/llm_pipeline/conftest.py
git commit -m "test(llm-pipeline): e2e happy flow with mocked Anthropic"
```

---

### Task 12.2: Failure flow integration tests

**Files:**
- Modify: `tests/integration/modules/llm_pipeline/test_e2_flow.py`

- [ ] **Step 1: Add failure tests**

```python
class TestE2FailureFlows:
    async def test_schema_mismatch_no_library_writes(
        self, async_client_authed, override_anthropic, seed_vendor_product,
    ):
        vendor, product = seed_vendor_product
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/docs",
            json={"vendor_id": str(vendor.id), "content": "# x"},
        )
        doc_id = r.json()["data"]["id"]

        bad_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hi")],
            stop_reason="end_turn",
            model_dump=lambda: {"id": "x"},
        )
        override_anthropic(bad_resp)

        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 422
        body = r.json()["detail"]
        assert body["error_code"] == "schema_mismatch"

    async def test_vrl_compile_failed_no_library_writes(
        self, async_client_authed, override_anthropic, seed_vendor_product,
    ):
        vendor, product = seed_vendor_product
        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/docs",
            json={"vendor_id": str(vendor.id), "content": "# x"},
        )
        doc_id = r.json()["data"]["id"]

        # canned response with intentionally invalid VRL
        bad_vrl_resp = SimpleNamespace(
            content=[SimpleNamespace(
                type="tool_use", name="submit_draft", id="t1",
                input={
                    "log_type": {"name": "X", "format": "json",
                                 "transport": None, "description": None},
                    "fields": [{"field_name": "x", "field_type": "string",
                                "is_required": False, "is_identifier": False,
                                "description": None, "example_value": None}],
                    "vrl_code": "this is not vrl !!!!",
                    "engine_version": "0.32",
                    "notes": "",
                },
            )],
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0),
            model_dump=lambda: {"id": "x"},
        )
        override_anthropic(bad_vrl_resp)

        r = await async_client_authed.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error_code"] == "vrl_compile_failed"
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest tests/integration/modules/llm_pipeline/ -v -m integration
git add tests/integration/modules/llm_pipeline/test_e2_flow.py
git commit -m "test(llm-pipeline): e2e failure flows for schema_mismatch and vrl_compile_failed"
```

---

## Final verification

- [ ] **Run all tests, lint, type-check**

```bash
uv run pytest -v
uv run ruff check app tests
uv run pyright app
```
Expected: all green, zero new ruff/pyright errors.

- [ ] **Confirm migration head**

```bash
uv run alembic current
```
Expected: `0010_add_llm_lineage_fk_constraints (head)`.

- [ ] **Smoke test the live endpoints (manual)**

Start the dev server (`uv run uvicorn app.main:app --reload`), upload a small markdown doc via curl, then trigger generate with a mocked LLM (or real Anthropic if API key is set). Confirm the three rows appear in DB:

```sql
SELECT lt.id, lt.status, lt.source, lt.source_job_id,
       pr.id, pr.status, pr.source, pr.source_job_id,
       j.status, j.error_code
FROM log_types lt
JOIN parse_rules pr ON pr.log_type_id = lt.id
JOIN llm_generation_jobs j ON j.id = lt.source_job_id
WHERE lt.status = 'llm_draft'
ORDER BY lt.created_at DESC
LIMIT 5;
```

---

## Spec coverage checklist (self-review)

| Spec section | Covered by |
|---|---|
| §1.1 new module + admin doc upload | Tasks 3.1 / 5.1 / 5.2 / 5.3 |
| §1.1 generate endpoint + LLM call + 3-table writes | Tasks 4.1 / 8.* / 9.* / 10.* / 11.* |
| §1.1 library schema extensions | Tasks 1.1 / 3.3 / 3.4 |
| §1.1 Anthropic client refactor | Task 0.2 / 0.3 / 0.4 |
| §1.1 VRL cheatsheet refactor | Task 0.5 |
| §1.1 unit + integration tests | Throughout; M12 |
| §2.1 docs table | Task 2.1 |
| §2.1 jobs table | Task 2.2 |
| §2.2 log_types extension | Tasks 2.3 / 3.3 |
| §2.2 parse_rules extension | Tasks 2.4 / 3.4 |
| §2.2 field_schemas unchanged | Confirmed (no task) |
| §2.3 service-layer invariants | Task 10.2 (status="llm_draft" forced in `_write_drafts`) |
| §2.4 circular FK migration order | Tasks 2.1 → 2.5 |
| §3.1 module structure | Task 3.1 / scaffold steps |
| §3.2.1 Anthropic client shared | Task 0.2 / 0.3 / 0.4 |
| §3.2.2 cheatsheet shared | Task 0.5 |
| §3.4 3-tx pattern | Tasks 7.1 / 10.2 |
| §3.5 endpoints | Tasks 5.3 / 11.2 |
| §4.1 tool schema | Task 8.1 |
| §4.2 Block 1 | Task 8.2 |
| §4.3 Block 2 | Task 8.3 |
| §4.4 doc truncation | Task 8.3 (test_doc_truncation) |
| §4.5 engine + hint | Task 4.1 schemas + 8.3 renderer |
| §4.6 cost (informational) | Settings + Task 0.1 |
| §5.1 validation pipeline | Tasks 9.1 / 9.2 / 6.2 / 10.2 |
| §5.4 HTTP mapping | Task 11.2 (`_HTTP_FOR_CODE`) |
| §6 testing strategy | All test tasks |
| §7.1 sync block + proxy timeout note | Documented in spec; runtime concern, no code task |
| §7.2 in-memory throttle | Task 11.1 |
| §7.3 doc truncation mitigation | Task 8.3 + Task 4.1 (hint) |
| §7.4 LLM hallucination mitigation | Task 9.2 (self-consistency) + Task 8.2 (Block 1 prompt) |
| §7.5 current_parse_rule invariant unchanged | Confirmed (no task) |
| §7.6 refactor blast radius | Task 0.3 + 0.4 + 0.5 each run existing test suites |

---

## Notes for the executing engineer

- **Conftest fixtures**: This plan refers to `db_session`, `db_session_factory`, `async_client`, `async_client_authed`, `app`, `seed_vendor`. Verify each name in `tests/conftest.py` and `tests/integration/conftest.py`. If a name differs, do a one-shot rename in the new test files — do NOT change conftest fixtures (existing tests depend on them).

- **`get_db_session_factory`**: If this dep doesn't exist in `app/core/database.py`, add it next to `get_db_session`. It must return the project's `async_sessionmaker` (singleton) so the job repository can open independent transactions.

- **`replace_for_log_type` signature**: confirm in step 6.2 / Task 10.2. The service's `_write_drafts` must call it correctly. If the existing repo method has a different name (e.g. `bulk_replace`), use that name throughout.

- **`vrl_runtime.compile_program` signature**: confirm in Task 6.2 step 1. Wrap whatever exception class it raises.

- **Slug collision**: `_slugify(draft.log_type.name)` may collide with an existing log_type's slug under the same product (DB has unique(product_id, slug)). If conflict happens, INSERT will raise IntegrityError → caught by `_write_drafts` `except` → `DbWriteError`. v1 acceptable: reviewer will see job failed with `db_write_failed`, can rename hint and retry. (No retry-with-suffix logic in v1.)

- **CLAUDE.md**: do NOT auto-commit unless the user requests. Each task lists a `git commit` step — execute only if running with explicit auto-commit instruction; otherwise stop after passing tests and let the user commit.
