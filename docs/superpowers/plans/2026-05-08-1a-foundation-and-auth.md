# 1a: Foundation + Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 LogScope 後端骨架 + auth module，產出能透過 HTTP 登入、回應 `/auth/me` 的可運行 FastAPI 服務，並完成 PG / Redis / Alembic 的連線設定，作為後續 Library 與其他 spec 的基礎。

**Architecture:** 採 growin-api-platform 的 feature module 風格 — `app/modules/{feature}/{models,repositories,services,routers}/`。Auth 用 HttpOnly cookie 帶 session_id，session 資料存 Redis（30 天 TTL），密碼用 bcrypt。所有 DB 操作走 SQLAlchemy 2.0 async + asyncpg；Alembic async template 管 migration，`set_updated_at()` PL/pgSQL trigger 是 `updated_at` 自動更新的安全網。

**Tech Stack:** Python 3.13、uv、FastAPI、Pydantic v2、SQLAlchemy 2.0 async、asyncpg、Alembic、redis.asyncio、structlog、passlib[bcrypt]、pytest + pytest-asyncio + httpx AsyncClient、ruff、pyright。

**Spec ref:** `docs/superpowers/specs/2026-05-08-foundation-and-library-min-design.md`

---

## File Structure（本 plan 範圍）

| 路徑 | 職責 |
|---|---|
| `pyproject.toml` | uv 專案設定、依賴、pytest / ruff / pyright 設定 |
| `docker-compose.yml` | postgres + redis（v1 不啟用 ClickHouse） |
| `Makefile` | 常用指令快捷 |
| `.env.example` | 環境變數範本 |
| `app/main.py` | `create_app()`、掛 router、`/healthz` |
| `app/core/config.py` | pydantic-settings 讀 env |
| `app/core/logging.py` | structlog 設定 |
| `app/core/database.py` | AsyncEngine、async sessionmaker、`get_db_session` dep |
| `app/core/cache.py` | redis.asyncio client、`get_redis` dep |
| `app/core/lifespan.py` | DB / Redis 啟動關閉 |
| `app/core/middleware.py` | request id middleware |
| `app/core/exception_handlers.py` | 把 `AppException` 轉成統一 JSON |
| `app/api/v1/__init__.py` | 聚合所有 module router 到 `/api/v1` |
| `app/common/mixins.py` | `TimestampMixin` |
| `app/common/exceptions.py` | `AppException` 階層 |
| `app/common/schemas.py` | `DataResponse` / `PaginatedResponse` / `ErrorResponse` |
| `app/common/auth.py` | `current_user` FastAPI dep |
| `app/alembic/env.py` | 從 settings 讀 URL、import models |
| `app/alembic/helpers.py` | `add_updated_at_trigger` / `drop_updated_at_trigger` |
| `app/alembic/versions/0001_*.py` | users 表 + `set_updated_at()` function + trigger |
| `app/alembic/versions/0002_*.py` | seed admin user |
| `app/modules/auth/models/user.py` | `User` ORM model |
| `app/modules/auth/repositories/user_repository.py` | user DB query |
| `app/modules/auth/services/password_service.py` | bcrypt hash / verify |
| `app/modules/auth/services/auth_service.py` | login / logout / get me |
| `app/modules/auth/routers/auth_router.py` | `POST /login`、`POST /logout`、`GET /me` |
| `app/modules/auth/schemas.py` | LoginRequest、UserRead |
| `tests/conftest.py` | client / mock_db / mock_cache fixtures |
| `tests/unit/...` | 各 service / router 單測 |
| `tests/integration/conftest.py` | 真實 DB / Redis fixture |
| `tests/integration/modules/auth/test_auth_flow.py` | login → me → logout |

---

## Task 1: 初始化 uv 專案與依賴

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `ruff.toml`
- Create: `pyrightconfig.json`

- [ ] **Step 1:** 在 repo 根目錄執行 uv init

```bash
cd /Users/amos/Documents/side-projects/logscope
uv init --name logscope --python 3.13 --no-readme
```

- [ ] **Step 2:** 把 `pyproject.toml` 換成下面內容

```toml
[project]
name = "logscope"
version = "0.1.0"
description = "Log analysis platform with VRL editor, vendor library, and LLM Copilot."
requires-python = ">=3.13,<3.14"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "structlog>=24.4",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.18",
    "httpx>=0.28",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.8",
    "pyright>=1.1.390",
    "anyio>=4.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3:** 寫 `.gitignore`

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.coverage
.idea/
.DS_Store
.env
web/node_modules/
web/.next/
```

- [ ] **Step 4:** 寫 `ruff.toml`

```toml
target-version = "py313"
line-length = 120
exclude = [".venv", "__pycache__", ".ruff_cache", ".pytest_cache", "app/alembic/versions"]

[lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "DTZ", "T10", "RUF"]
ignore = ["E501"]

[lint.isort]
known-first-party = ["app", "tests"]
```

- [ ] **Step 5:** 寫 `pyrightconfig.json`

```json
{
  "include": ["app", "tests"],
  "exclude": ["**/__pycache__", ".venv", "app/alembic/versions"],
  "pythonVersion": "3.13",
  "typeCheckingMode": "standard",
  "reportMissingImports": "error",
  "reportMissingTypeStubs": false
}
```

