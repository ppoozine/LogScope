# 1b: Library Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1a 骨架上實作 LogScope Library 的後端 — 6 張 library 表 + 完整 CRUD + Library overview 聚合 endpoint，以及一條 end-to-end 的 integration test 證明 vendor → product → log_type → fields → parse_rule → publish → sample 流程可走。

**Architecture:** 沿用 Plan 1a 立的 feature module 結構（`app/modules/library/{models,repositories,services,routers}/`、共用 schemas.py 集中所有 Pydantic I/O）。Repo 提供 `get/list/create/update/delete` 基本動作，Service 處理業務邏輯與跨 repo 操作（例如 publish 同時改 LogType 與 ParseRule），Router 依賴注入 Service。`api/v1/__init__.py` 聚合掛載各 module 的 router。LogType 與 ParseRule 之間有循環 FK，migration 用 `use_alter=True` + ALTER 兩階段建。

**Tech Stack:** Python 3.13、async SQLAlchemy 2.0 + asyncpg、Alembic、Pydantic v2、FastAPI、pytest + pytest-asyncio、AAA pattern。

**Spec ref:** `docs/superpowers/specs/2026-05-08-foundation-and-library-min-design.md` §4 資料模型、§5 API 規格、§8 測試。

---

## File Structure（本 plan 範圍）

| 路徑 | 職責 |
|---|---|
| `tests/conftest.py` | **新增** — 共用 fixtures（`app`, `client`, `mock_session`, `mock_redis`, helper builders）抽出，1a 的 inline fixtures 改用 |
| `app/modules/library/__init__.py` | 空檔 |
| `app/modules/library/models/__init__.py` | export 6 個 model |
| `app/modules/library/models/vendor.py` | Vendor ORM |
| `app/modules/library/models/product.py` | Product ORM |
| `app/modules/library/models/log_type.py` | LogType ORM（含 `current_parse_rule_id` 循環 FK，`use_alter=True`） |
| `app/modules/library/models/field_schema.py` | FieldSchema ORM |
| `app/modules/library/models/parse_rule.py` | ParseRule ORM |
| `app/modules/library/models/sample_log.py` | SampleLog ORM |
| `app/alembic/versions/0003_init_library.py` | 6 張表 + 循環 FK ALTER + 全表的 updated_at trigger |
| `app/modules/library/schemas.py` | 全 Library 的 Pydantic I/O schemas（Read/Create/Update/Nested/Overview） |
| `app/modules/library/repositories/__init__.py` | 空檔 |
| `app/modules/library/repositories/vendor_repository.py` | get/list/create/update/delete |
| `app/modules/library/repositories/product_repository.py` | 同上，+ `list_by_vendor`、`get_by_vendor_and_slug` |
| `app/modules/library/repositories/log_type_repository.py` | 同上，+ `list_by_product`、`get_by_product_and_slug` |
| `app/modules/library/repositories/field_schema_repository.py` | `list_by_log_type`、`replace_for_log_type`（transaction 內 delete-then-insert） |
| `app/modules/library/repositories/parse_rule_repository.py` | get/list_by_log_type/create/update_draft/get_max_version |
| `app/modules/library/repositories/sample_log_repository.py` | get/list_by_log_type/create/delete |
| `app/modules/library/services/__init__.py` | 空檔 |
| `app/modules/library/services/vendor_service.py` | 業務邏輯 |
| `app/modules/library/services/product_service.py` | |
| `app/modules/library/services/log_type_service.py` | 含 publish flow |
| `app/modules/library/services/field_schema_service.py` | bulk replace |
| `app/modules/library/services/parse_rule_service.py` | 建新 draft、PATCH draft |
| `app/modules/library/services/sample_log_service.py` | |
| `app/modules/library/services/library_overview_service.py` | 聚合 vendor/product/log_type 計數 |
| `app/modules/library/routers/__init__.py` | 空檔 |
| `app/modules/library/routers/vendor_router.py` | `/library/vendors/...` |
| `app/modules/library/routers/product_router.py` | `/library/vendors/{vendor_slug}/products/...` 與 `/library/products/{id}` |
| `app/modules/library/routers/log_type_router.py` | `/library/products/{product_id}/log_types`、`/library/log_types/{id}`、`.../publish` |
| `app/modules/library/routers/field_schema_router.py` | `PUT /library/log_types/{id}/fields` |
| `app/modules/library/routers/parse_rule_router.py` | `/library/log_types/{id}/parse_rules`、`/library/parse_rules/{id}` |
| `app/modules/library/routers/sample_log_router.py` | `/library/log_types/{id}/samples`、`/library/samples/{id}` |
| `app/modules/library/routers/library_overview_router.py` | `GET /library/overview` |
| `app/api/v1/__init__.py` | **修改** — include 上述 7 個 library router |
| `app/alembic/env.py` | **修改** — 加 import library models（讓 alembic autogenerate 能掃） |
| `tests/unit/modules/library/...` | 各 service / router 的 unit test |
| `tests/integration/modules/library/test_library_flow.py` | end-to-end flow test |

---

## Task 1: 抽 `tests/conftest.py` 共用 fixtures

Plan 1a 各 unit test 都自建 inline `app` fixture；1b 模組多，這個 inline 重複會炸。先抽公共 fixture。

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/unit/test_health.py`（改用共用 fixture）
- Modify: `tests/unit/modules/auth/test_auth_router.py`（改用共用 fixture）

- [ ] **Step 1: 寫 `tests/conftest.py`**

```python
"""Shared pytest fixtures and mock helpers.

Only fixtures that are useful across multiple test files belong here.
Single-test helpers should stay in the test file.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


# =============================================================================
# Mock DB helpers (mirroring growin's pattern)
# =============================================================================


def make_mock_session_for_single(return_value):
    """Mock AsyncSession whose `execute().scalar_one_or_none()` returns `return_value`."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


def make_mock_session_for_list(return_value: list):
    """Mock AsyncSession whose `execute().scalars().all()` returns `return_value`."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = return_value
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


def make_mock_session_for_side_effects(side_effects: list):
    """Mock AsyncSession whose `execute()` returns successive results.

    Each item in `side_effects` is either a list (treated as scalars().all())
    or a scalar value (treated as scalar_one_or_none()).
    """
    mock_session = MagicMock()
    mock_results = []
    for value in side_effects:
        mock_result = MagicMock()
        if isinstance(value, list):
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = value
            mock_result.scalars.return_value = mock_scalars
        else:
            mock_result.scalar_one_or_none.return_value = value
        mock_results.append(mock_result)
    mock_session.execute = AsyncMock(side_effect=mock_results)
    return mock_session


# =============================================================================
# Mock Redis helper
# =============================================================================


def make_mock_redis(*, get_return: str | None = None) -> MagicMock:
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=get_return)
    redis.delete = AsyncMock(return_value=1)
    return redis


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app instance with no-op lifespan (no real DB / Redis needed for unit tests)."""
    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_a: FastAPI) -> AsyncGenerator[None, None]:
        yield

    app.router.lifespan_context = _noop_lifespan
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient bound to the test FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: 改 `tests/unit/test_health.py`**

把 inline 的 `app` fixture 拿掉，改用共用 fixture 並加 `client`：

```python
class TestHealth:
    """Tests for /healthz endpoint."""

    async def test_healthz_returns_200(self, client):
        """Should return 200 with status=ok."""
        # Arrange / Act
        response = await client.get("/healthz")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

整個檔案最終長這樣（替換完整內容）：

```python
class TestHealth:
    """Tests for /healthz endpoint."""

    async def test_healthz_returns_200(self, client):
        """Should return 200 with status=ok."""
        # Arrange / Act
        response = await client.get("/healthz")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: 改 `tests/unit/modules/auth/test_auth_router.py`**

刪掉檔案頭的 inline `app` fixture（自有的），保留三個 TestClass，把每個 test 的 `(self, app: FastAPI)` 改成 `(self, app, client)` 並把 inline `AsyncClient(...)` 改成直接用 `client`。

完整改法：

```python
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user, get_auth_service
from app.modules.auth.models.user import User


class TestLoginRoute:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_returns_session_cookie_on_success(self, app: FastAPI, client: AsyncClient):
        """Should set HttpOnly session cookie when login succeeds."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(return_value="sid-abc")
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.c", "password": "x"},
        )

        # Assert
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "session=sid-abc" in cookie
        assert "HttpOnly" in cookie

    async def test_login_returns_401_on_invalid(self, app: FastAPI, client: AsyncClient):
        """Should map UnauthorizedError to 401."""
        # Arrange
        from app.common.exceptions import UnauthorizedError

        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(side_effect=UnauthorizedError("invalid credentials"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.c", "password": "x"},
        )

        # Assert
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"


class TestMeRoute:
    """Tests for GET /api/v1/auth/me."""

    async def test_me_returns_user(self, app: FastAPI, client: AsyncClient):
        """Should return current user when authenticated."""
        # Arrange
        import uuid
        from datetime import UTC, datetime

        u = User()
        u.id = uuid.uuid4()
        u.email = "me@x.y"
        u.display_name = "Me"
        u.is_active = True
        u.created_at = datetime.now(UTC)
        u.updated_at = datetime.now(UTC)

        app.dependency_overrides[current_user] = lambda: u

        # Act
        r = await client.get("/api/v1/auth/me")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == "me@x.y"
        assert body["data"]["display_name"] == "Me"


class TestLogoutRoute:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_clears_cookie(self, app: FastAPI, client: AsyncClient):
        """Should call AuthService.logout and clear cookie."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.logout = AsyncMock(return_value=None)
        app.dependency_overrides[get_auth_service] = lambda: fake_auth
        client.cookies.set("session", "sid-abc")

        # Act
        r = await client.post("/api/v1/auth/logout")

        # Assert
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "session=" in cookie
        assert "Max-Age=0" in cookie
        fake_auth.logout.assert_awaited_once_with("sid-abc")
```

- [ ] **Step 4: 跑全 unit test 確認沒壞**

Run: `uv run pytest tests/unit -v`
Expected: 22 passed（與 Plan 1a 數量相同）

- [ ] **Step 5: 跑 lint**

Run: `uv run ruff check . && uv run pyright`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/unit/test_health.py tests/unit/modules/auth/test_auth_router.py
git commit -m "test: extract shared conftest fixtures and helpers"
```

---

## Task 2: Library 6 個 SQLAlchemy models

**Files:**
- Create: `app/modules/library/__init__.py`（空檔）
- Create: `app/modules/library/models/__init__.py`
- Create: `app/modules/library/models/vendor.py`
- Create: `app/modules/library/models/product.py`
- Create: `app/modules/library/models/log_type.py`
- Create: `app/modules/library/models/field_schema.py`
- Create: `app/modules/library/models/parse_rule.py`
- Create: `app/modules/library/models/sample_log.py`
- Modify: `app/alembic/env.py`（加 library models import）

- [ ] **Step 1: `app/modules/library/__init__.py`**（空檔）

- [ ] **Step 2: `app/modules/library/models/vendor.py`**

```python
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
```

- [ ] **Step 3: `app/modules/library/models/product.py`**

```python
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class Product(Base, TimestampMixin):
    __tablename__ = "products"

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
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deploy_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    doc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
```

- [ ] **Step 4: `app/modules/library/models/log_type.py`**

LogType 有循環 FK 指向 ParseRule（用 `use_alter=True` 讓 Alembic 能延後加 constraint）：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class LogType(Base, TimestampMixin):
    __tablename__ = "log_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    transport: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    current_parse_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "parse_rules.id",
            use_alter=True,
            name="fk_log_types_current_parse_rule",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
```

- [ ] **Step 5: `app/modules/library/models/field_schema.py`**

```python
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class FieldSchema(Base, TimestampMixin):
    __tablename__ = "field_schemas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    log_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_identifier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    example_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 6: `app/modules/library/models/parse_rule.py`**

```python
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class ParseRule(Base, TimestampMixin):
    __tablename__ = "parse_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    log_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    vrl_code: Mapped[str] = mapped_column(Text, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
```

- [ ] **Step 7: `app/modules/library/models/sample_log.py`**

```python
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base


class SampleLog(Base, TimestampMixin):
    __tablename__ = "sample_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    log_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_log: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
```

- [ ] **Step 8: `app/modules/library/models/__init__.py`**

```python
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.models.vendor import Vendor

__all__ = [
    "FieldSchema",
    "LogType",
    "ParseRule",
    "Product",
    "SampleLog",
    "Vendor",
]
```

- [ ] **Step 9: 修改 `app/alembic/env.py`，加 library models import**

在現有的 `from app.modules.auth.models import user as _user_model  # noqa: F401  # type: ignore[import-not-found]` 那行下面加：

```python
# Library models
from app.modules.library.models import (  # noqa: F401
    field_schema as _field_schema_model,
    log_type as _log_type_model,
    parse_rule as _parse_rule_model,
    product as _product_model,
    sample_log as _sample_log_model,
    vendor as _vendor_model,
)
```

- [ ] **Step 10: lint + test**

Run: `uv run ruff check . && uv run pyright app/modules/library/ && uv run pytest tests/unit -v`
Expected: 0 lint errors, 0 pyright errors, 22 unit tests still passing

- [ ] **Step 11: Commit**

```bash
git add app/modules/library/ app/alembic/env.py
git commit -m "feat(library): add 6 SQLAlchemy models for Library tables"
```

---

## Task 3: Migration 0003 — 6 個 library 表 + 循環 FK + triggers

**Files:**
- Create: `app/alembic/versions/0003_init_library.py`

- [ ] **Step 1: 建 revision 骨架**

Run: `uv run alembic revision -m "init library"`
然後把產生的檔重 rename 為 `0003_init_library.py`

- [ ] **Step 2: 覆寫內容**