- [ ] **Step 6:** Sync 依賴並驗證

Run: `uv sync`
Expected: 無錯誤，建立 `.venv`、`uv.lock`

- [ ] **Step 7:** Commit

```bash
git add pyproject.toml uv.lock .python-version .gitignore ruff.toml pyrightconfig.json
git commit -m "chore: init uv project with FastAPI + SQLAlchemy + Redis deps"
```

---

## Task 2: docker-compose（Postgres + Redis）

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1:** 寫 `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: logscope
      POSTGRES_PASSWORD: logscope
      POSTGRES_DB: logscope
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U logscope"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

- [ ] **Step 2:** 寫 `.env.example`

```
DATABASE_URL=postgresql+asyncpg://logscope:logscope@localhost:5432/logscope
REDIS_URL=redis://localhost:6379/0

SESSION_COOKIE_SECURE=false
SESSION_TTL_SECONDS=2592000

LOGSCOPE_ADMIN_EMAIL=admin@logscope.local
LOGSCOPE_ADMIN_PASSWORD=changeme

LOG_LEVEL=INFO
LOG_FORMAT=json
```

- [ ] **Step 3:** 啟動驗證

Run: `docker compose up -d && docker compose ps`
Expected: postgres 與 redis 都顯示 `healthy`

- [ ] **Step 4:** Commit

```bash
git add docker-compose.yml .env.example
git commit -m "chore: add docker-compose for postgres and redis"
```

---

## Task 3: `app/core/config.py` — Settings

**Files:**
- Create: `app/__init__.py`（空檔）
- Create: `app/core/__init__.py`（空檔）
- Create: `app/core/config.py`
- Create: `tests/__init__.py`（空檔）
- Create: `tests/unit/__init__.py`（空檔）
- Create: `tests/unit/core/__init__.py`（空檔）
- Create: `tests/unit/core/test_config.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/core/test_config.py
import os

from app.core.config import Settings


class TestSettings:
    """Tests for Settings env loading."""

    def test_settings_loads_database_url_from_env(self, monkeypatch):
        """Should load DATABASE_URL from env."""
        # Arrange
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("LOGSCOPE_ADMIN_EMAIL", "a@b.c")
        monkeypatch.setenv("LOGSCOPE_ADMIN_PASSWORD", "x")

        # Act
        settings = Settings()

        # Assert
        assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.session_ttl_seconds == 2592000  # default
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/core/test_config.py -v`
Expected: ImportError / ModuleNotFoundError

- [ ] **Step 3:** 實作 `app/core/config.py`

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    # Cookie name 固定為 "session"，不暴露為 setting（避免 dep alias 與 settings 失聯）
    session_cookie_secure: bool = Field(False, alias="SESSION_COOKIE_SECURE")
    session_ttl_seconds: int = Field(2592000, alias="SESSION_TTL_SECONDS")

    admin_email: str = Field(..., alias="LOGSCOPE_ADMIN_EMAIL")
    admin_password: str = Field(..., alias="LOGSCOPE_ADMIN_PASSWORD")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/core/test_config.py -v`
Expected: PASS

- [ ] **Step 5:** Commit

```bash
git add app/__init__.py app/core/__init__.py app/core/config.py tests/__init__.py tests/unit/__init__.py tests/unit/core/__init__.py tests/unit/core/test_config.py
git commit -m "feat(core): add Settings with pydantic-settings"
```

---

## Task 4: `app/core/logging.py` — structlog 設定

**Files:**
- Create: `app/core/logging.py`

- [ ] **Step 1:** 實作（這層是 wiring，不需單測；測試會跟著 main.py 一起檢查）

```python
import logging
import sys

import structlog


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level),
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 2:** Commit

```bash
git add app/core/logging.py
git commit -m "feat(core): add structlog configuration"
```

---

## Task 5: `app/core/database.py` — AsyncEngine + Session

**Files:**
- Create: `app/core/database.py`
- Create: `tests/unit/core/test_database.py`

- [ ] **Step 1:** 寫測試（驗證 sessionmaker 行為）

```python
# tests/unit/core/test_database.py
from app.core.database import DatabaseManager


class TestDatabaseManager:
    """Tests for DatabaseManager wiring."""

    def test_init_does_not_connect_immediately(self):
        """Should defer engine creation to connect()."""
        # Arrange / Act
        mgr = DatabaseManager(url="postgresql+asyncpg://u:p@h:5432/db")

        # Assert
        assert mgr._engine is None
        assert mgr._sessionmaker is None
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/core/test_database.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作

```python
# app/core/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all models."""


class DatabaseManager:
    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if self._engine is not None:
            return
        self._engine = create_async_engine(self._url, pool_pre_ping=True)
        self._sessionmaker = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._sessionmaker is None:
            raise RuntimeError("DatabaseManager not connected")
        async with self._sessionmaker() as session:
            yield session


_db: DatabaseManager | None = None


def init_database(url: str) -> DatabaseManager:
    global _db
    _db = DatabaseManager(url)
    return _db


def get_database() -> DatabaseManager:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends: yield AsyncSession bound to current request."""
    async for session in get_database().session():
        yield session
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/core/test_database.py -v`
Expected: PASS