```python
"""init library

Revision ID: 0003_init_library
Revises: 0002_seed_admin_user
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import (
    add_updated_at_trigger,
    drop_updated_at_trigger,
)

revision: str = "0003_init_library"
down_revision: str | None = "0002_seed_admin_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vendors
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_vendors_slug", "vendors", ["slug"])

    # products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("deploy_type", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("doc_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("vendor_id", "slug", name="uq_products_vendor_slug"),
    )
    op.create_index("ix_products_vendor_id", "products", ["vendor_id"])
    op.create_index("ix_products_category", "products", ["category"])

    # log_types — 不含 current_parse_rule_id FK constraint（先建，下面 ALTER 加）
    op.create_table(
        "log_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("transport", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("current_parse_rule_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK 之後 ALTER
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("product_id", "slug", name="uq_log_types_product_slug"),
    )
    op.create_index("ix_log_types_product_id", "log_types", ["product_id"])
    op.create_index("ix_log_types_status", "log_types", ["status"])

    # parse_rules
    op.create_table(
        "parse_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("vrl_code", sa.Text, nullable=False),
        sa.Column("engine_version", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("log_type_id", "version", name="uq_parse_rules_log_type_version"),
    )
    op.create_index("ix_parse_rules_log_type_id", "parse_rules", ["log_type_id"])
    op.create_index("ix_parse_rules_status", "parse_rules", ["status"])

    # 解循環：現在 ALTER log_types 加 FK 到 parse_rules
    op.create_foreign_key(
        "fk_log_types_current_parse_rule",
        "log_types",
        "parse_rules",
        ["current_parse_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # field_schemas
    op.create_table(
        "field_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_identifier", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("example_value", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("log_type_id", "field_name", name="uq_field_schemas_log_type_name"),
    )
    op.create_index("ix_field_schemas_log_type_id", "field_schemas", ["log_type_id"])
    op.create_index("ix_field_schemas_log_type_sort_order", "field_schemas", ["log_type_id", "sort_order"])

    # sample_logs
    op.create_table(
        "sample_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_log", sa.Text, nullable=False),
        sa.Column("label", sa.String(20), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_sample_logs_log_type_id", "sample_logs", ["log_type_id"])

    # 為每張表加 updated_at trigger
    for table in ("vendors", "products", "log_types", "parse_rules", "field_schemas", "sample_logs"):
        add_updated_at_trigger(table)


def downgrade() -> None:
    for table in ("sample_logs", "field_schemas", "parse_rules", "log_types", "products", "vendors"):
        drop_updated_at_trigger(table)
    op.drop_table("sample_logs")
    op.drop_table("field_schemas")
    op.drop_constraint("fk_log_types_current_parse_rule", "log_types", type_="foreignkey")
    op.drop_table("parse_rules")
    op.drop_table("log_types")
    op.drop_table("products")
    op.drop_table("vendors")
```

- [ ] **Step 3: 跑 migration**

Run: `uv run alembic upgrade head`
Expected: log 顯示 `Running upgrade 0002_seed_admin_user -> 0003_init_library`

- [ ] **Step 4: 驗證 schema**

Run: `docker compose exec postgres psql -U logscope -c "\dt"`
Expected: 看到 vendors / products / log_types / parse_rules / field_schemas / sample_logs / users 共 7 個 table（加上 alembic_version）

驗證 trigger：

```bash
docker compose exec postgres psql -U logscope -c "SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg_%' ORDER BY tgname;"
```

Expected: 7 個 trigger（含 users 那個）

驗證循環 FK：

```bash
docker compose exec postgres psql -U logscope -c "\d log_types"
```

Expected: 看到 `\"current_parse_rule_id\" REFERENCES parse_rules(id) ON DELETE SET NULL`

- [ ] **Step 5: lint + test 確認沒壞**

Run: `uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠，22 unit tests pass

- [ ] **Step 6: Commit**

```bash
git add app/alembic/versions/0003_init_library.py
git commit -m "feat(alembic): add 0003 init library migration with circular FK and triggers"
```

---

## Task 4: Library Pydantic schemas（一個檔集中所有 I/O）

**Files:**
- Create: `app/modules/library/schemas.py`

- [ ] **Step 1: 實作**

```python
# app/modules/library/schemas.py
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Common literal types
# =============================================================================

VendorStatus = Literal["active", "inactive"]
ProductStatus = Literal["active", "inactive"]
ProductCategory = Literal["network", "endpoint", "auth", "other"]
DeployType = Literal["cloud", "on_prem", "hybrid"]
LogTypeStatus = Literal["draft", "published"]
LogTypeSource = Literal["manual"]
LogFormat = Literal["syslog", "json", "cef", "leef", "csv", "other"]
LogTransport = Literal["syslog_udp", "syslog_tcp", "http", "file", "other"]
FieldType = Literal["string", "int", "float", "bool", "timestamp", "ip", "object", "array"]
EngineVersion = Literal["0.25", "0.32"]
ParseRuleStatus = Literal["draft", "published"]
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
    category: ProductCategory | None = None
    doc_url: str | None = None
    status: ProductStatus = "active"


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: str | None = None
    description: str | None = None
    deploy_type: DeployType | None = None
    category: ProductCategory | None = None
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
    category: ProductCategory | None
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
    category: ProductCategory | None
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
```

- [ ] **Step 2: lint + pyright**

Run: `uv run ruff check app/modules/library/schemas.py && uv run pyright app/modules/library/schemas.py`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add app/modules/library/schemas.py
git commit -m "feat(library): add Pydantic schemas for all Library entities"
```

---

## Task 5: VendorRepository

**Files:**
- Create: `app/modules/library/repositories/__init__.py`（空檔）
- Create: `app/modules/library/repositories/vendor_repository.py`
- Create: `tests/unit/modules/library/__init__.py`（空檔）
- Create: `tests/unit/modules/library/test_vendor_repository.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_vendor_repository.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)

from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.vendor_repository import VendorRepository


def _make_vendor(slug: str = "acme", name: str = "Acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = name
    v.slug = slug
    v.status = "active"
    return v


class TestVendorRepositoryGetBySlug:
    """Tests for VendorRepository.get_by_slug()."""

    async def test_returns_vendor_when_found(self):
        """Should return Vendor when slug matches."""
        # Arrange
        target = _make_vendor("acme")
        session = make_mock_session_for_single(target)
        repo = VendorRepository(session)

        # Act
        result = await repo.get_by_slug("acme")

        # Assert
        assert result is target
        session.execute.assert_awaited_once()

    async def test_returns_none_when_missing(self):
        """Should return None when slug does not exist."""
        # Arrange
        session = make_mock_session_for_single(None)
        repo = VendorRepository(session)

        # Act
        result = await repo.get_by_slug("missing")

        # Assert
        assert result is None


class TestVendorRepositoryList:
    """Tests for VendorRepository.list()."""

    async def test_returns_all_vendors(self):
        """Should return list of vendors from session."""
        # Arrange
        vendors = [_make_vendor("a"), _make_vendor("b")]
        session = make_mock_session_for_list(vendors)
        repo = VendorRepository(session)

        # Act
        result = await repo.list()

        # Assert
        assert result == vendors


class TestVendorRepositoryCreate:
    """Tests for VendorRepository.create()."""

    async def test_creates_and_flushes(self):
        """Should add Vendor to session, flush, refresh, and return it."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = VendorRepository(session)
        vendor = _make_vendor()

        # Act
        result = await repo.create(vendor)

        # Assert
        session.add.assert_called_once_with(vendor)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(vendor)
        assert result is vendor


class TestVendorRepositoryDelete:
    """Tests for VendorRepository.delete()."""

    async def test_deletes_vendor(self):
        """Should call session.delete and flush."""
        # Arrange
        session = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        repo = VendorRepository(session)
        vendor = _make_vendor()

        # Act
        await repo.delete(vendor)

        # Assert
        session.delete.assert_awaited_once_with(vendor)
        session.flush.assert_awaited_once()
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_vendor_repository.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/repositories/vendor_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.vendor import Vendor


class VendorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.id == vendor_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Vendor | None:
        result = await self._session.execute(select(Vendor).where(Vendor.slug == slug))
        return result.scalar_one_or_none()

    async def list(self, *, status: str | None = None) -> list[Vendor]:
        stmt = select(Vendor)
        if status is not None:
            stmt = stmt.where(Vendor.status == status)
        stmt = stmt.order_by(Vendor.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, vendor: Vendor) -> Vendor:
        self._session.add(vendor)
        await self._session.flush()
        await self._session.refresh(vendor)
        return vendor

    async def delete(self, vendor: Vendor) -> None:
        await self._session.delete(vendor)
        await self._session.flush()
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_vendor_repository.py -v`
Expected: PASS（4 個 test）

- [ ] **Step 5: lint**

Run: `uv run ruff check . && uv run pyright app/modules/library/repositories/`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add app/modules/library/repositories/__init__.py app/modules/library/repositories/vendor_repository.py tests/unit/modules/library/__init__.py tests/unit/modules/library/test_vendor_repository.py
git commit -m "feat(library): add VendorRepository"
```

---

## Task 6: VendorService

**Files:**
- Create: `app/modules/library/services/__init__.py`（空檔）
- Create: `app/modules/library/services/vendor_service.py`
- Create: `app/common/utils/__init__.py`（空檔，若不存在）
- Create: `app/common/utils/slug.py`
- Create: `tests/unit/common/utils/__init__.py`（空檔）
- Create: `tests/unit/common/utils/test_slug.py`
- Create: `tests/unit/modules/library/test_vendor_service.py`

- [ ] **Step 1: 寫 slug helper test**

```python
# tests/unit/common/utils/test_slug.py
from app.common.utils.slug import slugify


class TestSlugify:
    """Tests for slugify utility."""

    def test_lowercases_and_replaces_spaces(self):
        """Should lowercase and replace spaces with hyphens."""
        # Arrange / Act
        result = slugify("Palo Alto Networks")

        # Assert
        assert result == "palo-alto-networks"

    def test_strips_special_chars(self):
        """Should remove non-alphanumeric chars except hyphens."""
        # Arrange / Act
        result = slugify("Acme, Inc.")

        # Assert
        assert result == "acme-inc"

    def test_collapses_multiple_hyphens(self):
        """Should collapse runs of hyphens into one."""
        # Arrange / Act
        result = slugify("foo  --  bar")

        # Assert
        assert result == "foo-bar"

    def test_strips_leading_trailing_hyphens(self):
        """Should not start or end with a hyphen."""
        # Arrange / Act
        result = slugify("--hello--")

        # Assert
        assert result == "hello"
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/common/utils/test_slug.py -v`
Expected: ImportError

- [ ] **Step 3: 實作 slug helper**

```python
# app/common/utils/slug.py
import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Lowercases, replaces non-alphanumeric runs with single hyphens,
    and strips leading/trailing hyphens. Does not handle Unicode normalization
    beyond ASCII fold; callers needing CJK support should pre-transliterate.
    """
    lowered = text.lower()
    hyphenated = _NON_ALNUM.sub("-", lowered)
    return hyphenated.strip("-")
```

- [ ] **Step 4: Run slug test 預期通過**

Run: `uv run pytest tests/unit/common/utils/test_slug.py -v`
Expected: 4 passed

- [ ] **Step 5: 寫 VendorService test**

```python
# tests/unit/modules/library/test_vendor_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.vendor import Vendor
from app.modules.library.schemas import VendorCreate, VendorUpdate
from app.modules.library.services.vendor_service import VendorService


def _make_vendor(slug: str = "acme", name: str = "Acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = name
    v.slug = slug
    v.status = "active"
    return v


def _make_service(*, get_by_slug_returns: Vendor | None = None, get_by_id_returns: Vendor | None = None):
    repo = MagicMock()
    repo.get_by_slug = AsyncMock(return_value=get_by_slug_returns)
    repo.get_by_id = AsyncMock(return_value=get_by_id_returns)
    repo.list = AsyncMock(return_value=[])
    repo.create = AsyncMock(side_effect=lambda v: v)
    repo.delete = AsyncMock(return_value=None)
    return VendorService(repo), repo


class TestVendorServiceCreate:
    """Tests for VendorService.create()."""

    async def test_create_auto_generates_slug(self):
        """Should slugify name when slug omitted."""
        # Arrange
        service, repo = _make_service(get_by_slug_returns=None)
        request = VendorCreate(name="Palo Alto Networks")

        # Act
        result = await service.create(request, current_user_id=uuid.uuid4())

        # Assert
        assert result.slug == "palo-alto-networks"
        repo.create.assert_awaited_once()

    async def test_create_uses_provided_slug(self):
        """Should respect explicit slug."""
        # Arrange
        service, repo = _make_service(get_by_slug_returns=None)
        request = VendorCreate(name="Acme", slug="acme-corp")

        # Act
        result = await service.create(request, current_user_id=uuid.uuid4())

        # Assert
        assert result.slug == "acme-corp"

    async def test_create_raises_conflict_when_slug_exists(self):
        """Should raise ConflictError if slug already in DB."""
        # Arrange
        service, _ = _make_service(get_by_slug_returns=_make_vendor("acme"))
        request = VendorCreate(name="Acme")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(request, current_user_id=uuid.uuid4())


class TestVendorServiceUpdate:
    """Tests for VendorService.update()."""

    async def test_update_applies_changes(self):
        """Should apply provided fields to vendor."""
        # Arrange
        existing = _make_vendor("acme", "Old Name")
        service, repo = _make_service(get_by_id_returns=existing)
        repo.update = AsyncMock(side_effect=lambda v: v)
        request = VendorUpdate(name="New Name")

        # Act
        result = await service.update(existing.id, request)

        # Assert
        assert result.name == "New Name"

    async def test_update_raises_not_found(self):
        """Should raise NotFoundError when vendor missing."""
        # Arrange
        service, _ = _make_service(get_by_id_returns=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update(uuid.uuid4(), VendorUpdate(name="X"))


class TestVendorServiceDelete:
    """Tests for VendorService.delete()."""

    async def test_delete_calls_repo(self):
        """Should fetch then delete."""
        # Arrange
        existing = _make_vendor()
        service, repo = _make_service(get_by_id_returns=existing)

        # Act
        await service.delete(existing.id)

        # Assert
        repo.delete.assert_awaited_once_with(existing)

    async def test_delete_raises_not_found(self):
        """Should raise NotFoundError when missing."""
        # Arrange
        service, _ = _make_service(get_by_id_returns=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4())
```

- [ ] **Step 6: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_vendor_service.py -v`
Expected: ImportError

- [ ] **Step 7: 補 repository 缺的 update method**

修改 `app/modules/library/repositories/vendor_repository.py`，加：

```python
    async def update(self, vendor: Vendor) -> Vendor:
        await self._session.flush()
        await self._session.refresh(vendor)
        return vendor
```

- [ ] **Step 8: 實作 VendorService**

```python
# app/modules/library/services/vendor_service.py
import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.vendor import Vendor
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import VendorCreate, VendorUpdate


class VendorService:
    def __init__(self, repo: VendorRepository) -> None:
        self._repo = repo

    async def list(self, *, status: str | None = None) -> list[Vendor]:
        return await self._repo.list(status=status)

    async def get_by_slug(self, slug: str) -> Vendor:
        vendor = await self._repo.get_by_slug(slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {slug}")
        return vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor:
        vendor = await self._repo.get_by_id(vendor_id)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_id}")
        return vendor

    async def create(self, data: VendorCreate, *, current_user_id: uuid.UUID) -> Vendor:
        slug = data.slug or slugify(data.name)
        existing = await self._repo.get_by_slug(slug)
        if existing is not None:
            raise ConflictError(f"vendor slug already exists: {slug}")

        vendor = Vendor()
        vendor.name = data.name
        vendor.slug = slug
        vendor.website_url = data.website_url
        vendor.logo_url = data.logo_url
        vendor.status = data.status
        vendor.created_by = current_user_id
        return await self._repo.create(vendor)

    async def update(self, vendor_id: uuid.UUID, data: VendorUpdate) -> Vendor:
        vendor = await self.get_by_id(vendor_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(vendor, field, value)
        return await self._repo.update(vendor)

    async def delete(self, vendor_id: uuid.UUID) -> None:
        vendor = await self.get_by_id(vendor_id)
        await self._repo.delete(vendor)
```

- [ ] **Step 9: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/ -v`
Expected: 9 passed（4 repo + 5 service）

- [ ] **Step 10: lint + 全 unit test**

Run: `uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 11: Commit**

```bash
git add app/common/utils/ app/modules/library/services/ app/modules/library/repositories/vendor_repository.py tests/unit/common/utils/ tests/unit/modules/library/test_vendor_service.py
git commit -m "feat(library): add VendorService and slugify helper"
```

---

## Task 7: VendorRouter + 掛 api/v1

**Files:**
- Create: `app/modules/library/routers/__init__.py`（空檔）
- Create: `app/modules/library/routers/vendor_router.py`
- Modify: `app/api/v1/__init__.py`（include vendor_router）
- Create: `tests/unit/modules/library/test_vendor_router.py`

- [ ] **Step 1: 寫 router test**

```python
# tests/unit/modules/library/test_vendor_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.vendor import Vendor
from app.modules.library.routers.vendor_router import get_vendor_service


def _logged_in_user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "test@x.y"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_vendor(slug: str = "acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = "Acme"
    v.slug = slug
    v.website_url = None
    v.logo_url = None
    v.status = "active"
    v.created_at = datetime.now(UTC)
    v.updated_at = datetime.now(UTC)
    return v


class TestVendorList:
    """Tests for GET /api/v1/library/vendors."""

    async def test_returns_vendor_list(self, app: FastAPI, client: AsyncClient):
        """Should return paginated list of vendors."""
        # Arrange
        fake_service = AsyncMock()
        fake_service.list = AsyncMock(return_value=[_make_vendor("a"), _make_vendor("b")])
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 2

    async def test_requires_auth(self, app: FastAPI, client: AsyncClient):
        """Should 401 when not logged in."""
        # Arrange (no current_user override → real one runs, no cookie → 401)
        # Act
        r = await client.get("/api/v1/library/vendors")

        # Assert
        assert r.status_code == 401


class TestVendorGet:
    """Tests for GET /api/v1/library/vendors/{slug}."""

    async def test_returns_vendor_when_found(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with vendor body."""
        # Arrange
        target = _make_vendor("acme")
        fake_service = AsyncMock()
        fake_service.get_by_slug = AsyncMock(return_value=target)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors/acme")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["slug"] == "acme"

    async def test_returns_404_when_missing(self, app: FastAPI, client: AsyncClient):
        """Should return 404 when service raises NotFoundError."""
        # Arrange
        from app.common.exceptions import NotFoundError

        fake_service = AsyncMock()
        fake_service.get_by_slug = AsyncMock(side_effect=NotFoundError("vendor not found"))
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.get("/api/v1/library/vendors/missing")

        # Assert
        assert r.status_code == 404