- [ ] **Step 5:** Commit

```bash
git add app/core/database.py tests/unit/core/test_database.py
git commit -m "feat(core): add async DatabaseManager and Base"
```

---

## Task 6: `app/core/cache.py` — Redis client

**Files:**
- Create: `app/core/cache.py`
- Create: `tests/unit/core/test_cache.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/core/test_cache.py
from app.core.cache import CacheManager


class TestCacheManager:
    """Tests for CacheManager wiring."""

    def test_init_defers_connection(self):
        """Should defer client creation to connect()."""
        # Arrange / Act
        mgr = CacheManager(url="redis://localhost:6379/0")

        # Assert
        assert mgr._client is None
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/core/test_cache.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作

```python
# app/core/cache.py
from redis.asyncio import Redis, from_url


class CacheManager:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = from_url(self._url, decode_responses=True)
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("CacheManager not connected")
        return self._client


_cache: CacheManager | None = None


def init_cache(url: str) -> CacheManager:
    global _cache
    _cache = CacheManager(url)
    return _cache


def get_cache() -> CacheManager:
    if _cache is None:
        raise RuntimeError("Cache not initialized")
    return _cache


async def get_redis() -> Redis:
    """FastAPI Depends: return active Redis client."""
    return get_cache().client
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/core/test_cache.py -v`
Expected: PASS

- [ ] **Step 5:** Commit

```bash
git add app/core/cache.py tests/unit/core/test_cache.py
git commit -m "feat(core): add async CacheManager (redis.asyncio)"
```

---

## Task 7: `app/common/exceptions.py` + `app/core/exception_handlers.py`

**Files:**
- Create: `app/common/__init__.py`（空檔）
- Create: `app/common/exceptions.py`
- Create: `app/core/exception_handlers.py`
- Create: `tests/unit/common/__init__.py`（空檔）
- Create: `tests/unit/common/test_exceptions.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/common/test_exceptions.py
from app.common.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)


class TestAppException:
    """Tests for AppException hierarchy."""

    def test_not_found_default_status(self):
        """Should set status_code=404 and code='not_found'."""
        # Arrange / Act
        exc = NotFoundError("vendor not found")

        # Assert
        assert exc.status_code == 404
        assert exc.code == "not_found"
        assert exc.detail == "vendor not found"

    def test_conflict_default_status(self):
        """Should set status_code=409."""
        # Arrange / Act
        exc = ConflictError()

        # Assert
        assert exc.status_code == 409
        assert exc.code == "conflict"

    def test_unauthorized_default_status(self):
        """Should set status_code=401."""
        # Arrange / Act
        exc = UnauthorizedError()

        # Assert
        assert exc.status_code == 401
        assert isinstance(exc, AppException)
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/common/test_exceptions.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作 `app/common/exceptions.py`

```python
class AppException(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.__name__
        super().__init__(self.detail)


class NotFoundError(AppException):
    status_code = 404
    code = "not_found"


class ConflictError(AppException):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppException):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppException):
    status_code = 403
    code = "forbidden"


class ValidationError(AppException):
    status_code = 422
    code = "validation_error"
```

- [ ] **Step 4:** 實作 `app/core/exception_handlers.py`

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.exceptions import AppException


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "detail": exc.detail}},
        )
```

- [ ] **Step 5:** Run 預期通過

Run: `uv run pytest tests/unit/common/test_exceptions.py -v`
Expected: PASS

- [ ] **Step 6:** Commit

```bash
git add app/common/__init__.py app/common/exceptions.py app/core/exception_handlers.py tests/unit/common/__init__.py tests/unit/common/test_exceptions.py
git commit -m "feat(common): add AppException hierarchy and FastAPI handler"
```

---

## Task 8: `app/common/schemas.py` + `app/common/mixins.py`

**Files:**
- Create: `app/common/schemas.py`
- Create: `app/common/mixins.py`

- [ ] **Step 1:** 實作 `app/common/schemas.py`

```python
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataResponse(BaseModel, Generic[T]):
    data: T


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int


class ErrorBody(BaseModel):
    code: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
```

- [ ] **Step 2:** 實作 `app/common/mixins.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 3:** Run lint 與 type check 確認沒錯

Run: `uv run ruff check app/common/ && uv run pyright app/common/`
Expected: 0 errors

- [ ] **Step 4:** Commit

```bash
git add app/common/schemas.py app/common/mixins.py
git commit -m "feat(common): add response wrappers and TimestampMixin"
```

---

## Task 9: `app/core/middleware.py` + `app/core/lifespan.py`

**Files:**
- Create: `app/core/middleware.py`
- Create: `app/core/lifespan.py`

- [ ] **Step 1:** 實作 `app/core/middleware.py`

```python
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["x-request-id"] = request_id
        return response
```

- [ ] **Step 2:** 實作 `app/core/lifespan.py`

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import init_cache
from app.core.config import get_settings
from app.core.database import init_database
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    db = init_database(settings.database_url)
    cache = init_cache(settings.redis_url)
    await db.connect()
    await cache.connect()
    try:
        yield
    finally:
        await cache.disconnect()
        await db.disconnect()