class TestVendorCreate:
    """Tests for POST /api/v1/library/vendors."""

    async def test_creates_vendor(self, app: FastAPI, client: AsyncClient):
        """Should accept body and return 201 with created vendor."""
        # Arrange
        created = _make_vendor("acme")
        fake_service = AsyncMock()
        fake_service.create = AsyncMock(return_value=created)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.post(
            "/api/v1/library/vendors",
            json={"name": "Acme"},
        )

        # Assert
        assert r.status_code == 201
        assert r.json()["data"]["slug"] == "acme"


class TestVendorDelete:
    """Tests for DELETE /api/v1/library/vendors/{id}."""

    async def test_deletes_vendor(self, app: FastAPI, client: AsyncClient):
        """Should return 204 on success."""
        # Arrange
        fake_service = AsyncMock()
        fake_service.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_vendor_service] = lambda: fake_service
        app.dependency_overrides[current_user] = _logged_in_user

        # Act
        r = await client.delete(f"/api/v1/library/vendors/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_vendor_router.py -v`
Expected: ImportError 或 404 errors

- [ ] **Step 3: 實作 vendor_router.py**

```python
# app/modules/library/routers/vendor_router.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    VendorCreate,
    VendorRead,
    VendorStatus,
    VendorUpdate,
)
from app.modules.library.services.vendor_service import VendorService

router = APIRouter()


async def get_vendor_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VendorService:
    return VendorService(VendorRepository(session))


@router.get("", response_model=DataResponse[list[VendorRead]])
async def list_vendors(
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
    status_filter: VendorStatus | None = None,
) -> DataResponse[list[VendorRead]]:
    vendors = await service.list(status=status_filter)
    return DataResponse(data=[VendorRead.model_validate(v) for v in vendors])


@router.get("/{slug}", response_model=DataResponse[VendorRead])
async def get_vendor(
    slug: str,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.get_by_slug(slug)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.post("", response_model=DataResponse[VendorRead], status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorCreate,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.create(body, current_user_id=user.id)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.patch("/{vendor_id}", response_model=DataResponse[VendorRead])
async def update_vendor(
    vendor_id: uuid.UUID,
    body: VendorUpdate,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[VendorRead]:
    vendor = await service.update(vendor_id, body)
    return DataResponse(data=VendorRead.model_validate(vendor))


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: uuid.UUID,
    service: Annotated[VendorService, Depends(get_vendor_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(vendor_id)
```

- [ ] **Step 4: 把 vendor_router 掛進 api/v1**

修改 `app/api/v1/__init__.py`，把它變成：

```python
from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.vendor_router import router as vendor_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
```

- [ ] **Step 5: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_vendor_router.py -v`
Expected: 5 passed

- [ ] **Step 6: 全 unit test + lint**

Run: `uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 7: Commit**

```bash
git add app/modules/library/routers/__init__.py app/modules/library/routers/vendor_router.py app/api/v1/__init__.py tests/unit/modules/library/test_vendor_router.py
git commit -m "feat(library): add Vendor router and wire to api/v1"
```

---

## Task 8: ProductRepository

**Files:**
- Create: `app/modules/library/repositories/product_repository.py`
- Create: `tests/unit/modules/library/test_product_repository.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_product_repository.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)

from app.modules.library.models.product import Product
from app.modules.library.repositories.product_repository import ProductRepository


def _make_product(slug: str = "pan-os", vendor_id: uuid.UUID | None = None) -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id or uuid.uuid4()
    p.name = "PAN-OS"
    p.slug = slug
    p.status = "active"
    return p


class TestProductRepositoryGetByVendorAndSlug:
    """Tests for ProductRepository.get_by_vendor_and_slug()."""

    async def test_returns_product_when_found(self):
        """Should return Product when (vendor_id, slug) matches."""
        # Arrange
        target = _make_product()
        session = make_mock_session_for_single(target)
        repo = ProductRepository(session)

        # Act
        result = await repo.get_by_vendor_and_slug(target.vendor_id, "pan-os")

        # Assert
        assert result is target


class TestProductRepositoryListByVendor:
    """Tests for ProductRepository.list_by_vendor()."""

    async def test_returns_products_for_vendor(self):
        """Should return products belonging to the vendor."""
        # Arrange
        vendor_id = uuid.uuid4()
        products = [_make_product("a", vendor_id), _make_product("b", vendor_id)]
        session = make_mock_session_for_list(products)
        repo = ProductRepository(session)

        # Act
        result = await repo.list_by_vendor(vendor_id)

        # Assert
        assert result == products


class TestProductRepositoryCreate:
    """Tests for ProductRepository.create()."""

    async def test_creates_and_flushes(self):
        """Should add, flush, refresh, and return."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = ProductRepository(session)
        product = _make_product()

        # Act
        result = await repo.create(product)

        # Assert
        session.add.assert_called_once_with(product)
        session.flush.assert_awaited_once()
        assert result is product
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_product_repository.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/repositories/product_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: uuid.UUID) -> Product | None:
        result = await self._session.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def get_by_vendor_and_slug(self, vendor_id: uuid.UUID, slug: str) -> Product | None:
        result = await self._session.execute(
            select(Product).where(Product.vendor_id == vendor_id, Product.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_vendor(self, vendor_id: uuid.UUID) -> list[Product]:
        stmt = select(Product).where(Product.vendor_id == vendor_id).order_by(Product.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, product: Product) -> Product:
        self._session.add(product)
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def update(self, product: Product) -> Product:
        await self._session.flush()
        await self._session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        await self._session.delete(product)
        await self._session.flush()
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_product_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: lint**

Run: `uv run ruff check . && uv run pyright app/modules/library/repositories/product_repository.py`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add app/modules/library/repositories/product_repository.py tests/unit/modules/library/test_product_repository.py
git commit -m "feat(library): add ProductRepository"
```

---

## Task 9: ProductService

**Files:**
- Create: `app/modules/library/services/product_service.py`
- Create: `tests/unit/modules/library/test_product_service.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_product_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.schemas import ProductCreate, ProductUpdate
from app.modules.library.services.product_service import ProductService


def _make_vendor() -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.slug = "acme"
    return v


def _make_product(vendor_id: uuid.UUID, slug: str = "pan-os") -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id
    p.name = "PAN-OS"
    p.slug = slug
    p.status = "active"
    return p


def _make_service(
    *,
    vendor_get_by_slug: Vendor | None = None,
    product_get_by_vendor_slug: Product | None = None,
    product_get_by_id: Product | None = None,
):
    vendor_repo = MagicMock()
    vendor_repo.get_by_slug = AsyncMock(return_value=vendor_get_by_slug)

    product_repo = MagicMock()
    product_repo.get_by_vendor_and_slug = AsyncMock(return_value=product_get_by_vendor_slug)
    product_repo.get_by_id = AsyncMock(return_value=product_get_by_id)
    product_repo.list_by_vendor = AsyncMock(return_value=[])
    product_repo.create = AsyncMock(side_effect=lambda p: p)
    product_repo.update = AsyncMock(side_effect=lambda p: p)
    product_repo.delete = AsyncMock(return_value=None)

    return ProductService(product_repo, vendor_repo), product_repo, vendor_repo


class TestProductServiceCreate:
    """Tests for ProductService.create()."""

    async def test_create_under_vendor_slug(self):
        """Should create product under a vendor identified by slug."""
        # Arrange
        vendor = _make_vendor()
        service, _product_repo, _ = _make_service(vendor_get_by_slug=vendor)
        request = ProductCreate(name="PAN-OS")

        # Act
        result = await service.create(vendor.slug, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.vendor_id == vendor.id
        assert result.slug == "pan-os"

    async def test_create_raises_when_vendor_missing(self):
        """Should raise NotFoundError when vendor slug invalid."""
        # Arrange
        service, _, _ = _make_service(vendor_get_by_slug=None)
        request = ProductCreate(name="PAN-OS")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create("missing", request, current_user_id=uuid.uuid4())

    async def test_create_raises_conflict_when_slug_used_in_vendor(self):
        """Should raise ConflictError if (vendor, slug) already exists."""
        # Arrange
        vendor = _make_vendor()
        existing = _make_product(vendor.id, "pan-os")
        service, _, _ = _make_service(
            vendor_get_by_slug=vendor,
            product_get_by_vendor_slug=existing,
        )
        request = ProductCreate(name="PAN-OS")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(vendor.slug, request, current_user_id=uuid.uuid4())


class TestProductServiceListByVendor:
    """Tests for ProductService.list_by_vendor_slug()."""

    async def test_returns_products_for_vendor(self):
        """Should fetch vendor then products."""
        # Arrange
        vendor = _make_vendor()
        service, product_repo, _ = _make_service(vendor_get_by_slug=vendor)
        product_repo.list_by_vendor = AsyncMock(return_value=[_make_product(vendor.id)])

        # Act
        result = await service.list_by_vendor_slug(vendor.slug)

        # Assert
        assert len(result) == 1


class TestProductServiceUpdate:
    """Tests for ProductService.update()."""

    async def test_update_applies_changes(self):
        """Should apply update fields."""
        # Arrange
        product = _make_product(uuid.uuid4(), "pan-os")
        service, _, _ = _make_service(product_get_by_id=product)
        request = ProductUpdate(name="New Name")

        # Act
        result = await service.update(product.id, request)

        # Assert
        assert result.name == "New Name"


class TestProductServiceDelete:
    """Tests for ProductService.delete()."""

    async def test_deletes_product(self):
        """Should delete via repo."""
        # Arrange
        product = _make_product(uuid.uuid4())
        service, repo, _ = _make_service(product_get_by_id=product)

        # Act
        await service.delete(product.id)

        # Assert
        repo.delete.assert_awaited_once_with(product)
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_product_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/services/product_service.py
import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.common.utils.slug import slugify
from app.modules.library.models.product import Product
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import ProductCreate, ProductUpdate


class ProductService:
    def __init__(
        self,
        product_repo: ProductRepository,
        vendor_repo: VendorRepository,
    ) -> None:
        self._products = product_repo
        self._vendors = vendor_repo

    async def list_by_vendor_slug(self, vendor_slug: str) -> list[Product]:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")
        return await self._products.list_by_vendor(vendor.id)

    async def get_by_vendor_and_slug(self, vendor_slug: str, product_slug: str) -> Product:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")
        product = await self._products.get_by_vendor_and_slug(vendor.id, product_slug)
        if product is None:
            raise NotFoundError(f"product not found: {vendor_slug}/{product_slug}")
        return product

    async def get_by_id(self, product_id: uuid.UUID) -> Product:
        product = await self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"product not found: {product_id}")
        return product

    async def create(
        self,
        vendor_slug: str,
        data: ProductCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> Product:
        vendor = await self._vendors.get_by_slug(vendor_slug)
        if vendor is None:
            raise NotFoundError(f"vendor not found: {vendor_slug}")

        slug = data.slug or slugify(data.name)
        existing = await self._products.get_by_vendor_and_slug(vendor.id, slug)
        if existing is not None:
            raise ConflictError(f"product slug already exists in vendor: {slug}")

        product = Product()
        product.vendor_id = vendor.id
        product.name = data.name
        product.slug = slug
        product.version = data.version
        product.description = data.description
        product.deploy_type = data.deploy_type
        product.category = data.category
        product.doc_url = data.doc_url
        product.status = data.status
        product.created_by = current_user_id
        return await self._products.create(product)

    async def update(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_by_id(product_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(product, field, value)
        return await self._products.update(product)

    async def delete(self, product_id: uuid.UUID) -> None:
        product = await self.get_by_id(product_id)
        await self._products.delete(product)
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_product_service.py -v`
Expected: 6 passed

- [ ] **Step 5: lint**

Run: `uv run ruff check . && uv run pyright app/modules/library/services/`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add app/modules/library/services/product_service.py tests/unit/modules/library/test_product_service.py
git commit -m "feat(library): add ProductService"
```

---

## Task 10: ProductRouter + 掛 api/v1

**Files:**
- Create: `app/modules/library/routers/product_router.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/modules/library/test_product_router.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_product_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.product import Product
from app.modules.library.routers.product_router import get_product_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_product() -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = uuid.uuid4()
    p.name = "PAN-OS"
    p.slug = "pan-os"
    p.version = None
    p.description = None
    p.deploy_type = None
    p.category = "network"
    p.doc_url = None
    p.status = "active"
    p.created_at = datetime.now(UTC)
    p.updated_at = datetime.now(UTC)
    return p


class TestProductListByVendor:
    """Tests for GET /api/v1/library/vendors/{vendor_slug}/products."""

    async def test_returns_products(self, app: FastAPI, client: AsyncClient):
        """Should return list scoped to vendor."""
        # Arrange
        fake = AsyncMock()
        fake.list_by_vendor_slug = AsyncMock(return_value=[_make_product()])
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/vendors/acme/products")

        # Assert
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestProductGet:
    """Tests for GET /api/v1/library/vendors/{vendor_slug}/products/{slug}."""

    async def test_returns_product(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with product body."""
        # Arrange
        fake = AsyncMock()
        fake.get_by_vendor_and_slug = AsyncMock(return_value=_make_product())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/vendors/acme/products/pan-os")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["slug"] == "pan-os"


class TestProductCreate:
    """Tests for POST /api/v1/library/vendors/{vendor_slug}/products."""

    async def test_creates_product(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_product())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            "/api/v1/library/vendors/acme/products",
            json={"name": "PAN-OS"},
        )

        # Assert
        assert r.status_code == 201


class TestProductUpdate:
    """Tests for PATCH /api/v1/library/products/{id}."""

    async def test_updates_product(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        fake = AsyncMock()
        fake.update = AsyncMock(return_value=_make_product())
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/products/{uuid.uuid4()}",
            json={"version": "v2"},
        )

        # Assert
        assert r.status_code == 200


class TestProductDelete:
    """Tests for DELETE /api/v1/library/products/{id}."""

    async def test_deletes_product(self, app: FastAPI, client: AsyncClient):
        """Should return 204."""
        # Arrange
        fake = AsyncMock()
        fake.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_product_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.delete(f"/api/v1/library/products/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_product_router.py -v`
Expected: 404 / ImportError

- [ ] **Step 3: 實作 product_router.py**

```python
# app/modules/library/routers/product_router.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.modules.library.services.product_service import ProductService

router = APIRouter()


async def get_product_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductService:
    return ProductService(ProductRepository(session), VendorRepository(session))


@router.get(
    "/vendors/{vendor_slug}/products",
    response_model=DataResponse[list[ProductRead]],
)
async def list_products(
    vendor_slug: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[ProductRead]]:
    products = await service.list_by_vendor_slug(vendor_slug)
    return DataResponse(data=[ProductRead.model_validate(p) for p in products])


@router.get(
    "/vendors/{vendor_slug}/products/{product_slug}",
    response_model=DataResponse[ProductRead],
)
async def get_product(
    vendor_slug: str,
    product_slug: str,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.get_by_vendor_and_slug(vendor_slug, product_slug)
    return DataResponse(data=ProductRead.model_validate(product))


@router.post(
    "/vendors/{vendor_slug}/products",
    response_model=DataResponse[ProductRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    vendor_slug: str,
    body: ProductCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.create(vendor_slug, body, current_user_id=user.id)
    return DataResponse(data=ProductRead.model_validate(product))


@router.patch(
    "/products/{product_id}",
    response_model=DataResponse[ProductRead],
)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[ProductRead]:
    product = await service.update(product_id, body)
    return DataResponse(data=ProductRead.model_validate(product))


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(product_id)
```

- [ ] **Step 4: 修改 `app/api/v1/__init__.py`**

加入 product_router：

```python
from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.product_router import router as product_router
from app.modules.library.routers.vendor_router import router as vendor_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
router.include_router(product_router, prefix="/library", tags=["library:product"])
```

- [ ] **Step 5: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_product_router.py -v`
Expected: 5 passed

- [ ] **Step 6: 全 unit test + lint**

Run: `uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 7: Commit**

```bash
git add app/modules/library/routers/product_router.py app/api/v1/__init__.py tests/unit/modules/library/test_product_router.py
git commit -m "feat(library): add Product router and wire to api/v1"
```

---

## Task 11: LogTypeRepository

**Files:**
- Create: `app/modules/library/repositories/log_type_repository.py`
- Create: `tests/unit/modules/library/test_log_type_repository.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_log_type_repository.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import (
    make_mock_session_for_list,
    make_mock_session_for_single,
)

from app.modules.library.models.log_type import LogType
from app.modules.library.repositories.log_type_repository import LogTypeRepository


def _make_log_type(slug: str = "traffic", product_id: uuid.UUID | None = None) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id or uuid.uuid4()
    lt.name = "Traffic"
    lt.slug = slug
    lt.format = "csv"
    lt.status = "draft"
    lt.source = "manual"
    return lt


class TestLogTypeRepositoryGetByProductAndSlug:
    """Tests for LogTypeRepository.get_by_product_and_slug()."""

    async def test_returns_log_type_when_found(self):
        """Should return LogType when (product_id, slug) matches."""
        # Arrange
        target = _make_log_type()
        session = make_mock_session_for_single(target)
        repo = LogTypeRepository(session)

        # Act
        result = await repo.get_by_product_and_slug(target.product_id, "traffic")

        # Assert
        assert result is target


class TestLogTypeRepositoryListByProduct:
    """Tests for LogTypeRepository.list_by_product()."""

    async def test_returns_log_types_for_product(self):
        """Should return scoped list."""
        # Arrange
        product_id = uuid.uuid4()
        log_types = [_make_log_type("a", product_id), _make_log_type("b", product_id)]
        session = make_mock_session_for_list(log_types)
        repo = LogTypeRepository(session)

        # Act
        result = await repo.list_by_product(product_id)

        # Assert
        assert result == log_types


class TestLogTypeRepositoryCreate:
    """Tests for LogTypeRepository.create()."""

    async def test_creates_and_returns(self):
        """Should add, flush, refresh, return."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = LogTypeRepository(session)
        log_type = _make_log_type()

        # Act
        result = await repo.create(log_type)

        # Assert
        assert result is log_type
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_log_type_repository.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/repositories/log_type_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.log_type import LogType


class LogTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, log_type_id: uuid.UUID) -> LogType | None:
        result = await self._session.execute(select(LogType).where(LogType.id == log_type_id))
        return result.scalar_one_or_none()

    async def get_by_product_and_slug(
        self, product_id: uuid.UUID, slug: str
    ) -> LogType | None:
        result = await self._session.execute(
            select(LogType).where(LogType.product_id == product_id, LogType.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_product(self, product_id: uuid.UUID) -> list[LogType]:
        stmt = (
            select(LogType)
            .where(LogType.product_id == product_id)
            .order_by(LogType.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, log_type: LogType) -> LogType:
        self._session.add(log_type)
        await self._session.flush()
        await self._session.refresh(log_type)
        return log_type

    async def update(self, log_type: LogType) -> LogType:
        await self._session.flush()
        await self._session.refresh(log_type)
        return log_type

    async def delete(self, log_type: LogType) -> None:
        await self._session.delete(log_type)
        await self._session.flush()
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_log_type_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: lint + Commit**

```bash
uv run ruff check . && uv run pyright app/modules/library/repositories/log_type_repository.py
git add app/modules/library/repositories/log_type_repository.py tests/unit/modules/library/test_log_type_repository.py
git commit -m "feat(library): add LogTypeRepository"
```

---

## Task 12: ParseRuleRepository

**Files:**
- Create: `app/modules/library/repositories/parse_rule_repository.py`
- Create: `tests/unit/modules/library/test_parse_rule_repository.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_parse_rule_repository.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import make_mock_session_for_list, make_mock_session_for_single

from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository


def _make_parse_rule(version: int = 1, log_type_id: uuid.UUID | None = None) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = log_type_id or uuid.uuid4()
    pr.version = version
    pr.vrl_code = ".action = 'allow'"
    pr.engine_version = "0.32"
    pr.status = "draft"
    return pr


class TestParseRuleRepositoryListByLogType:
    """Tests for ParseRuleRepository.list_by_log_type()."""

    async def test_returns_versions_descending(self):
        """Should return all parse rules for log type."""
        # Arrange
        log_type_id = uuid.uuid4()
        rules = [
            _make_parse_rule(2, log_type_id),
            _make_parse_rule(1, log_type_id),
        ]
        session = make_mock_session_for_list(rules)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.list_by_log_type(log_type_id)

        # Assert
        assert result == rules


class TestParseRuleRepositoryGetMaxVersion:
    """Tests for ParseRuleRepository.get_max_version()."""

    async def test_returns_max_version_when_rules_exist(self):
        """Should return the max version int."""
        # Arrange
        session = make_mock_session_for_single(3)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.get_max_version(uuid.uuid4())

        # Assert
        assert result == 3

    async def test_returns_zero_when_no_rules(self):
        """Should return 0 when no rows."""
        # Arrange
        session = make_mock_session_for_single(None)
        repo = ParseRuleRepository(session)

        # Act
        result = await repo.get_max_version(uuid.uuid4())

        # Assert
        assert result == 0


class TestParseRuleRepositoryCreate:
    """Tests for ParseRuleRepository.create()."""

    async def test_creates_and_returns(self):
        """Should add, flush, refresh."""
        # Arrange
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = ParseRuleRepository(session)
        rule = _make_parse_rule()

        # Act
        result = await repo.create(rule)

        # Assert
        assert result is rule
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_repository.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/repositories/parse_rule_repository.py
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.parse_rule import ParseRule


class ParseRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, rule_id: uuid.UUID) -> ParseRule | None:
        result = await self._session.execute(select(ParseRule).where(ParseRule.id == rule_id))
        return result.scalar_one_or_none()

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[ParseRule]:
        stmt = (
            select(ParseRule)
            .where(ParseRule.log_type_id == log_type_id)
            .order_by(ParseRule.version.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_max_version(self, log_type_id: uuid.UUID) -> int:
        stmt = select(func.max(ParseRule.version)).where(ParseRule.log_type_id == log_type_id)
        result = await self._session.execute(stmt)
        max_version = result.scalar_one_or_none()
        return max_version or 0

    async def create(self, rule: ParseRule) -> ParseRule:
        self._session.add(rule)
        await self._session.flush()
        await self._session.refresh(rule)
        return rule

    async def update(self, rule: ParseRule) -> ParseRule:
        await self._session.flush()
        await self._session.refresh(rule)
        return rule
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_repository.py -v`
Expected: 4 passed

- [ ] **Step 5: lint + Commit**

```bash
uv run ruff check . && uv run pyright app/modules/library/repositories/parse_rule_repository.py
git add app/modules/library/repositories/parse_rule_repository.py tests/unit/modules/library/test_parse_rule_repository.py
git commit -m "feat(library): add ParseRuleRepository with version-aware queries"
```

---

## Task 13: LogTypeService（含 publish flow）

LogTypeService 負責 LogType 本身的 CRUD，**以及 publish flow**（會同時改 LogType 與 ParseRule）。

**Files:**
- Create: `app/modules/library/services/log_type_service.py`
- Create: `tests/unit/modules/library/test_log_type_service.py`

- [ ] **Step 1: 寫測試（重點：publish flow 三條路徑）**

```python
# tests/unit/modules/library/test_log_type_service.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.models.product import Product
from app.modules.library.schemas import LogTypeCreate, LogTypeUpdate
from app.modules.library.services.log_type_service import LogTypeService


def _make_product() -> Product:
    p = Product()
    p.id = uuid.uuid4()
    return p


def _make_log_type(
    *,
    product_id: uuid.UUID | None = None,
    current_parse_rule_id: uuid.UUID | None = None,
    status: str = "draft",
) -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id or uuid.uuid4()
    lt.name = "Traffic"
    lt.slug = "traffic"
    lt.format = "csv"
    lt.status = status
    lt.source = "manual"
    lt.current_parse_rule_id = current_parse_rule_id
    return lt


def _make_parse_rule(
    *,
    log_type_id: uuid.UUID,
    status: str = "draft",
    version: int = 1,
) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = log_type_id
    pr.version = version
    pr.status = status
    pr.engine_version = "0.32"
    pr.vrl_code = "."
    return pr


def _make_service(
    *,
    log_type_get_by_id: LogType | None = None,
    log_type_get_by_product_slug: LogType | None = None,
    product_get_by_id: Product | None = None,
    parse_rule_get_by_id: ParseRule | None = None,
):
    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get_by_id)
    log_type_repo.get_by_product_and_slug = AsyncMock(return_value=log_type_get_by_product_slug)
    log_type_repo.list_by_product = AsyncMock(return_value=[])
    log_type_repo.create = AsyncMock(side_effect=lambda lt: lt)
    log_type_repo.update = AsyncMock(side_effect=lambda lt: lt)
    log_type_repo.delete = AsyncMock(return_value=None)

    product_repo = MagicMock()
    product_repo.get_by_id = AsyncMock(return_value=product_get_by_id)

    parse_rule_repo = MagicMock()
    parse_rule_repo.get_by_id = AsyncMock(return_value=parse_rule_get_by_id)
    parse_rule_repo.update = AsyncMock(side_effect=lambda pr: pr)

    return (
        LogTypeService(log_type_repo, product_repo, parse_rule_repo),
        log_type_repo,
        product_repo,
        parse_rule_repo,
    )


class TestLogTypeServiceCreate:
    """Tests for LogTypeService.create()."""

    async def test_create_under_existing_product(self):
        """Should attach to existing product."""
        # Arrange
        product = _make_product()
        service, _, _, _ = _make_service(product_get_by_id=product)
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act
        result = await service.create(product.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.product_id == product.id
        assert result.slug == "traffic"

    async def test_create_raises_when_product_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _, _ = _make_service(product_get_by_id=None)
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create(uuid.uuid4(), request, current_user_id=uuid.uuid4())

    async def test_create_raises_conflict_on_slug_collision(self):
        """Should raise ConflictError when product+slug already exists."""
        # Arrange
        product = _make_product()
        existing = _make_log_type(product_id=product.id)
        service, _, _, _ = _make_service(
            product_get_by_id=product,
            log_type_get_by_product_slug=existing,
        )
        request = LogTypeCreate(name="Traffic", format="csv")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(product.id, request, current_user_id=uuid.uuid4())


class TestLogTypeServicePublish:
    """Tests for LogTypeService.publish()."""

    async def test_publish_promotes_draft_rule(self):
        """Should promote current draft parse rule to published."""
        # Arrange
        log_type = _make_log_type()
        rule = _make_parse_rule(log_type_id=log_type.id, status="draft")
        log_type.current_parse_rule_id = rule.id
        service, log_type_repo, _, parse_rule_repo = _make_service(
            log_type_get_by_id=log_type,
            parse_rule_get_by_id=rule,
        )

        # Act
        result = await service.publish(log_type.id)

        # Assert
        assert result.status == "published"
        assert rule.status == "published"
        assert result.published_at is not None
        log_type_repo.update.assert_awaited_once()
        parse_rule_repo.update.assert_awaited_once()

    async def test_publish_raises_validation_when_no_current_rule(self):
        """Should raise ValidationError when log type has no current parse rule."""
        # Arrange
        log_type = _make_log_type(current_parse_rule_id=None)
        service, _, _, _ = _make_service(log_type_get_by_id=log_type)

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.publish(log_type.id)

    async def test_publish_raises_conflict_when_already_published(self):
        """Should raise ConflictError when current rule is already published."""
        # Arrange
        log_type = _make_log_type()
        rule = _make_parse_rule(log_type_id=log_type.id, status="published")
        log_type.current_parse_rule_id = rule.id
        service, _, _, _ = _make_service(
            log_type_get_by_id=log_type,
            parse_rule_get_by_id=rule,
        )

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.publish(log_type.id)


class TestLogTypeServiceUpdate:
    """Tests for LogTypeService.update()."""

    async def test_update_applies_changes(self):
        """Should apply provided fields."""
        # Arrange
        log_type = _make_log_type()
        service, _, _, _ = _make_service(log_type_get_by_id=log_type)
        request = LogTypeUpdate(name="New Name")

        # Act
        result = await service.update(log_type.id, request)

        # Assert
        assert result.name == "New Name"


class TestLogTypeServiceDelete:
    """Tests for LogTypeService.delete()."""

    async def test_deletes_log_type(self):
        """Should call repo.delete."""
        # Arrange
        log_type = _make_log_type()
        service, repo, _, _ = _make_service(log_type_get_by_id=log_type)

        # Act
        await service.delete(log_type.id)

        # Assert
        repo.delete.assert_awaited_once_with(log_type)
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_log_type_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/services/log_type_service.py
import uuid
from datetime import UTC, datetime

from app.common.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.common.utils.slug import slugify
from app.modules.library.models.log_type import LogType
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.schemas import LogTypeCreate, LogTypeUpdate


class LogTypeService:
    def __init__(
        self,
        log_type_repo: LogTypeRepository,
        product_repo: ProductRepository,
        parse_rule_repo: ParseRuleRepository,
    ) -> None:
        self._log_types = log_type_repo
        self._products = product_repo
        self._parse_rules = parse_rule_repo

    async def list_by_product(self, product_id: uuid.UUID) -> list[LogType]:
        return await self._log_types.list_by_product(product_id)

    async def get_by_id(self, log_type_id: uuid.UUID) -> LogType:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return log_type

    async def create(
        self,
        product_id: uuid.UUID,
        data: LogTypeCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> LogType:
        product = await self._products.get_by_id(product_id)
        if product is None:
            raise NotFoundError(f"product not found: {product_id}")

        slug = data.slug or slugify(data.name)
        existing = await self._log_types.get_by_product_and_slug(product_id, slug)
        if existing is not None:
            raise ConflictError(f"log type slug already exists in product: {slug}")

        log_type = LogType()
        log_type.product_id = product_id
        log_type.name = data.name
        log_type.slug = slug
        log_type.format = data.format
        log_type.transport = data.transport
        log_type.description = data.description
        log_type.status = "draft"
        log_type.source = "manual"
        log_type.created_by = current_user_id
        return await self._log_types.create(log_type)

    async def update(self, log_type_id: uuid.UUID, data: LogTypeUpdate) -> LogType:
        log_type = await self.get_by_id(log_type_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(log_type, field, value)
        return await self._log_types.update(log_type)

    async def delete(self, log_type_id: uuid.UUID) -> None:
        log_type = await self.get_by_id(log_type_id)
        await self._log_types.delete(log_type)

    async def publish(self, log_type_id: uuid.UUID) -> LogType:
        """Publish flow: promote current draft parse rule to published.

        Raises:
            NotFoundError: log type not found
            ValidationError: no current parse rule to publish
            ConflictError: current parse rule already published
        """
        log_type = await self.get_by_id(log_type_id)
        if log_type.current_parse_rule_id is None:
            raise ValidationError("no parse rule to publish")

        rule = await self._parse_rules.get_by_id(log_type.current_parse_rule_id)
        if rule is None:
            raise ValidationError("no parse rule to publish")
        if rule.status == "published":
            raise ConflictError("already published")

        rule.status = "published"
        await self._parse_rules.update(rule)

        log_type.status = "published"
        log_type.published_at = datetime.now(UTC)
        return await self._log_types.update(log_type)
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_log_type_service.py -v`
Expected: 8 passed

- [ ] **Step 5: lint + Commit**

```bash
uv run ruff check . && uv run pyright app/modules/library/services/log_type_service.py
git add app/modules/library/services/log_type_service.py tests/unit/modules/library/test_log_type_service.py
git commit -m "feat(library): add LogTypeService with publish flow"
```

---

## Task 14: ParseRuleService

ParseRuleService 負責建新 draft（同時更新 LogType.current_parse_rule_id）與 PATCH 既有 draft。

**Files:**
- Create: `app/modules/library/services/parse_rule_service.py`
- Create: `tests/unit/modules/library/test_parse_rule_service.py`

- [ ] **Step 1: 寫測試**

```python
# tests/unit/modules/library/test_parse_rule_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.schemas import ParseRuleCreate, ParseRuleUpdate
from app.modules.library.services.parse_rule_service import ParseRuleService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.status = "draft"
    return lt


def _make_rule(*, status: str = "draft", version: int = 1) -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = uuid.uuid4()
    pr.version = version
    pr.vrl_code = "."
    pr.engine_version = "0.32"
    pr.status = status
    return pr


def _make_service(
    *,
    log_type_get_by_id: LogType | None = None,
    rule_get_by_id: ParseRule | None = None,
    max_version: int = 0,
):
    parse_rule_repo = MagicMock()
    parse_rule_repo.get_by_id = AsyncMock(return_value=rule_get_by_id)
    parse_rule_repo.get_max_version = AsyncMock(return_value=max_version)
    parse_rule_repo.list_by_log_type = AsyncMock(return_value=[])
    parse_rule_repo.create = AsyncMock(side_effect=lambda r: r)
    parse_rule_repo.update = AsyncMock(side_effect=lambda r: r)

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get_by_id)
    log_type_repo.update = AsyncMock(side_effect=lambda lt: lt)

    return (
        ParseRuleService(parse_rule_repo, log_type_repo),
        parse_rule_repo,
        log_type_repo,
    )


class TestParseRuleServiceCreateDraft:
    """Tests for ParseRuleService.create_draft()."""

    async def test_create_first_version(self):
        """Should create version 1 when no existing rules."""
        # Arrange
        log_type = _make_log_type()
        service, _, log_type_repo = _make_service(
            log_type_get_by_id=log_type,
            max_version=0,
        )
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act
        result = await service.create_draft(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.version == 1
        assert result.status == "draft"
        # log_type 應被更新 current_parse_rule_id 與 status
        log_type_repo.update.assert_awaited_once()
        assert log_type.current_parse_rule_id == result.id
        assert log_type.status == "draft"

    async def test_create_increments_version(self):
        """Should set version = max + 1."""
        # Arrange
        log_type = _make_log_type()
        service, _, _ = _make_service(
            log_type_get_by_id=log_type,
            max_version=2,
        )
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act
        result = await service.create_draft(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.version == 3

    async def test_create_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get_by_id=None)
        request = ParseRuleCreate(vrl_code=".", engine_version="0.32")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create_draft(uuid.uuid4(), request, current_user_id=uuid.uuid4())


class TestParseRuleServiceUpdate:
    """Tests for ParseRuleService.update()."""

    async def test_update_applies_changes_to_draft(self):
        """Should update vrl_code on draft rule."""
        # Arrange
        rule = _make_rule(status="draft")
        service, _, _ = _make_service(rule_get_by_id=rule)
        request = ParseRuleUpdate(vrl_code="new code")

        # Act
        result = await service.update(rule.id, request)

        # Assert
        assert result.vrl_code == "new code"

    async def test_update_raises_conflict_on_published_rule(self):
        """Should raise ConflictError when rule is published (immutable)."""
        # Arrange
        rule = _make_rule(status="published")
        service, _, _ = _make_service(rule_get_by_id=rule)
        request = ParseRuleUpdate(vrl_code="new code")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.update(rule.id, request)

    async def test_update_raises_not_found(self):
        """Should raise NotFoundError when rule missing."""
        # Arrange
        service, _, _ = _make_service(rule_get_by_id=None)
        request = ParseRuleUpdate(vrl_code="new")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update(uuid.uuid4(), request)
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作**

```python
# app/modules/library/services/parse_rule_service.py
import uuid

from app.common.exceptions import ConflictError, NotFoundError
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.parse_rule_repository import ParseRuleRepository
from app.modules.library.schemas import ParseRuleCreate, ParseRuleUpdate


class ParseRuleService:
    def __init__(
        self,
        parse_rule_repo: ParseRuleRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._rules = parse_rule_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[ParseRule]:
        return await self._rules.list_by_log_type(log_type_id)

    async def get_by_id(self, rule_id: uuid.UUID) -> ParseRule:
        rule = await self._rules.get_by_id(rule_id)
        if rule is None:
            raise NotFoundError(f"parse rule not found: {rule_id}")
        return rule

    async def create_draft(
        self,
        log_type_id: uuid.UUID,
        data: ParseRuleCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> ParseRule:
        """Create a new draft parse rule version and point log_type.current at it.

        Atomic when called within a single AsyncSession transaction (caller's
        session manages commit boundary).
        """
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        max_version = await self._rules.get_max_version(log_type_id)
        rule = ParseRule()
        rule.log_type_id = log_type_id
        rule.version = max_version + 1
        rule.vrl_code = data.vrl_code
        rule.engine_version = data.engine_version
        rule.notes = data.notes
        rule.status = "draft"
        rule.created_by = current_user_id
        rule = await self._rules.create(rule)

        # Point current to the new draft, mark log_type back to draft
        log_type.current_parse_rule_id = rule.id
        log_type.status = "draft"
        await self._log_types.update(log_type)

        return rule

    async def update(self, rule_id: uuid.UUID, data: ParseRuleUpdate) -> ParseRule:
        rule = await self.get_by_id(rule_id)
        if rule.status == "published":
            raise ConflictError("cannot edit published parse rule")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(rule, field, value)
        return await self._rules.update(rule)
```

- [ ] **Step 4: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_parse_rule_service.py -v`
Expected: 6 passed

- [ ] **Step 5: lint + Commit**

```bash
uv run ruff check . && uv run pyright app/modules/library/services/parse_rule_service.py
git add app/modules/library/services/parse_rule_service.py tests/unit/modules/library/test_parse_rule_service.py
git commit -m "feat(library): add ParseRuleService for draft creation and editing"
```

---

## Task 15: LogTypeRouter + ParseRuleRouter + 掛 api/v1

**Files:**
- Create: `app/modules/library/routers/log_type_router.py`
- Create: `app/modules/library/routers/parse_rule_router.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/modules/library/test_log_type_router.py`
- Create: `tests/unit/modules/library/test_parse_rule_router.py`

- [ ] **Step 1: 寫 log_type_router test（最低限度）**

```python
# tests/unit/modules/library/test_log_type_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.log_type import LogType
from app.modules.library.routers.log_type_router import get_log_type_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = uuid.uuid4()
    lt.name = "Traffic"
    lt.slug = "traffic"
    lt.format = "csv"
    lt.transport = None
    lt.status = "draft"
    lt.source = "manual"
    lt.current_parse_rule_id = None
    lt.description = None
    lt.published_at = None
    lt.created_at = datetime.now(UTC)
    lt.updated_at = datetime.now(UTC)
    return lt


class TestLogTypeListByProduct:
    """Tests for GET /api/v1/library/products/{product_id}/log_types."""

    async def test_returns_log_types(self, app: FastAPI, client: AsyncClient):
        """Should return scoped list."""
        # Arrange
        fake = AsyncMock()
        fake.list_by_product = AsyncMock(return_value=[_make_log_type()])
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get(f"/api/v1/library/products/{uuid.uuid4()}/log_types")

        # Assert
        assert r.status_code == 200


class TestLogTypeCreate:
    """Tests for POST /api/v1/library/products/{product_id}/log_types."""

    async def test_creates(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_log_type())
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/products/{uuid.uuid4()}/log_types",
            json={"name": "Traffic", "format": "csv"},
        )

        # Assert
        assert r.status_code == 201


class TestLogTypePublish:
    """Tests for POST /api/v1/library/log_types/{id}/publish."""

    async def test_publishes(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        published = _make_log_type()
        published.status = "published"
        published.published_at = datetime.now(UTC)
        fake = AsyncMock()
        fake.publish = AsyncMock(return_value=published)
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(f"/api/v1/library/log_types/{uuid.uuid4()}/publish")

        # Assert
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "published"

    async def test_returns_409_on_already_published(self, app: FastAPI, client: AsyncClient):
        """Should map ConflictError to 409."""
        # Arrange
        from app.common.exceptions import ConflictError

        fake = AsyncMock()
        fake.publish = AsyncMock(side_effect=ConflictError("already published"))
        app.dependency_overrides[get_log_type_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(f"/api/v1/library/log_types/{uuid.uuid4()}/publish")

        # Assert
        assert r.status_code == 409
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_log_type_router.py -v`
Expected: 404 / ImportError

- [ ] **Step 3: 實作 log_type_router.py**

```python
# app/modules/library/routers/log_type_router.py
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
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.schemas import (
    LogTypeCreate,
    LogTypeRead,
    LogTypeUpdate,
)
from app.modules.library.services.log_type_service import LogTypeService

router = APIRouter()


async def get_log_type_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogTypeService:
    return LogTypeService(
        LogTypeRepository(session),
        ProductRepository(session),
        ParseRuleRepository(session),
    )


@router.get(
    "/products/{product_id}/log_types",
    response_model=DataResponse[list[LogTypeRead]],
)
async def list_log_types(
    product_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[LogTypeRead]]:
    log_types = await service.list_by_product(product_id)
    return DataResponse(data=[LogTypeRead.model_validate(lt) for lt in log_types])


@router.get(
    "/log_types/{log_type_id}",
    response_model=DataResponse[LogTypeRead],
)
async def get_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.get_by_id(log_type_id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.post(
    "/products/{product_id}/log_types",
    response_model=DataResponse[LogTypeRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_log_type(
    product_id: uuid.UUID,
    body: LogTypeCreate,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.create(product_id, body, current_user_id=user.id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.patch(
    "/log_types/{log_type_id}",
    response_model=DataResponse[LogTypeRead],
)
async def update_log_type(
    log_type_id: uuid.UUID,
    body: LogTypeUpdate,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.update(log_type_id, body)
    return DataResponse(data=LogTypeRead.model_validate(log_type))


@router.delete(
    "/log_types/{log_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(log_type_id)


@router.post(
    "/log_types/{log_type_id}/publish",
    response_model=DataResponse[LogTypeRead],
)
async def publish_log_type(
    log_type_id: uuid.UUID,
    service: Annotated[LogTypeService, Depends(get_log_type_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[LogTypeRead]:
    log_type = await service.publish(log_type_id)
    return DataResponse(data=LogTypeRead.model_validate(log_type))
```

- [ ] **Step 4: 寫 parse_rule_router test**

```python
# tests/unit/modules/library/test_parse_rule_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.parse_rule import ParseRule
from app.modules.library.routers.parse_rule_router import get_parse_rule_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_rule() -> ParseRule:
    pr = ParseRule()
    pr.id = uuid.uuid4()
    pr.log_type_id = uuid.uuid4()
    pr.version = 1
    pr.vrl_code = "."
    pr.engine_version = "0.32"
    pr.status = "draft"
    pr.notes = None
    pr.created_at = datetime.now(UTC)
    pr.updated_at = datetime.now(UTC)
    return pr


class TestParseRuleCreate:
    """Tests for POST /api/v1/library/log_types/{id}/parse_rules."""

    async def test_creates_draft(self, app: FastAPI, client: AsyncClient):
        """Should return 201 with new draft."""
        # Arrange
        fake = AsyncMock()
        fake.create_draft = AsyncMock(return_value=_make_rule())
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/log_types/{uuid.uuid4()}/parse_rules",
            json={"vrl_code": ".", "engine_version": "0.32"},
        )

        # Assert
        assert r.status_code == 201


class TestParseRuleUpdate:
    """Tests for PATCH /api/v1/library/parse_rules/{id}."""

    async def test_updates_draft(self, app: FastAPI, client: AsyncClient):
        """Should return 200."""
        # Arrange
        fake = AsyncMock()
        fake.update = AsyncMock(return_value=_make_rule())
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/parse_rules/{uuid.uuid4()}",
            json={"vrl_code": "new"},
        )

        # Assert
        assert r.status_code == 200

    async def test_returns_409_on_published(self, app: FastAPI, client: AsyncClient):
        """Should map ConflictError to 409."""
        # Arrange
        from app.common.exceptions import ConflictError

        fake = AsyncMock()
        fake.update = AsyncMock(side_effect=ConflictError("immutable"))
        app.dependency_overrides[get_parse_rule_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.patch(
            f"/api/v1/library/parse_rules/{uuid.uuid4()}",
            json={"vrl_code": "new"},
        )

        # Assert
        assert r.status_code == 409
```

- [ ] **Step 5: 實作 parse_rule_router.py**

```python
# app/modules/library/routers/parse_rule_router.py
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
```

- [ ] **Step 6: 修改 `app/api/v1/__init__.py`**

加 log_type_router 與 parse_rule_router：

```python
from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.log_type_router import router as log_type_router
from app.modules.library.routers.parse_rule_router import router as parse_rule_router
from app.modules.library.routers.product_router import router as product_router
from app.modules.library.routers.vendor_router import router as vendor_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
router.include_router(product_router, prefix="/library", tags=["library:product"])
router.include_router(log_type_router, prefix="/library", tags=["library:log_type"])
router.include_router(parse_rule_router, prefix="/library", tags=["library:parse_rule"])
```

- [ ] **Step 7: Run 預期通過**

Run: `uv run pytest tests/unit/modules/library/test_log_type_router.py tests/unit/modules/library/test_parse_rule_router.py -v`
Expected: 6 passed

- [ ] **Step 8: 全 unit + lint**

Run: `uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 9: Commit**

```bash
git add app/modules/library/routers/log_type_router.py app/modules/library/routers/parse_rule_router.py app/api/v1/__init__.py tests/unit/modules/library/test_log_type_router.py tests/unit/modules/library/test_parse_rule_router.py
git commit -m "feat(library): add LogType and ParseRule routers and wire to api/v1"
```

---

## Task 16: FieldSchema 全 slice（repo + service + router，bulk replace）

FieldSchema 只有一個對外 endpoint：`PUT /library/log_types/{id}/fields` 整批覆蓋。

**Files:**
- Create: `app/modules/library/repositories/field_schema_repository.py`
- Create: `app/modules/library/services/field_schema_service.py`
- Create: `app/modules/library/routers/field_schema_router.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/modules/library/test_field_schema_service.py`
- Create: `tests/unit/modules/library/test_field_schema_router.py`

- [ ] **Step 1: 寫 service test**

```python
# tests/unit/modules/library/test_field_schema_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import NotFoundError
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.models.log_type import LogType
from app.modules.library.schemas import FieldSchemaBulkReplace, FieldSchemaItem
from app.modules.library.services.field_schema_service import FieldSchemaService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    return lt


def _make_field(name: str = "src_ip") -> FieldSchema:
    f = FieldSchema()
    f.id = uuid.uuid4()
    f.field_name = name
    f.field_type = "string"
    return f


def _make_service(*, log_type_get: LogType | None = None):
    field_repo = MagicMock()
    field_repo.list_by_log_type = AsyncMock(return_value=[])
    field_repo.replace_for_log_type = AsyncMock(side_effect=lambda lt_id, items: [
        _make_field(item.field_name) for item in items
    ])

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get)

    return FieldSchemaService(field_repo, log_type_repo), field_repo, log_type_repo


class TestFieldSchemaServiceReplace:
    """Tests for FieldSchemaService.replace_for_log_type()."""

    async def test_replaces_fields(self):
        """Should call repo.replace_for_log_type with items."""
        # Arrange
        log_type = _make_log_type()
        service, field_repo, _ = _make_service(log_type_get=log_type)
        body = FieldSchemaBulkReplace(
            fields=[
                FieldSchemaItem(field_name="src_ip", field_type="ip", is_identifier=True),
                FieldSchemaItem(field_name="dst_ip", field_type="ip"),
            ]
        )

        # Act
        result = await service.replace_for_log_type(log_type.id, body)

        # Assert
        assert len(result) == 2
        field_repo.replace_for_log_type.assert_awaited_once()

    async def test_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get=None)
        body = FieldSchemaBulkReplace(fields=[])

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.replace_for_log_type(uuid.uuid4(), body)


class TestFieldSchemaServiceList:
    """Tests for FieldSchemaService.list_by_log_type()."""

    async def test_returns_fields(self):
        """Should return repo result."""
        # Arrange
        log_type = _make_log_type()
        service, field_repo, _ = _make_service(log_type_get=log_type)
        field_repo.list_by_log_type = AsyncMock(return_value=[_make_field("a"), _make_field("b")])

        # Act
        result = await service.list_by_log_type(log_type.id)

        # Assert
        assert len(result) == 2
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_field_schema_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作 repository**

```python
# app/modules/library/repositories/field_schema_repository.py
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.field_schema import FieldSchema


class FieldSchemaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[FieldSchema]:
        stmt = (
            select(FieldSchema)
            .where(FieldSchema.log_type_id == log_type_id)
            .order_by(FieldSchema.sort_order, FieldSchema.field_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def replace_for_log_type(
        self,
        log_type_id: uuid.UUID,
        items: list[FieldSchema],
    ) -> list[FieldSchema]:
        """Atomically delete existing fields for log_type then insert new ones.

        Caller is responsible for ensuring all `items` have `log_type_id` set.
        Operation runs within the caller's session transaction.
        """
        await self._session.execute(
            delete(FieldSchema).where(FieldSchema.log_type_id == log_type_id)
        )
        for item in items:
            self._session.add(item)
        await self._session.flush()
        for item in items:
            await self._session.refresh(item)
        return items
```

- [ ] **Step 4: 實作 service**

```python
# app/modules/library/services/field_schema_service.py
import uuid

from app.common.exceptions import NotFoundError
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import FieldSchemaBulkReplace


class FieldSchemaService:
    def __init__(
        self,
        field_repo: FieldSchemaRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._fields = field_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[FieldSchema]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return await self._fields.list_by_log_type(log_type_id)

    async def replace_for_log_type(
        self,
        log_type_id: uuid.UUID,
        data: FieldSchemaBulkReplace,
    ) -> list[FieldSchema]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        items: list[FieldSchema] = []
        for fi in data.fields:
            f = FieldSchema()
            f.log_type_id = log_type_id
            f.field_name = fi.field_name
            f.field_type = fi.field_type
            f.description = fi.description
            f.is_required = fi.is_required
            f.is_identifier = fi.is_identifier
            f.example_value = fi.example_value
            f.sort_order = fi.sort_order
            items.append(f)

        return await self._fields.replace_for_log_type(log_type_id, items)
```

- [ ] **Step 5: 寫 router test**

```python
# tests/unit/modules/library/test_field_schema_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.field_schema import FieldSchema
from app.modules.library.routers.field_schema_router import get_field_schema_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_field(name: str = "src_ip") -> FieldSchema:
    f = FieldSchema()
    f.id = uuid.uuid4()
    f.log_type_id = uuid.uuid4()
    f.field_name = name
    f.field_type = "ip"
    f.description = None
    f.is_required = False
    f.is_identifier = True
    f.example_value = None
    f.sort_order = 0
    return f


class TestFieldSchemaPut:
    """Tests for PUT /api/v1/library/log_types/{id}/fields."""

    async def test_replaces_fields(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with new fields."""
        # Arrange
        fake = AsyncMock()
        fake.replace_for_log_type = AsyncMock(return_value=[_make_field("src_ip")])
        app.dependency_overrides[get_field_schema_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.put(
            f"/api/v1/library/log_types/{uuid.uuid4()}/fields",
            json={"fields": [{"field_name": "src_ip", "field_type": "ip", "is_identifier": True}]},
        )

        # Assert
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
```

- [ ] **Step 6: 實作 router**

```python
# app/modules/library/routers/field_schema_router.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.field_schema_repository import (
    FieldSchemaRepository,
)
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.schemas import (
    FieldSchemaBulkReplace,
    FieldSchemaRead,
)
from app.modules.library.services.field_schema_service import FieldSchemaService

router = APIRouter()


async def get_field_schema_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FieldSchemaService:
    return FieldSchemaService(
        FieldSchemaRepository(session),
        LogTypeRepository(session),
    )


@router.put(
    "/log_types/{log_type_id}/fields",
    response_model=DataResponse[list[FieldSchemaRead]],
)
async def replace_log_type_fields(
    log_type_id: uuid.UUID,
    body: FieldSchemaBulkReplace,
    service: Annotated[FieldSchemaService, Depends(get_field_schema_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[FieldSchemaRead]]:
    fields = await service.replace_for_log_type(log_type_id, body)
    return DataResponse(data=[FieldSchemaRead.model_validate(f) for f in fields])
```

- [ ] **Step 7: 修改 `app/api/v1/__init__.py`** — 加 field_schema_router

```python
from app.modules.library.routers.field_schema_router import router as field_schema_router

# 在 router include 區塊加：
router.include_router(field_schema_router, prefix="/library", tags=["library:field"])
```

- [ ] **Step 8: 全 unit test + lint**

Run: `uv run pytest tests/unit/modules/library/test_field_schema_service.py tests/unit/modules/library/test_field_schema_router.py -v`
Expected: 4 passed

`uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 9: Commit**

```bash
git add app/modules/library/repositories/field_schema_repository.py app/modules/library/services/field_schema_service.py app/modules/library/routers/field_schema_router.py app/api/v1/__init__.py tests/unit/modules/library/test_field_schema_service.py tests/unit/modules/library/test_field_schema_router.py
git commit -m "feat(library): add FieldSchema bulk replace endpoint"
```

---

## Task 17: SampleLog 全 slice

**Files:**
- Create: `app/modules/library/repositories/sample_log_repository.py`
- Create: `app/modules/library/services/sample_log_service.py`
- Create: `app/modules/library/routers/sample_log_router.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/modules/library/test_sample_log_service.py`
- Create: `tests/unit/modules/library/test_sample_log_router.py`

- [ ] **Step 1: 實作 repository**

```python
# app/modules/library/repositories/sample_log_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.library.models.sample_log import SampleLog


class SampleLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, sample_id: uuid.UUID) -> SampleLog | None:
        result = await self._session.execute(
            select(SampleLog).where(SampleLog.id == sample_id)
        )
        return result.scalar_one_or_none()

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[SampleLog]:
        stmt = (
            select(SampleLog)
            .where(SampleLog.log_type_id == log_type_id)
            .order_by(SampleLog.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, sample: SampleLog) -> SampleLog:
        self._session.add(sample)
        await self._session.flush()
        await self._session.refresh(sample)
        return sample

    async def delete(self, sample: SampleLog) -> None:
        await self._session.delete(sample)
        await self._session.flush()
```

- [ ] **Step 2: 寫 service test**

```python
# tests/unit/modules/library/test_sample_log_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import NotFoundError
from app.modules.library.models.log_type import LogType
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.schemas import SampleLogCreate
from app.modules.library.services.sample_log_service import SampleLogService


def _make_log_type() -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    return lt


def _make_sample() -> SampleLog:
    s = SampleLog()
    s.id = uuid.uuid4()
    s.log_type_id = uuid.uuid4()
    s.raw_log = "1,2,3"
    s.label = "normal"
    return s


def _make_service(
    *,
    log_type_get: LogType | None = None,
    sample_get: SampleLog | None = None,
):
    sample_repo = MagicMock()
    sample_repo.get_by_id = AsyncMock(return_value=sample_get)
    sample_repo.list_by_log_type = AsyncMock(return_value=[])
    sample_repo.create = AsyncMock(side_effect=lambda s: s)
    sample_repo.delete = AsyncMock(return_value=None)

    log_type_repo = MagicMock()
    log_type_repo.get_by_id = AsyncMock(return_value=log_type_get)

    return SampleLogService(sample_repo, log_type_repo), sample_repo, log_type_repo


class TestSampleLogServiceCreate:
    """Tests for SampleLogService.create()."""

    async def test_creates(self):
        """Should attach to log_type and create."""
        # Arrange
        log_type = _make_log_type()
        service, _, _ = _make_service(log_type_get=log_type)
        request = SampleLogCreate(raw_log="1,2,3")

        # Act
        result = await service.create(log_type.id, request, current_user_id=uuid.uuid4())

        # Assert
        assert result.log_type_id == log_type.id
        assert result.raw_log == "1,2,3"

    async def test_raises_not_found_when_log_type_missing(self):
        """Should raise NotFoundError."""
        # Arrange
        service, _, _ = _make_service(log_type_get=None)
        request = SampleLogCreate(raw_log="x")

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.create(uuid.uuid4(), request, current_user_id=uuid.uuid4())


class TestSampleLogServiceDelete:
    """Tests for SampleLogService.delete()."""

    async def test_deletes(self):
        """Should fetch and delete."""
        # Arrange
        sample = _make_sample()
        service, repo, _ = _make_service(sample_get=sample)

        # Act
        await service.delete(sample.id)

        # Assert
        repo.delete.assert_awaited_once_with(sample)

    async def test_raises_not_found(self):
        """Should raise NotFoundError when missing."""
        # Arrange
        service, _, _ = _make_service(sample_get=None)

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4())
```

- [ ] **Step 3: 實作 service**

```python
# app/modules/library/services/sample_log_service.py
import uuid

from app.common.exceptions import NotFoundError
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.schemas import SampleLogCreate


class SampleLogService:
    def __init__(
        self,
        sample_repo: SampleLogRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._samples = sample_repo
        self._log_types = log_type_repo

    async def list_by_log_type(self, log_type_id: uuid.UUID) -> list[SampleLog]:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")
        return await self._samples.list_by_log_type(log_type_id)

    async def create(
        self,
        log_type_id: uuid.UUID,
        data: SampleLogCreate,
        *,
        current_user_id: uuid.UUID,
    ) -> SampleLog:
        log_type = await self._log_types.get_by_id(log_type_id)
        if log_type is None:
            raise NotFoundError(f"log type not found: {log_type_id}")

        sample = SampleLog()
        sample.log_type_id = log_type_id
        sample.raw_log = data.raw_log
        sample.label = data.label
        sample.description = data.description
        sample.added_by = current_user_id
        return await self._samples.create(sample)

    async def delete(self, sample_id: uuid.UUID) -> None:
        sample = await self._samples.get_by_id(sample_id)
        if sample is None:
            raise NotFoundError(f"sample not found: {sample_id}")
        await self._samples.delete(sample)
```

- [ ] **Step 4: 寫 router test**

```python
# tests/unit/modules/library/test_sample_log_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.models.sample_log import SampleLog
from app.modules.library.routers.sample_log_router import get_sample_log_service


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


def _make_sample() -> SampleLog:
    s = SampleLog()
    s.id = uuid.uuid4()
    s.log_type_id = uuid.uuid4()
    s.raw_log = "1,2,3"
    s.label = "normal"
    s.description = None
    s.created_at = datetime.now(UTC)
    return s


class TestSampleCreate:
    """Tests for POST /api/v1/library/log_types/{id}/samples."""

    async def test_creates_sample(self, app: FastAPI, client: AsyncClient):
        """Should return 201."""
        # Arrange
        fake = AsyncMock()
        fake.create = AsyncMock(return_value=_make_sample())
        app.dependency_overrides[get_sample_log_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.post(
            f"/api/v1/library/log_types/{uuid.uuid4()}/samples",
            json={"raw_log": "1,2,3"},
        )

        # Assert
        assert r.status_code == 201


class TestSampleDelete:
    """Tests for DELETE /api/v1/library/samples/{id}."""

    async def test_deletes(self, app: FastAPI, client: AsyncClient):
        """Should return 204."""
        # Arrange
        fake = AsyncMock()
        fake.delete = AsyncMock(return_value=None)
        app.dependency_overrides[get_sample_log_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.delete(f"/api/v1/library/samples/{uuid.uuid4()}")

        # Assert
        assert r.status_code == 204
```

- [ ] **Step 5: 實作 router**

```python
# app/modules/library/routers/sample_log_router.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.sample_log_repository import SampleLogRepository
from app.modules.library.schemas import SampleLogCreate, SampleLogRead
from app.modules.library.services.sample_log_service import SampleLogService

router = APIRouter()


async def get_sample_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SampleLogService:
    return SampleLogService(
        SampleLogRepository(session),
        LogTypeRepository(session),
    )


@router.get(
    "/log_types/{log_type_id}/samples",
    response_model=DataResponse[list[SampleLogRead]],
)
async def list_samples(
    log_type_id: uuid.UUID,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    _user: Annotated[User, Depends(current_user)],
) -> DataResponse[list[SampleLogRead]]:
    samples = await service.list_by_log_type(log_type_id)
    return DataResponse(data=[SampleLogRead.model_validate(s) for s in samples])


@router.post(
    "/log_types/{log_type_id}/samples",
    response_model=DataResponse[SampleLogRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_sample(
    log_type_id: uuid.UUID,
    body: SampleLogCreate,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    user: Annotated[User, Depends(current_user)],
) -> DataResponse[SampleLogRead]:
    sample = await service.create(log_type_id, body, current_user_id=user.id)
    return DataResponse(data=SampleLogRead.model_validate(sample))


@router.delete(
    "/samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sample(
    sample_id: uuid.UUID,
    service: Annotated[SampleLogService, Depends(get_sample_log_service)],
    _user: Annotated[User, Depends(current_user)],
) -> None:
    await service.delete(sample_id)
```

- [ ] **Step 6: 修改 `app/api/v1/__init__.py`** — 加 sample_log_router

```python
from app.modules.library.routers.sample_log_router import router as sample_log_router

# 在 router include 區塊加：
router.include_router(sample_log_router, prefix="/library", tags=["library:sample"])
```

- [ ] **Step 7: 全 unit test + lint**

Run: `uv run pytest tests/unit/modules/library/test_sample_log_service.py tests/unit/modules/library/test_sample_log_router.py -v`
Expected: 6 passed

`uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 8: Commit**

```bash
git add app/modules/library/repositories/sample_log_repository.py app/modules/library/services/sample_log_service.py app/modules/library/routers/sample_log_router.py app/api/v1/__init__.py tests/unit/modules/library/test_sample_log_service.py tests/unit/modules/library/test_sample_log_router.py
git commit -m "feat(library): add SampleLog CRUD endpoints"
```

---

## Task 18: Library Overview service + router

聚合 vendor → product → log_type 計數，給 `/library` 列表頁用。

**Files:**
- Create: `app/modules/library/services/library_overview_service.py`
- Create: `app/modules/library/routers/library_overview_router.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/modules/library/test_library_overview_service.py`
- Create: `tests/unit/modules/library/test_library_overview_router.py`

- [ ] **Step 1: 寫 service test**

```python
# tests/unit/modules/library/test_library_overview_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.library.models.log_type import LogType
from app.modules.library.models.product import Product
from app.modules.library.models.vendor import Vendor
from app.modules.library.services.library_overview_service import (
    LibraryOverviewService,
)


def _make_vendor(slug: str = "acme") -> Vendor:
    v = Vendor()
    v.id = uuid.uuid4()
    v.name = "Acme"
    v.slug = slug
    v.logo_url = None
    v.status = "active"
    return v


def _make_product(vendor_id: uuid.UUID, slug: str = "p1", category: str = "network") -> Product:
    p = Product()
    p.id = uuid.uuid4()
    p.vendor_id = vendor_id
    p.name = "P1"
    p.slug = slug
    p.category = category
    p.status = "active"
    return p


def _make_log_type(product_id: uuid.UUID, status: str = "draft") -> LogType:
    lt = LogType()
    lt.id = uuid.uuid4()
    lt.product_id = product_id
    lt.name = "lt"
    lt.slug = "lt"
    lt.status = status
    return lt


def _make_service(*, vendors: list[Vendor], products: dict, log_types: dict):
    """`products` is dict[vendor_id -> list[Product]]; `log_types` is dict[product_id -> list[LogType]]."""
    vendor_repo = MagicMock()
    vendor_repo.list = AsyncMock(return_value=vendors)

    product_repo = MagicMock()
    product_repo.list_by_vendor = AsyncMock(side_effect=lambda vid: products.get(vid, []))

    log_type_repo = MagicMock()
    log_type_repo.list_by_product = AsyncMock(side_effect=lambda pid: log_types.get(pid, []))

    return LibraryOverviewService(vendor_repo, product_repo, log_type_repo)


class TestLibraryOverview:
    """Tests for LibraryOverviewService.overview()."""

    async def test_returns_grouped_with_counts(self):
        """Should return vendor → products with log_type counts."""
        # Arrange
        vendor = _make_vendor()
        product = _make_product(vendor.id)
        log_types = [
            _make_log_type(product.id, "published"),
            _make_log_type(product.id, "published"),
            _make_log_type(product.id, "draft"),
        ]
        service = _make_service(
            vendors=[vendor],
            products={vendor.id: [product]},
            log_types={product.id: log_types},
        )

        # Act
        groups = await service.overview()

        # Assert
        assert len(groups) == 1
        group = groups[0]
        assert group.vendor.slug == "acme"
        assert len(group.products) == 1
        op = group.products[0]
        assert op.log_type_counts.total == 3
        assert op.log_type_counts.published == 2
        assert op.log_type_counts.draft == 1
        assert op.is_empty is False

    async def test_empty_product_marked_is_empty(self):
        """Should set is_empty=True when product has no log types."""
        # Arrange
        vendor = _make_vendor()
        product = _make_product(vendor.id)
        service = _make_service(
            vendors=[vendor],
            products={vendor.id: [product]},
            log_types={},
        )

        # Act
        groups = await service.overview()

        # Assert
        assert groups[0].products[0].is_empty is True
        assert groups[0].products[0].log_type_counts.total == 0

    async def test_filters_by_category(self):
        """Should drop products whose category doesn't match filter."""
        # Arrange
        vendor = _make_vendor()
        p1 = _make_product(vendor.id, "p1", category="network")
        p2 = _make_product(vendor.id, "p2", category="endpoint")
        service = _make_service(
            vendors=[vendor],
            products={vendor.id: [p1, p2]},
            log_types={},
        )

        # Act
        groups = await service.overview(category="network")

        # Assert
        assert len(groups[0].products) == 1
        assert groups[0].products[0].slug == "p1"
```

- [ ] **Step 2: Run，預期失敗**

Run: `uv run pytest tests/unit/modules/library/test_library_overview_service.py -v`
Expected: ImportError

- [ ] **Step 3: 實作 service**

```python
# app/modules/library/services/library_overview_service.py
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    LogTypeCounts,
    OverviewProduct,
    OverviewVendor,
    OverviewVendorGroup,
)


class LibraryOverviewService:
    def __init__(
        self,
        vendor_repo: VendorRepository,
        product_repo: ProductRepository,
        log_type_repo: LogTypeRepository,
    ) -> None:
        self._vendors = vendor_repo
        self._products = product_repo
        self._log_types = log_type_repo

    async def overview(
        self,
        *,
        category: str | None = None,
        log_type_status: str | None = None,
    ) -> list[OverviewVendorGroup]:
        """Aggregate vendor → products → log_type counts.

        Filters:
            category: keep only products with `Product.category == category`
            log_type_status: keep only products that have at least one log_type
                with that status (if status is "未建庫" / "is_empty", caller
                handles via the is_empty flag instead — this filter is for
                published/draft).
        """
        vendors = await self._vendors.list()
        groups: list[OverviewVendorGroup] = []

        for vendor in vendors:
            products = await self._products.list_by_vendor(vendor.id)
            overview_products: list[OverviewProduct] = []

            for product in products:
                if category is not None and product.category != category:
                    continue

                log_types = await self._log_types.list_by_product(product.id)
                published = sum(1 for lt in log_types if lt.status == "published")
                draft = sum(1 for lt in log_types if lt.status == "draft")
                total = len(log_types)

                if log_type_status == "published" and published == 0:
                    continue
                if log_type_status == "draft" and draft == 0:
                    continue

                overview_products.append(
                    OverviewProduct(
                        id=product.id,
                        name=product.name,
                        slug=product.slug,
                        category=product.category,  # type: ignore[arg-type]
                        status=product.status,  # type: ignore[arg-type]
                        log_type_counts=LogTypeCounts(
                            total=total,
                            published=published,
                            draft=draft,
                        ),
                        is_empty=(total == 0),
                    )
                )

            groups.append(
                OverviewVendorGroup(
                    vendor=OverviewVendor(
                        id=vendor.id,
                        name=vendor.name,
                        slug=vendor.slug,
                        logo_url=vendor.logo_url,
                    ),
                    products=overview_products,
                )
            )

        return groups
```

- [ ] **Step 4: 寫 router test**

```python
# tests/unit/modules/library/test_library_overview_router.py
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import AsyncClient

from app.common.auth import current_user
from app.modules.auth.models.user import User
from app.modules.library.routers.library_overview_router import (
    get_library_overview_service,
)
from app.modules.library.schemas import (
    LogTypeCounts,
    OverviewProduct,
    OverviewVendor,
    OverviewVendorGroup,
)


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = "x@y.z"
    u.is_active = True
    u.created_at = datetime.now(UTC)
    u.updated_at = datetime.now(UTC)
    return u


class TestLibraryOverviewRoute:
    """Tests for GET /api/v1/library/overview."""

    async def test_returns_grouped_response(self, app: FastAPI, client: AsyncClient):
        """Should return 200 with vendor groups."""
        # Arrange
        sample = [
            OverviewVendorGroup(
                vendor=OverviewVendor(
                    id=uuid.uuid4(),
                    name="Acme",
                    slug="acme",
                    logo_url=None,
                ),
                products=[
                    OverviewProduct(
                        id=uuid.uuid4(),
                        name="P",
                        slug="p",
                        category="network",
                        status="active",
                        log_type_counts=LogTypeCounts(total=0, published=0, draft=0),
                        is_empty=True,
                    )
                ],
            )
        ]
        fake = AsyncMock()
        fake.overview = AsyncMock(return_value=sample)
        app.dependency_overrides[get_library_overview_service] = lambda: fake
        app.dependency_overrides[current_user] = _user

        # Act
        r = await client.get("/api/v1/library/overview")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["vendor"]["slug"] == "acme"
        assert body["data"][0]["products"][0]["is_empty"] is True
```

- [ ] **Step 5: 實作 router**

```python
# app/modules/library/routers/library_overview_router.py
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import current_user
from app.common.schemas import DataResponse
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.library.repositories.log_type_repository import LogTypeRepository
from app.modules.library.repositories.product_repository import ProductRepository
from app.modules.library.repositories.vendor_repository import VendorRepository
from app.modules.library.schemas import (
    OverviewVendorGroup,
    ProductCategory,
)
from app.modules.library.services.library_overview_service import (
    LibraryOverviewService,
)

router = APIRouter()


async def get_library_overview_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LibraryOverviewService:
    return LibraryOverviewService(
        VendorRepository(session),
        ProductRepository(session),
        LogTypeRepository(session),
    )


@router.get(
    "/overview",
    response_model=DataResponse[list[OverviewVendorGroup]],
)
async def overview(
    service: Annotated[LibraryOverviewService, Depends(get_library_overview_service)],
    _user: Annotated[User, Depends(current_user)],
    category: Annotated[ProductCategory | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> DataResponse[list[OverviewVendorGroup]]:
    groups = await service.overview(category=category, log_type_status=status_filter)
    return DataResponse(data=groups)
```

- [ ] **Step 6: 修改 `app/api/v1/__init__.py`** — 加 library_overview_router

```python
from app.modules.library.routers.library_overview_router import router as library_overview_router

# 在 router include 區塊加（建議放第一個 library router 之前）：
router.include_router(library_overview_router, prefix="/library", tags=["library"])
```

- [ ] **Step 7: 全 unit + lint**

Run: `uv run pytest tests/unit/modules/library/test_library_overview_service.py tests/unit/modules/library/test_library_overview_router.py -v`
Expected: 4 passed

`uv run ruff check . && uv run pyright && uv run pytest tests/unit -v`
Expected: 全綠

- [ ] **Step 8: Commit**

```bash
git add app/modules/library/services/library_overview_service.py app/modules/library/routers/library_overview_router.py app/api/v1/__init__.py tests/unit/modules/library/test_library_overview_service.py tests/unit/modules/library/test_library_overview_router.py
git commit -m "feat(library): add /library/overview aggregated endpoint"
```

---

## Task 19: 全 lint pass + unit test pass + 手動 smoke

- [ ] **Step 1:** `make lint` 全綠（ruff check / format / pyright）

- [ ] **Step 2:** `make test` 全綠

預期 unit test 數應該約是 22（1a 既有）+ ~50（1b 新增）= 72 上下，依 router test 數量略有差異。

若有 lint 殘留：先 `make format` 再檢查，仍無法修的逐項處理（不可隨手 noqa）。

- [ ] **Step 3:** 手動 smoke — 端到端建一條完整 vendor/product/log_type/...

```bash
# 確認 docker compose 起著且 0003 migration 已 apply
docker compose ps
uv run alembic upgrade head

# 啟動 API
make api &
sleep 3
CK=$(mktemp)

# 登入
curl -sS -c "$CK" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@logscope.local","password":"changeme"}'

# 建 vendor
curl -sS -b "$CK" -X POST http://localhost:8000/api/v1/library/vendors \
  -H "Content-Type: application/json" \
  -d '{"name":"Palo Alto Networks"}'

# 建 product
curl -sS -b "$CK" -X POST http://localhost:8000/api/v1/library/vendors/palo-alto-networks/products \
  -H "Content-Type: application/json" \
  -d '{"name":"PAN-OS","category":"network"}'

# Get overview
curl -sS -b "$CK" http://localhost:8000/api/v1/library/overview | jq

kill %1
rm -f "$CK"
```

預期：每一步都 200/201，最後 overview 回的 JSON 內 `palo-alto-networks` vendor 下有 `pan-os` product，`is_empty: true`（因為還沒建 log_type）。

- [ ] **Step 4:** Commit（若有任何修正）

若一切過了不需 commit；若有修正則：

```bash
git add -p   # 選擇性加要 commit 的修正
git commit -m "fix: address lint/test issues found in 1b green-light pass"
```

---

## Task 20: Library flow integration test

end-to-end 測一條完整流程 — 真 PG / Redis。

**Files:**
- Create: `tests/integration/modules/library/__init__.py`（空檔）
- Create: `tests/integration/modules/library/test_library_flow.py`

- [ ] **Step 1: 寫測試**

```python
# tests/integration/modules/library/test_library_flow.py
import os
import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Log in as admin and return client with session cookie."""
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    return client


class TestLibraryFlow:
    """End-to-end flow: vendor → product → log_type → fields → parse_rule → publish → sample → overview."""

    async def test_full_flow(self, authenticated_client: AsyncClient):
        """Should walk through every Library write path and finish at a published state."""
        # Arrange — generate unique slug to avoid conflicts across re-runs
        unique = uuid.uuid4().hex[:8]
        vendor_slug = f"vendor-{unique}"

        # Act 1: create vendor
        r = await authenticated_client.post(
            "/api/v1/library/vendors",
            json={"name": f"Vendor {unique}", "slug": vendor_slug},
        )
        # Assert 1
        assert r.status_code == 201, r.text
        vendor = r.json()["data"]

        # Act 2: create product under vendor
        r = await authenticated_client.post(
            f"/api/v1/library/vendors/{vendor_slug}/products",
            json={"name": "Test Product", "slug": "test-product", "category": "network"},
        )
        # Assert 2
        assert r.status_code == 201
        product = r.json()["data"]

        # Act 3: create log_type
        r = await authenticated_client.post(
            f"/api/v1/library/products/{product['id']}/log_types",
            json={"name": "Traffic", "slug": "traffic", "format": "csv"},
        )
        # Assert 3
        assert r.status_code == 201
        log_type = r.json()["data"]
        assert log_type["status"] == "draft"

        # Act 4: replace fields
        r = await authenticated_client.put(
            f"/api/v1/library/log_types/{log_type['id']}/fields",
            json={
                "fields": [
                    {"field_name": "src_ip", "field_type": "ip", "is_identifier": True},
                    {"field_name": "dst_ip", "field_type": "ip", "is_identifier": True},
                    {"field_name": "action", "field_type": "string"},
                ]
            },
        )
        # Assert 4
        assert r.status_code == 200
        assert len(r.json()["data"]) == 3

        # Act 5: create draft parse_rule
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/parse_rules",
            json={
                "vrl_code": ". = parse_csv!(.message)",
                "engine_version": "0.32",
                "notes": "v1 draft",
            },
        )
        # Assert 5
        assert r.status_code == 201
        parse_rule = r.json()["data"]
        assert parse_rule["version"] == 1
        assert parse_rule["status"] == "draft"

        # Act 6: publish
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/publish",
        )
        # Assert 6
        assert r.status_code == 200
        published_lt = r.json()["data"]
        assert published_lt["status"] == "published"
        assert published_lt["published_at"] is not None

        # Act 7: re-publish should 409
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/publish",
        )
        # Assert 7
        assert r.status_code == 409

        # Act 8: add sample
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/samples",
            json={"raw_log": "1,2,allow", "label": "normal"},
        )
        # Assert 8
        assert r.status_code == 201

        # Act 9: overview reflects state
        r = await authenticated_client.get("/api/v1/library/overview")
        # Assert 9
        assert r.status_code == 200
        groups = r.json()["data"]
        my_group = next(g for g in groups if g["vendor"]["slug"] == vendor_slug)
        assert len(my_group["products"]) == 1
        op = my_group["products"][0]
        assert op["log_type_counts"]["published"] == 1
        assert op["is_empty"] is False

        # Cleanup: delete vendor (cascades aren't on vendor → product, so we delete in reverse)
        # log_type cascade will delete fields/samples/parse_rules
        r = await authenticated_client.delete(f"/api/v1/library/log_types/{log_type['id']}")
        assert r.status_code == 204
        r = await authenticated_client.delete(f"/api/v1/library/products/{product['id']}")
        assert r.status_code == 204
        r = await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")
        assert r.status_code == 204
```

- [ ] **Step 2: 跑 integration test**

確保 docker compose 起、migration 已 apply：

```bash
docker compose ps
uv run alembic upgrade head
make test-int
```

預期 4 個 integration test 全綠（Plan 1a 已有 2 個 + 此 task 新增 1 個 + 1a flow）：
- `test_login_then_me_then_logout`
- `test_login_with_wrong_password_rejected`
- `test_full_flow`

- [ ] **Step 3: Commit**

```bash
git add tests/integration/modules/library/
git commit -m "test(library): add end-to-end integration test for full Library flow"
```

---

## Self-Review 與驗收

- [ ] **Self-check 1: Spec 對照**

| Spec § | Plan 對應 |
|---|---|
| §1.1 進 v1（Library 範圍） | Tasks 2-18 涵蓋 |
| §3.6 Repository / Service 介面風格 | Tasks 5/8/11/12 等等都遵循 |
| §4 資料模型（6 表 + users） | Tasks 2 + 3 |
| §4.4 循環 FK | Task 3 用 `use_alter=True` 兩階段建 |
| §4.8 Publish 流程 | Task 13 LogTypeService.publish |
| §5 API 規格全部 endpoint | Tasks 7/10/15/16/17/18 |
| §5.2 Library Overview filter（AND） | Task 18 service.overview 同時收 category + log_type_status，逐 product 過濾 |
| §6 Migration（trigger） | Task 3 為 6 表加 trigger |
| §8 測試 AAA pattern | 所有 service / router test 都用 `# Arrange / # Act / # Assert` 三段註解 |
| §10 驗收 1a 已涵蓋的；1b 新增「能完整走完 Library 流程」 | Task 20 |

- [ ] **Self-check 2: 全綠**

```bash
make lint && make test && make test-int
```

- [ ] **Self-check 3: 手動 smoke 一條 vendor → ... → publish 流程**

依 Task 19 Step 3 的 curl 序列。

---

## 完成定義

- 20 個 task 全部 commit 在 `feat/library-backend` 分支
- `make lint && make test && make test-int` 全綠
- 至少一條完整 vendor/product/log_type/fields/parse_rule/publish/sample 流程能透過 API 跑通
- Library overview endpoint 反映正確計數
- ParseRule 版本遞增 + draft → published 的不可變性都驗證過

下一步 plan：1c（Frontend，Next.js + Library 列表頁 + 詳情頁 + Copilot panel 預留）。

---

## Known gaps（v1 接受、之後處理）

| 議題 | 現況 | 後續 |
|---|---|---|
| 刪 vendor / product 有子資料時應回 409 | DB 層用 `ondelete="RESTRICT"` 阻擋，但 `IntegrityError` 會以 500 冒泡（沒映射到 `ConflictError`） | 加 `app/core/exception_handlers.py` 的 IntegrityError → 409 handler，或在 service 層顯式 count children；spec 1c 開始前順手做 |
| Sample log delete 沒檢查 ownership | 任何登入 user 都能刪別人的 sample | 加 user 範圍檢查；目前 v1 單用戶不影響 |
| Product 詳情 nested endpoint（spec §5.4 GET 包 log_types/fields/parse_rule/samples） | 本 plan 沒實作，列表頁與詳情頁可分多個 GET 拼出 | 1c 若前端體驗差再加 nested endpoint |
| `LogType` 詳情 nested（spec §5.5 GET 含 fields / current_parse_rule / sample_logs） | 同上，未實作 | 1c 視前端需求加 |
| 全文搜尋 `?q=` | overview endpoint 沒 wire `q` 參數到實際 SQL filter | 1c 列表頁要用時加 ILIKE 搜 vendor.name / product.name |