```

- [ ] **Step 3:** Commit

```bash
git add app/core/middleware.py app/core/lifespan.py
git commit -m "feat(core): add request-id middleware and lifespan manager"
```

---

## Task 10: `app/main.py` + `app/api/v1/__init__.py` 骨架

**Files:**
- Create: `app/api/__init__.py`（空檔）
- Create: `app/api/v1/__init__.py`
- Create: `app/main.py`
- Create: `tests/unit/test_health.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/test_health.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """Override lifespan to no-op for unit-style health check test."""
    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_a: FastAPI) -> AsyncGenerator[None, None]:
        yield

    app.router.lifespan_context = _noop_lifespan
    return app


class TestHealth:
    """Tests for /healthz endpoint."""

    async def test_healthz_returns_200(self, app: FastAPI):
        """Should return 200 with status=ok."""
        # Arrange
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Act
            response = await client.get("/healthz")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/test_health.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作 `app/api/v1/__init__.py`

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")
```

- [ ] **Step 4:** 實作 `app/main.py`

```python
from fastapi import FastAPI

from app.api.v1 import router as api_v1_router
from app.core.exception_handlers import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.middleware import register_middleware


def create_app() -> FastAPI:
    app = FastAPI(title="LogScope", lifespan=lifespan)
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_v1_router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5:** Run 預期通過

Run: `uv run pytest tests/unit/test_health.py -v`
Expected: PASS

- [ ] **Step 6:** 手動跑起來確認

Run: `uv run uvicorn app.main:app --port 8000` 然後 `curl http://localhost:8000/healthz`
Expected: `{"status":"ok"}`，再 ctrl+c 關掉

- [ ] **Step 7:** Commit

```bash
git add app/main.py app/api/__init__.py app/api/v1/__init__.py tests/unit/test_health.py
git commit -m "feat(core): add FastAPI app skeleton with /healthz"
```

---

## Task 11: Alembic init + 設定

**Files:**
- Create: `alembic.ini`
- Create: `app/alembic/env.py`
- Create: `app/alembic/script.py.mako`
- Create: `app/alembic/helpers.py`
- Create: `app/alembic/__init__.py`（空檔）
- Create: `app/alembic/versions/.gitkeep`

- [ ] **Step 1:** 跑 alembic init

Run: `uv run alembic init -t async app/alembic`
Expected: 建立 `alembic.ini` 與 `app/alembic/` 內檔案

- [ ] **Step 2:** 改 `alembic.ini` 的 `script_location` 與移除 `sqlalchemy.url`

```ini
[alembic]
script_location = app/alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3:** 改 `app/alembic/env.py`，把 URL 來源換成 settings、import models

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Import all models so Alembic autogenerate can detect them
from app.modules.auth.models import user as _user_model  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

> 註：`from app.modules.auth.models import user as _user_model` 暫時 import 不存在的模組會失敗 — 別在這階段跑 migrate；下面 Task 13 建好 user model 後此 import 才生效。先把 env.py 寫好讓它一就位即生效。

- [ ] **Step 4:** 寫 `app/alembic/helpers.py`

```python
from alembic import op


def add_updated_at_trigger(table_name: str) -> None:
    op.execute(f"""
        CREATE TRIGGER trg_{table_name}_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def drop_updated_at_trigger(table_name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};")


def create_set_updated_at_function() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def drop_set_updated_at_function() -> None:
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
```

- [ ] **Step 5:** Commit（暫不能跑 migrate，等 Task 13 後再跑）

```bash
git add alembic.ini app/alembic/
git commit -m "chore(alembic): init async alembic with settings-driven URL and trigger helpers"
```

---

## Task 12: Auth module 結構 + User model

**Files:**
- Create: `app/modules/__init__.py`（空檔）
- Create: `app/modules/auth/__init__.py`（空檔）
- Create: `app/modules/auth/models/__init__.py`
- Create: `app/modules/auth/models/user.py`

- [ ] **Step 1:** 寫 User model

```python
# app/modules/auth/models/user.py
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin
from app.core.database import Base

if TYPE_CHECKING:
    pass


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

- [ ] **Step 2:** 寫 `app/modules/auth/models/__init__.py`

```python
from app.modules.auth.models.user import User

__all__ = ["User"]
```

- [ ] **Step 3:** Commit

```bash
git add app/modules/__init__.py app/modules/auth/__init__.py app/modules/auth/models/
git commit -m "feat(auth): add User model"
```

---

## Task 13: 第一個 migration（users 表 + set_updated_at function）

**Files:**
- Create: `app/alembic/versions/0001_init_users.py`

- [ ] **Step 1:** 確認 docker compose 起著，建 migration revision 骨架

Run: `uv run alembic revision -m "init users"`
Expected: 在 `app/alembic/versions/` 建出 `<rev>_init_users.py`，把它 rename 為 `0001_init_users.py`

- [ ] **Step 2:** 編輯該檔，內容如下（覆蓋）

```python
"""init users

Revision ID: 0001_init_users
Revises:
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import (
    add_updated_at_trigger,
    create_set_updated_at_function,
    drop_set_updated_at_function,
    drop_updated_at_trigger,
)

revision: str = "0001_init_users"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    create_set_updated_at_function()

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    add_updated_at_trigger("users")


def downgrade() -> None:
    drop_updated_at_trigger("users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    drop_set_updated_at_function()
```

- [ ] **Step 3:** 跑 migration

Run: `uv run alembic upgrade head`
Expected: log 顯示 INFO  [alembic.runtime.migration] Running upgrade -> 0001_init_users

- [ ] **Step 4:** 驗證表存在

Run: `docker compose exec postgres psql -U logscope -c "\d users"`
Expected: 顯示 users 表 schema、有 trigger `trg_users_updated_at`

- [ ] **Step 5:** Commit

```bash
git add app/alembic/versions/0001_init_users.py
git commit -m "feat(alembic): add 0001 init users migration with updated_at trigger"
```

---

## Task 14: PasswordService

**Files:**
- Create: `app/modules/auth/services/__init__.py`（空檔）
- Create: `app/modules/auth/services/password_service.py`
- Create: `tests/unit/modules/__init__.py`（空檔）
- Create: `tests/unit/modules/auth/__init__.py`（空檔）
- Create: `tests/unit/modules/auth/test_password_service.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/modules/auth/test_password_service.py
from app.modules.auth.services.password_service import PasswordService


class TestPasswordService:
    """Tests for PasswordService."""

    def test_hash_then_verify_succeeds(self):
        """Should verify a correct password against its hash."""
        # Arrange
        svc = PasswordService()
        plain = "s3cret!"

        # Act
        hashed = svc.hash(plain)
        ok = svc.verify(plain, hashed)

        # Assert
        assert ok is True
        assert hashed != plain

    def test_verify_rejects_wrong_password(self):
        """Should return False when password does not match hash."""
        # Arrange
        svc = PasswordService()
        hashed = svc.hash("right")

        # Act
        ok = svc.verify("wrong", hashed)

        # Assert
        assert ok is False
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/modules/auth/test_password_service.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作

```python
# app/modules/auth/services/password_service.py
from passlib.context import CryptContext


class PasswordService:
    def __init__(self) -> None:
        self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain: str) -> str:
        return self._ctx.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return self._ctx.verify(plain, hashed)
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/modules/auth/test_password_service.py -v`
Expected: PASS（兩個 test）

- [ ] **Step 5:** Commit

```bash
git add app/modules/auth/services/ tests/unit/modules/__init__.py tests/unit/modules/auth/__init__.py tests/unit/modules/auth/test_password_service.py
git commit -m "feat(auth): add PasswordService (bcrypt hash/verify)"
```

---

## Task 15: UserRepository

**Files:**
- Create: `app/modules/auth/repositories/__init__.py`（空檔）
- Create: `app/modules/auth/repositories/user_repository.py`
- Create: `tests/unit/modules/auth/test_user_repository.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/modules/auth/test_user_repository.py
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository


def _make_user(email: str = "a@b.c") -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = email
    user.password_hash = "hashed"
    user.is_active = True
    return user


class TestUserRepositoryGetByEmail:
    """Tests for UserRepository.get_by_email()."""

    async def test_returns_user_when_found(self):
        """Should return User when email exists."""
        # Arrange
        target = _make_user("found@x.y")
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = UserRepository(mock_session)

        # Act
        result = await repo.get_by_email("found@x.y")

        # Assert
        assert result is target
        mock_session.execute.assert_awaited_once()

    async def test_returns_none_when_not_found(self):
        """Should return None when no row matches."""
        # Arrange
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = UserRepository(mock_session)

        # Act
        result = await repo.get_by_email("missing@x.y")

        # Assert
        assert result is None
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/modules/auth/test_user_repository.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作

```python
# app/modules/auth/repositories/user_repository.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/modules/auth/test_user_repository.py -v`
Expected: PASS

- [ ] **Step 5:** Commit

```bash
git add app/modules/auth/repositories/ tests/unit/modules/auth/test_user_repository.py
git commit -m "feat(auth): add UserRepository.get_by_id/get_by_email"
```

---

## Task 16: Auth schemas

**Files:**
- Create: `app/modules/auth/schemas.py`

- [ ] **Step 1:** 實作

```python
# app/modules/auth/schemas.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime
```

- [ ] **Step 2:** 補 EmailStr 依賴

Run: `uv add 'pydantic[email]'`
Expected: pyproject.toml 出現 `email-validator` 相關 dependency

- [ ] **Step 3:** Commit

```bash
git add app/modules/auth/schemas.py pyproject.toml uv.lock
git commit -m "feat(auth): add LoginRequest and UserRead schemas"
```

---

## Task 17: AuthService（login / logout / get_current_user_from_session）

**Files:**
- Create: `app/modules/auth/services/auth_service.py`
- Create: `tests/unit/modules/auth/test_auth_service.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/modules/auth/test_auth_service.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import UnauthorizedError
from app.modules.auth.models.user import User
from app.modules.auth.services.auth_service import AuthService


def _make_user(email: str = "a@b.c", active: bool = True) -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = email
    u.password_hash = "stored-hash"
    u.is_active = active
    return u


def _make_service(
    *,
    user_lookup: User | None = None,
    password_ok: bool = True,
):
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=user_lookup)
    repo.get_by_id = AsyncMock(return_value=user_lookup)

    pwd = MagicMock()
    pwd.verify = MagicMock(return_value=password_ok)

    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=str(user_lookup.id) if user_lookup else None)
    redis.delete = AsyncMock(return_value=1)

    service = AuthService(
        user_repo=repo,
        password_service=pwd,
        redis_client=redis,
        session_ttl_seconds=3600,
    )
    return service, repo, pwd, redis


class TestAuthServiceLogin:
    """Tests for AuthService.login()."""

    async def test_login_success_returns_session_id(self):
        """Should return a session_id and store user_id in redis."""
        # Arrange
        user = _make_user()
        service, _repo, _pwd, redis = _make_service(user_lookup=user)

        # Act
        session_id = await service.login(email=user.email, password="anything")

        # Assert
        assert isinstance(session_id, str) and len(session_id) > 0
        redis.set.assert_awaited_once()
        args, kwargs = redis.set.call_args
        assert args[0] == f"session:{session_id}"
        assert args[1] == str(user.id)
        assert kwargs.get("ex") == 3600

    async def test_login_unknown_email_raises_unauthorized(self):
        """Should raise UnauthorizedError when email not found."""
        # Arrange
        service, *_ = _make_service(user_lookup=None)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email="x@y.z", password="p")

    async def test_login_wrong_password_raises_unauthorized(self):
        """Should raise UnauthorizedError when password.verify returns False."""
        # Arrange
        user = _make_user()
        service, *_ = _make_service(user_lookup=user, password_ok=False)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email=user.email, password="wrong")

    async def test_login_inactive_user_raises_unauthorized(self):
        """Should reject inactive users."""
        # Arrange
        user = _make_user(active=False)
        service, *_ = _make_service(user_lookup=user)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email=user.email, password="ok")


class TestAuthServiceLogout:
    """Tests for AuthService.logout()."""

    async def test_logout_deletes_session(self):
        """Should DEL session:{id} in redis."""
        # Arrange
        service, *_, redis = _make_service(user_lookup=_make_user())

        # Act
        await service.logout("abc-123")

        # Assert
        redis.delete.assert_awaited_once_with("session:abc-123")


class TestAuthServiceCurrentUser:
    """Tests for AuthService.get_current_user_from_session()."""

    async def test_returns_user_when_session_valid(self):
        """Should look up redis and return User."""
        # Arrange
        user = _make_user()
        service, repo, _pwd, _redis = _make_service(user_lookup=user)

        # Act
        result = await service.get_current_user_from_session("sid")

        # Assert
        assert result is user
        repo.get_by_id.assert_awaited_once()

    async def test_raises_when_no_session_id(self):
        """Should raise when session_id is None."""
        # Arrange
        service, *_ = _make_service(user_lookup=_make_user())

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.get_current_user_from_session(None)
```

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/modules/auth/test_auth_service.py -v`
Expected: ImportError

- [ ] **Step 3:** 實作

```python
# app/modules/auth/services/auth_service.py
import uuid
from typing import Protocol

from app.common.exceptions import UnauthorizedError
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.password_service import PasswordService


class _RedisLike(Protocol):
    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool: ...
    async def get(self, key: str) -> str | None: ...
    async def delete(self, key: str) -> int: ...


class AuthService:
    def __init__(
        self,
        *,
        user_repo: UserRepository,
        password_service: PasswordService,
        redis_client: _RedisLike,
        session_ttl_seconds: int,
    ) -> None:
        self._users = user_repo
        self._pwd = password_service
        self._redis = redis_client
        self._ttl = session_ttl_seconds

    async def login(self, *, email: str, password: str) -> str:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            raise UnauthorizedError("invalid credentials")
        if not self._pwd.verify(password, user.password_hash):
            raise UnauthorizedError("invalid credentials")

        session_id = uuid.uuid4().hex
        await self._redis.set(f"session:{session_id}", str(user.id), ex=self._ttl)
        return session_id

    async def logout(self, session_id: str) -> None:
        await self._redis.delete(f"session:{session_id}")

    async def get_current_user_from_session(self, session_id: str | None) -> User:
        if not session_id:
            raise UnauthorizedError("missing session")
        user_id_str = await self._redis.get(f"session:{session_id}")
        if user_id_str is None:
            raise UnauthorizedError("invalid session")
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError as e:
            raise UnauthorizedError("invalid session") from e
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("invalid session")
        return user
```

- [ ] **Step 4:** Run 預期通過

Run: `uv run pytest tests/unit/modules/auth/test_auth_service.py -v`
Expected: PASS（六個 test）

- [ ] **Step 5:** Commit

```bash
git add app/modules/auth/services/auth_service.py tests/unit/modules/auth/test_auth_service.py
git commit -m "feat(auth): add AuthService (login/logout/current_user)"
```

---

## Task 18: `app/common/auth.py` — current_user dependency

**Files:**
- Create: `app/common/auth.py`

- [ ] **Step 1:** 實作

```python
# app/common/auth.py
from typing import Annotated

from fastapi import Cookie, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService

# Cookie name 固定，不從 Settings 取，避免 Cookie(alias=...) 與 Settings 失聯
SESSION_COOKIE_NAME = "session"


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        password_service=PasswordService(),
        redis_client=redis,
        session_ttl_seconds=settings.session_ttl_seconds,
    )


async def current_user(
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    auth: Annotated[AuthService, Depends(get_auth_service)] = ...,  # type: ignore[assignment]
) -> User:
    return await auth.get_current_user_from_session(session_cookie)
```

- [ ] **Step 2:** Commit

```bash
git add app/common/auth.py
git commit -m "feat(common): add current_user FastAPI dependency"
```

---

## Task 19: Auth router

**Files:**
- Create: `app/modules/auth/routers/__init__.py`（空檔）
- Create: `app/modules/auth/routers/auth_router.py`
- Create: `tests/unit/modules/auth/test_auth_router.py`

- [ ] **Step 1:** 寫測試

```python
# tests/unit/modules/auth/test_auth_router.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.common.auth import get_auth_service, current_user
from app.modules.auth.models.user import User


@pytest.fixture
def app() -> FastAPI:
    from app.main import create_app

    app = create_app()

    @asynccontextmanager
    async def _noop(_a: FastAPI) -> AsyncGenerator[None, None]:
        yield

    app.router.lifespan_context = _noop
    return app


class TestLoginRoute:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_returns_session_cookie_on_success(self, app: FastAPI):
        """Should set HttpOnly session cookie when login succeeds."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(return_value="sid-abc")
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    async def test_login_returns_401_on_invalid(self, app: FastAPI):
        """Should map UnauthorizedError to 401."""
        # Arrange
        from app.common.exceptions import UnauthorizedError

        fake_auth = AsyncMock()
        fake_auth.login = AsyncMock(side_effect=UnauthorizedError("invalid credentials"))
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    async def test_me_returns_user(self, app: FastAPI):
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

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Act
            r = await client.get("/api/v1/auth/me")

        # Assert
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == "me@x.y"
        assert body["data"]["display_name"] == "Me"


class TestLogoutRoute:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_clears_cookie(self, app: FastAPI):
        """Should call AuthService.logout and clear cookie."""
        # Arrange
        fake_auth = AsyncMock()
        fake_auth.logout = AsyncMock(return_value=None)
        app.dependency_overrides[get_auth_service] = lambda: fake_auth

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

- [ ] **Step 2:** Run，預期失敗

Run: `uv run pytest tests/unit/modules/auth/test_auth_router.py -v`
Expected: ImportError 或 404 errors（router 還沒掛）

- [ ] **Step 3:** 實作 router

```python
# app/modules/auth/routers/auth_router.py
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from app.common.auth import SESSION_COOKIE_NAME, current_user, get_auth_service
from app.common.schemas import DataResponse
from app.core.config import Settings, get_settings
from app.modules.auth.models.user import User
from app.modules.auth.schemas import LoginRequest, UserRead
from app.modules.auth.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DataResponse[dict]:
    session_id = await auth.login(email=body.email, password=body.password)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return DataResponse(data={"ok": True})


@router.post("/logout")
async def logout(
    response: Response,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> DataResponse[dict]:
    if session_cookie:
        await auth.logout(session_cookie)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        path="/",
    )
    return DataResponse(data={"ok": True})


@router.get("/me", response_model=DataResponse[UserRead])
async def me(user: Annotated[User, Depends(current_user)]) -> DataResponse[UserRead]:
    return DataResponse(data=UserRead.model_validate(user))
```

- [ ] **Step 4:** 把 router 掛進 `app/api/v1/__init__.py`

```python
# app/api/v1/__init__.py
from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
```

- [ ] **Step 5:** Run 預期通過

Run: `uv run pytest tests/unit/modules/auth/test_auth_router.py -v`
Expected: PASS（四個 test）

- [ ] **Step 6:** Commit

```bash
git add app/modules/auth/routers/ app/api/v1/__init__.py tests/unit/modules/auth/test_auth_router.py
git commit -m "feat(auth): add /auth/login, /auth/logout, /auth/me routes"
```

---

## Task 20: Seed admin user（資料 migration）

**Files:**
- Create: `app/alembic/versions/0002_seed_admin_user.py`

- [ ] **Step 1:** 建空的 revision

Run: `uv run alembic revision -m "seed admin user"`
然後把檔名 rename 為 `0002_seed_admin_user.py`

- [ ] **Step 2:** 改寫該檔內容

```python
"""seed admin user

Revision ID: 0002_seed_admin_user
Revises: 0001_init_users
Create Date: 2026-05-08
"""
import os
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision: str = "0002_seed_admin_user"
down_revision: str | None = "0001_init_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    email = os.environ.get("LOGSCOPE_ADMIN_EMAIL")
    password = os.environ.get("LOGSCOPE_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError(
            "LOGSCOPE_ADMIN_EMAIL and LOGSCOPE_ADMIN_PASSWORD must be set to run 0002 migration"
        )

    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, display_name, is_active) "
            "VALUES (:id, :email, :hash, :name, true)"
        ).bindparams(
            id=uuid.uuid4(),
            email=email,
            hash=ctx.hash(password),
            name="Admin",
        )
    )


def downgrade() -> None:
    email = os.environ.get("LOGSCOPE_ADMIN_EMAIL")
    if not email:
        return
    op.execute(sa.text("DELETE FROM users WHERE email = :email").bindparams(email=email))
```

- [ ] **Step 3:** 跑 migration（先確保 .env 已從 .env.example 複製過來）

Run: `cp -n .env.example .env && uv run alembic upgrade head`
Expected: 執行 0002，無錯誤

- [ ] **Step 4:** 驗證有資料

Run: `docker compose exec postgres psql -U logscope -c "SELECT email, is_active FROM users;"`
Expected: 看到 admin@logscope.local / t

- [ ] **Step 5:** Commit

```bash
git add app/alembic/versions/0002_seed_admin_user.py
git commit -m "feat(alembic): seed admin user from env on first migration"
```

---

## Task 21: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1:** 寫 Makefile

```makefile
.PHONY: setup up down migrate api test test-int lint format gen-api shell

setup:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

migrate:
	uv run alembic upgrade head

api:
	uv run uvicorn app.main:app --reload --port 8000

test:
	uv run pytest tests/unit -v

test-int:
	uv run pytest tests/integration -v

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

format:
	uv run ruff format .
	uv run ruff check . --fix
```

- [ ] **Step 2:** 驗證指令可跑

Run: `make lint`
Expected: 0 errors（如果有錯誤先 `make format`）

- [ ] **Step 3:** Commit

```bash
git add Makefile
git commit -m "chore: add Makefile shortcuts"
```

---

## Task 22: 全 lint pass + 整體 unit 測試 pass

- [ ] **Step 1:** 跑全 lint

Run: `make lint`
Expected: 全綠

- [ ] **Step 2:** 跑全 unit 測試

Run: `make test`
Expected: 全綠

- [ ] **Step 3:** 若有錯誤逐項修正、commit

```bash
git add -p
git commit -m "fix: resolve lint and type errors after auth wiring"
```
（若沒錯就跳過）

---

## Task 23: Integration test — 真實 login → me → logout

**Files:**
- Create: `tests/integration/__init__.py`（空檔）
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/modules/__init__.py`（空檔）
- Create: `tests/integration/modules/auth/__init__.py`（空檔）
- Create: `tests/integration/modules/auth/test_auth_flow.py`

- [ ] **Step 1:** 寫 conftest

```python
# tests/integration/conftest.py
"""Integration test fixtures: real Postgres + Redis from docker-compose.

Assumes `make up && make migrate` has been run; tests will run admin login
and reuse the seeded admin user. Each test cleans up its own data.
"""
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def app() -> AsyncGenerator[FastAPI, None]:
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2:** 寫 integration test

```python
# tests/integration/modules/auth/test_auth_flow.py
import os

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


class TestAuthFlow:
    """End-to-end auth flow against real Postgres + Redis."""

    async def test_login_then_me_then_logout(self, client: AsyncClient):
        """Should log in, fetch /me, then log out and reject /me."""
        # Arrange
        email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
        password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]

        # Act 1: login
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

        # Assert 1
        assert r.status_code == 200, r.text
        assert "session" in client.cookies

        # Act 2: me
        r = await client.get("/api/v1/auth/me")

        # Assert 2
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["email"] == email

        # Act 3: logout
        r = await client.post("/api/v1/auth/logout")

        # Assert 3
        assert r.status_code == 200

        # Act 4: me (now unauthorized)
        r = await client.get("/api/v1/auth/me")

        # Assert 4
        assert r.status_code == 401

    async def test_login_with_wrong_password_rejected(self, client: AsyncClient):
        """Should return 401 for wrong password."""
        # Arrange
        email = os.environ["LOGSCOPE_ADMIN_EMAIL"]

        # Act
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "definitely-wrong"},
        )

        # Assert
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
```

- [ ] **Step 3:** 跑 integration test

Run: `make up && make migrate && make test-int`
Expected: 兩個 test 都 PASS

- [ ] **Step 4:** Commit

```bash
git add tests/integration/
git commit -m "test(auth): add integration test for login/me/logout flow"
```

---

## Self-Review 與驗收

- [ ] **Self-check 1:** Spec 對照
  - §3.5 Auth 流程：Task 17 + 19 + 20 全部實作（login/logout/me + admin seed）。✓
  - §3.4 Common：Task 7 + 8 完成。✓
  - §6 Migration：Task 11 + 13 + 20 完成（async template、helper、updated_at trigger、seed）。✓
  - §10 驗收 1～3 行：Task 22 + 23 涵蓋。
  - 注意：本 plan 不包含 library schema、library API、frontend；那是 1b / 1c。

- [ ] **Self-check 2:** 整段 lint + test 一次過

Run: `make lint && make test && make test-int`
Expected: 全綠

- [ ] **Self-check 3:** 手動 smoke

```bash
make api &
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@logscope.local","password":"changeme"}'
curl -b 'session=<貼上面回的 session>' http://localhost:8000/api/v1/auth/me
kill %1
```
Expected: 第一次回 200 + Set-Cookie，第二次回含 admin email 的 JSON

---

## 完成定義

- 所有 23 個 task 的 commit 都已在 `main` 上
- `make up && make migrate && make api` 跑得起來
- `make test` + `make test-int` 全綠
- `curl` 能完成 login → me → logout 流程

下一步 plan：1b（Library backend，6 張表 + CRUD + overview + integration test）。
