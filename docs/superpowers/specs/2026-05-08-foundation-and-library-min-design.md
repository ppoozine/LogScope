# LogScope — Foundation + Library (Manual CRUD) Spec

- 日期：2026-05-08
- 子專案編號：1（A 骨架 + B-min Library 手動 CRUD）
- 上游文件：`docs/LogScope_Design_Document_v1.2.html`
- POC 參考：`/Users/amos/Documents/side-projects/pyvrl-playground`
- Feature module 風格參考：`/Users/amos/Documents/TradingValley/projects/growin-api-platform`

---

## 1. 範圍

本 spec 是 LogScope 第一個實作 spec，目標是把平台骨架立好、Library 能透過 API 與 UI 完整運作；後續 Analyzer / Copilot / Pipeline 的 spec 在此基礎上疊加。

### 1.1 進 v1

**後端骨架**
- uv 專案、Python 3.13、FastAPI 應用框架
- PostgreSQL 主資料庫（SQLAlchemy 2.0 async + asyncpg）
- Redis（session 儲存）
- Alembic migration（async）
- Logging（structlog）、ruff + pyright、pytest
- Auth：email/password session（HttpOnly cookie + Redis）

**前端骨架**
- Next.js 14+ App Router、TypeScript
- Tailwind + shadcn/ui、TanStack Query、openapi-typescript、biome
- 全站 layout（top nav + 右側 Copilot panel 預留位置）
- 登入頁、空狀態、Library 列表頁、Product 詳情頁
- Analyzer / Copilot 路由為 placeholder 頁

**Library 資料模型與 API（手動 CRUD）**
- 6 個資料表：`vendors`、`products`、`log_types`、`field_schemas`、`parse_rules`、`sample_logs`
- `users` 表（auth 用）
- 完整 CRUD endpoint
- Publish 流程（draft → published 並升版本號）

**測試**
- 全部 service / router 寫 unit test，AAA pattern
- Library 完整流程 integration test（建 vendor → product → log_type → fields → parse_rule → publish → 詳情頁回傳）

### 1.2 不進 v1（指明後續 spec）

| 功能 | 後續 spec |
|---|---|
| VRL 編輯器、即時 parse | C（Analyzer） |
| Match bar、「載入 Analyzer」、「在 Analyzer 試打」 | C |
| 「存回 Library」、「存為 sample」 | C |
| Copilot 對話 UI、SSE、prompt 注入 | D |
| Review 頁面 diff 視圖、`in_review` / `rejected` 狀態、`source = llm_generated` | E |
| 「AI 建庫」按鈕功能 | E |
| ClickHouse 連線與寫入（含 parse 統計、使用頻率） | C 起 |
| Library response cache | 視效能再加 |
| 全文搜尋 / fuzzy search | 視需求再加 |
| OAuth、忘記密碼、註冊 UI | 視需求再加 |

---

## 2. Repo 結構

```
logscope/
├── app/                                  # Python package（FastAPI）
│   ├── main.py                           # create_app() + uvicorn 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                     # pydantic-settings
│   │   ├── database.py                   # AsyncEngine / sessionmaker
│   │   ├── cache.py                      # redis.asyncio client
│   │   ├── lifespan.py                   # app 啟動/關閉時連線管理
│   │   ├── deps.py                       # FastAPI Depends（db, cache, current_user）
│   │   ├── middleware.py                 # request id、logging context
│   │   ├── exception_handlers.py         # 統一處理 AppException
│   │   └── logging.py                    # structlog 設定
│   ├── common/
│   │   ├── __init__.py
│   │   ├── auth.py                       # session 解析、current_user dep
│   │   ├── exceptions.py                 # AppException 基底 + 子類
│   │   ├── mixins.py                     # TimestampMixin
│   │   ├── schemas.py                    # DataResponse / PaginatedResponse / ErrorResponse
│   │   ├── enums.py                      # 共用 enum
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── slug.py                   # slugify 工具
│   ├── api/                              # 路由聚合層
│   │   ├── __init__.py
│   │   └── v1/
│   │       └── __init__.py               # 掛載所有 module routers，prefix=/api/v1
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── user.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   └── user_repository.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth_service.py
│   │   │   │   └── password_service.py
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   └── auth_router.py
│   │   │   └── schemas.py
│   │   └── library/
│   │       ├── __init__.py
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   ├── vendor.py
│   │       │   ├── product.py
│   │       │   ├── log_type.py
│   │       │   ├── field_schema.py
│   │       │   ├── parse_rule.py
│   │       │   └── sample_log.py
│   │       ├── repositories/
│   │       │   ├── __init__.py
│   │       │   ├── vendor_repository.py
│   │       │   ├── product_repository.py
│   │       │   ├── log_type_repository.py
│   │       │   ├── field_schema_repository.py
│   │       │   ├── parse_rule_repository.py
│   │       │   └── sample_log_repository.py
│   │       ├── services/
│   │       │   ├── __init__.py
│   │       │   ├── vendor_service.py
│   │       │   ├── product_service.py
│   │       │   ├── log_type_service.py
│   │       │   ├── field_schema_service.py
│   │       │   ├── parse_rule_service.py
│   │       │   ├── sample_log_service.py
│   │       │   └── library_overview_service.py
│   │       ├── routers/
│   │       │   ├── __init__.py
│   │       │   ├── vendor_router.py
│   │       │   ├── product_router.py
│   │       │   ├── log_type_router.py
│   │       │   ├── field_schema_router.py
│   │       │   ├── parse_rule_router.py
│   │       │   ├── sample_log_router.py
│   │       │   └── library_overview_router.py
│   │       └── schemas.py
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                       # client / mock_db / mock_cache fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── common/
│   │   ├── core/
│   │   └── modules/
│   │       ├── auth/
│   │       └── library/
│   └── integration/
│       ├── __init__.py
│       ├── conftest.py                   # 真實 DB / Redis fixture
│       └── modules/
│           └── library/
│               └── test_library_flow.py
├── web/                                  # Next.js 子專案
│   ├── app/                              # App Router
│   │   ├── layout.tsx                    # top nav + Copilot panel 預留
│   │   ├── page.tsx                      # / → redirect /library
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── library/
│   │   │   ├── page.tsx                  # 列表
│   │   │   ├── loading.tsx
│   │   │   └── [vendor]/[product]/page.tsx
│   │   ├── analyzer/
│   │   │   └── page.tsx                  # placeholder
│   │   └── copilot/
│   │       └── page.tsx                  # placeholder
│   ├── components/
│   │   ├── ui/                           # shadcn/ui
│   │   ├── layout/
│   │   │   ├── top-nav.tsx
│   │   │   └── copilot-panel.tsx         # v1 是空殼
│   │   └── library/
│   │       ├── vendor-group.tsx
│   │       ├── product-card.tsx
│   │       ├── filter-sidebar.tsx
│   │       ├── log-type-tabs.tsx
│   │       ├── field-table.tsx
│   │       ├── vrl-display.tsx           # v1 唯讀
│   │       └── sample-log-list.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── types.ts                  # 從 openapi.json 自動生
│   │   │   ├── client.ts                 # fetch wrapper
│   │   │   └── queries/                  # TanStack Query hooks
│   │   ├── auth.ts
│   │   └── utils.ts
│   ├── middleware.ts                     # auth guard
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── biome.json
│   └── next.config.ts
├── docs/
│   ├── LogScope_Design_Document_v1.2.html
│   └── superpowers/
│       └── specs/
│           └── 2026-05-08-foundation-and-library-min-design.md
├── docker-compose.yml                    # postgres + redis（v1 不開 clickhouse）
├── Dockerfile.api                        # 之後部署用
├── Makefile
├── pyproject.toml                        # uv
├── uv.lock
├── alembic.ini
├── ruff.toml
├── pyrightconfig.json
├── .env.example
└── README.md                             # 簡短：跑起來指引
```

---

## 3. 後端設計

### 3.1 主要技術

| 項目 | 選型 |
|---|---|
| Python | 3.13 |
| 套件管理 | uv |
| Web | FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 async |
| DB driver | asyncpg |
| Migration | Alembic（async template） |
| Cache / Session | Redis（redis.asyncio） |
| Logging | structlog（json） |
| Lint / Type | ruff、pyright |
| Test | pytest、pytest-asyncio、httpx AsyncClient |
| Auth | passlib（bcrypt）+ session id（UUID）+ Redis |

### 3.2 `app/main.py`

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
    return app


app = create_app()
```

### 3.3 `app/api/v1/__init__.py`

```python
from fastapi import APIRouter

from app.modules.auth.routers.auth_router import router as auth_router
from app.modules.library.routers.vendor_router import router as vendor_router
from app.modules.library.routers.product_router import router as product_router
from app.modules.library.routers.log_type_router import router as log_type_router
from app.modules.library.routers.field_schema_router import router as field_schema_router
from app.modules.library.routers.parse_rule_router import router as parse_rule_router
from app.modules.library.routers.sample_log_router import router as sample_log_router
from app.modules.library.routers.library_overview_router import router as library_overview_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(library_overview_router, prefix="/library", tags=["library"])
router.include_router(vendor_router, prefix="/library/vendors", tags=["library:vendor"])
router.include_router(product_router, prefix="/library", tags=["library:product"])
router.include_router(log_type_router, prefix="/library", tags=["library:log_type"])
router.include_router(field_schema_router, prefix="/library", tags=["library:field"])
router.include_router(parse_rule_router, prefix="/library", tags=["library:parse_rule"])
router.include_router(sample_log_router, prefix="/library", tags=["library:sample"])
```

### 3.4 共用元件

#### `app/common/mixins.py`

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

DB 端再透過 trigger 做安全網（見 §6 Migration）。

#### `app/common/exceptions.py`

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

`exception_handlers.py` 註冊 handler 把 `AppException` 序列成統一格式：

```json
{ "error": { "code": "not_found", "detail": "vendor not found" } }
```

#### `app/common/schemas.py`

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
```

### 3.5 Auth 流程

| 步驟 | 行為 |
|---|---|
| `POST /api/v1/auth/login` | body: `{email, password}`；驗證 bcrypt → 產生 `session_id (UUID hex)` → 寫入 Redis `session:{session_id}` = `user_id`，TTL 30 天 → 回 `Set-Cookie: session=<id>; HttpOnly; SameSite=Lax; Path=/`（`Secure` 旗標由 `SESSION_COOKIE_SECURE` 控制；cookie 名固定 `session` 不外露為 setting） |
| `POST /api/v1/auth/logout` | 從 cookie 取 session_id → `DEL session:{session_id}` → 回 `Set-Cookie: session=; Max-Age=0` |
| `GET /api/v1/auth/me` | dep `current_user` 解析 cookie → Redis 拿 user_id → DB 查 user 回傳 |

`current_user` dependency 同時是 receive auth gate：未登入觸發 `UnauthorizedError`。

註冊 / 忘記密碼 v1 不開放：admin 帳號透過 Alembic data migration 建出，密碼從 `LOGSCOPE_ADMIN_PASSWORD` 環境變數讀。

### 3.6 Repository / Service 介面風格

不寫抽象基底類，但每個 repository 至少提供 `get` / `list` / `create` / `update` / `delete`，service 是業務邏輯入口：

```python
class VendorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> Vendor | None: ...
    async def list(self, *, status: str | None = None) -> list[Vendor]: ...
    async def create(self, data: VendorCreate, *, created_by: UUID) -> Vendor: ...
    async def update(self, vendor: Vendor, data: VendorUpdate) -> Vendor: ...
    async def delete(self, vendor: Vendor) -> None: ...


class VendorService:
    def __init__(self, repo: VendorRepository) -> None:
        self._repo = repo

    async def create(self, data: VendorCreate, *, current_user: User) -> Vendor:
        existing = await self._repo.get_by_slug(data.slug)
        if existing:
            raise ConflictError(f"vendor slug already exists: {data.slug}")
        return await self._repo.create(data, created_by=current_user.id)
```

Router 透過 `Depends` 拿到 service 實例：

```python
async def get_vendor_service(
    session: AsyncSession = Depends(get_db_session),
) -> VendorService:
    return VendorService(VendorRepository(session))


@router.post("", response_model=DataResponse[VendorRead])
async def create_vendor(
    body: VendorCreate,
    service: VendorService = Depends(get_vendor_service),
    user: User = Depends(current_user),
) -> DataResponse[VendorRead]:
    vendor = await service.create(body, current_user=user)
    return DataResponse(data=VendorRead.model_validate(vendor))
```

---

## 4. 資料模型

所有表：UUID PK、`created_at` / `updated_at`（雙層保險：SQLAlchemy `onupdate=func.now()` + Postgres trigger）。

### 4.1 `users`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| email | VARCHAR(255) | UNIQUE NOT NULL |
| password_hash | VARCHAR(255) | bcrypt |
| display_name | VARCHAR(100) | NULL OK |
| is_active | BOOLEAN | default true |
| created_at, updated_at | timestamptz | |

### 4.2 `vendors`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL |
| slug | VARCHAR(100) | UNIQUE NOT NULL，URL-safe |
| website_url | TEXT | NULL OK |
| logo_url | TEXT | NULL OK |
| status | VARCHAR(20) | NOT NULL，`active` / `inactive`，default `active` |
| created_by | UUID | FK → users.id |
| created_at, updated_at | timestamptz | |

註：文件 ERD 寫 `VENDOR.category`，但用戶在 Q5(2) 選 `PRODUCT.category`。本 spec 不在 vendor 加 category。

### 4.3 `products`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| vendor_id | UUID | FK → vendors.id NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| slug | VARCHAR(100) | NOT NULL，於同 vendor 內 unique |
| version | VARCHAR(50) | NULL OK |
| description | TEXT | |
| deploy_type | VARCHAR(50) | `cloud` / `on_prem` / `hybrid` / NULL |
| category | VARCHAR(50) | `network` / `endpoint` / `auth` / `other`（供 Library sidebar 篩選） |
| doc_url | TEXT | |
| status | VARCHAR(20) | NOT NULL，`active` / `inactive`，default `active` |
| created_by | UUID | FK → users.id |
| created_at, updated_at | timestamptz | |

Index：`UNIQUE (vendor_id, slug)`、`(category)`。

### 4.4 `log_types`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| product_id | UUID | FK → products.id NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| slug | VARCHAR(100) | NOT NULL，於同 product 內 unique |
| format | VARCHAR(20) | `syslog` / `json` / `cef` / `leef` / `csv` / `other` |
| transport | VARCHAR(20) | NULL OK，`syslog_udp` / `syslog_tcp` / `http` / `file` / `other` |
| status | VARCHAR(20) | NOT NULL，**v1 僅 `draft` / `published`** |
| source | VARCHAR(20) | NOT NULL，**v1 僅 `manual`**，default `manual` |
| current_parse_rule_id | UUID | FK → parse_rules.id，NULL OK；指向「目前 active 版本」 |
| description | TEXT | |
| published_at | timestamptz | NULL OK，publish 動作時填入 |
| created_by | UUID | FK → users.id |
| created_at, updated_at | timestamptz | |

Index：`UNIQUE (product_id, slug)`、`(status)`。

**循環 FK 處理**：`log_types.current_parse_rule_id` → `parse_rules.id`，而 `parse_rules.log_type_id` → `log_types.id`。Migration 流程：先建 `log_types`（不含 FK constraint）、再建 `parse_rules`、最後 ALTER ADD constraint。SQLAlchemy 用 `ForeignKey(..., use_alter=True, name="fk_log_types_current_parse_rule")`。

### 4.5 `field_schemas`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| log_type_id | UUID | FK → log_types.id NOT NULL |
| field_name | VARCHAR(100) | NOT NULL |
| field_type | VARCHAR(20) | `string` / `int` / `float` / `bool` / `timestamp` / `ip` / `object` / `array` |
| description | TEXT | |
| is_required | BOOLEAN | default false |
| is_identifier | BOOLEAN | default false（Library 詳情頁紫色標籤） |
| example_value | TEXT | |
| sort_order | INT | default 0，前端依此排序 |
| created_at, updated_at | timestamptz | |

Index：`UNIQUE (log_type_id, field_name)`、`(log_type_id, sort_order)`。

### 4.6 `parse_rules`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| log_type_id | UUID | FK → log_types.id NOT NULL |
| version | INT | NOT NULL，於同 log_type 內遞增（v1, v2, ...） |
| vrl_code | TEXT | NOT NULL |
| engine_version | VARCHAR(10) | NOT NULL，`0.25` 或 `0.32`（雙引擎都支援） |
| status | VARCHAR(20) | NOT NULL，`draft` / `published`，default `draft` |
| notes | TEXT | 版本備註 |
| created_by | UUID | FK → users.id |
| created_at, updated_at | timestamptz | |

Index：`UNIQUE (log_type_id, version)`、`(log_type_id, status)`。

### 4.7 `sample_logs`

| 欄位 | 型別 | 備註 |
|---|---|---|
| id | UUID | PK |
| log_type_id | UUID | FK → log_types.id NOT NULL |
| raw_log | TEXT | NOT NULL |
| label | VARCHAR(20) | NOT NULL，`normal` / `edge_case` / `error`，default `normal` |
| description | TEXT | |
| added_by | UUID | FK → users.id |
| created_at, updated_at | timestamptz | |

Index：`(log_type_id)`。

### 4.8 ParseRule 版本與 Publish 流程

**設計原則**：
- `parse_rules` row 一旦 `status = published` 就是不可變快照（PATCH 拒絕）
- `log_types.current_parse_rule_id` 永遠指向「目前 active 的版本」（draft 或 published 都算）
- `log_types.status` 與 `log_types.current_parse_rule_id` 指到的 row 的 status 同步維護（publish flow 一起更新）

**動作 1：建新草稿版本**

`POST /api/v1/library/log_types/{id}/parse_rules` body `{vrl_code, engine_version, notes?}`
1. 算 `new_version = max(existing.version) + 1`（無則 1）
2. INSERT `parse_rules` row：`status = 'draft'`、`version = new_version`、其餘照 body
3. UPDATE `log_types`：`current_parse_rule_id = new.id`、`status = 'draft'`（因為 current 現在是 draft）
4. 全程一個 transaction

**動作 2：編輯現有草稿**

`PATCH /api/v1/library/parse_rules/{id}` body `{vrl_code?, engine_version?, notes?}`
- 限 `status = 'draft'` 才允許；published row PATCH 回 409

**動作 3：Publish 當前草稿**

`POST /api/v1/library/log_types/{id}/publish`
- 取 `log_types.current_parse_rule_id` 指到的 PARSE_RULE row
- 若無 current → 422 `no parse rule to publish`
- 若該 row `status = 'published'` → 409 `already published`
- 若該 row `status = 'draft'`：UPDATE `parse_rules.status = 'published'`、UPDATE `log_types.status = 'published'`、`log_types.published_at = now()`

**結果**：`parse_rules` 表會累積一個 LOG_TYPE 的全部歷史版本（v1 published、v2 published、v3 draft 等），`current_parse_rule_id` 永遠指最新一筆。

---

## 5. API 規格

所有 endpoint 都在 `/api/v1` prefix 下，回傳格式統一 `DataResponse<T>` 或 `PaginatedResponse<T>`。

### 5.1 Auth

| Method | Path | 說明 |
|---|---|---|
| POST | `/auth/login` | body: `{email, password}` |
| POST | `/auth/logout` | 清除 session |
| GET | `/auth/me` | 回傳當前 user |

### 5.2 Library Overview（給列表頁用的聚合資料）

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/overview` | 回傳 vendor 分組的 product list，每 product 包含 log_type 計數、status 彙總、`is_empty` 標記（沒任何 log_type）。可帶 query：`?status=published&category=network&q=palo`。多個篩選用 **AND**（同時滿足），`q` 是 vendor.name / product.name 的 case-insensitive substring 匹配 |

回傳結構（簡化）：
```json
{
  "data": [
    {
      "vendor": { "id": "...", "name": "Palo Alto Networks", "slug": "palo-alto", "logo_url": null },
      "products": [
        {
          "id": "...", "name": "PAN-OS", "slug": "pan-os",
          "category": "network", "status": "active",
          "log_type_counts": { "total": 5, "published": 5, "draft": 0 },
          "is_empty": false
        }
      ]
    }
  ]
}
```

### 5.3 Vendor

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/vendors` | list；query：`?status=&q=` |
| GET | `/library/vendors/{slug}` | by slug |
| POST | `/library/vendors` | body: `{name, slug?, website_url?, logo_url?, status?}`，slug 若略則由 name slugify |
| PATCH | `/library/vendors/{id}` | partial update |
| DELETE | `/library/vendors/{id}` | 若旗下有 product → 409 |

### 5.4 Product

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/vendors/{vendor_slug}/products` | list |
| GET | `/library/vendors/{vendor_slug}/products/{product_slug}` | 詳情，**回傳 nested**：product 本身 + `log_types[]`，每個 log_type 含 `current_parse_rule`、`field_schemas[]`、`sample_logs[]`（給詳情頁一次取完） |
| POST | `/library/vendors/{vendor_slug}/products` | body: 同欄位 |
| PATCH | `/library/products/{id}` | partial update |
| DELETE | `/library/products/{id}` | 若旗下有 log_type → 409 |

### 5.5 Log Type

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/products/{product_id}/log_types` | list |
| GET | `/library/log_types/{id}` | 詳情，含 fields / current_parse_rule / sample_logs |
| POST | `/library/products/{product_id}/log_types` | body: `{name, slug?, format, transport?, description?}` |
| PATCH | `/library/log_types/{id}` | partial update |
| DELETE | `/library/log_types/{id}` | cascade 刪掉旗下 fields / parse_rules / samples |
| POST | `/library/log_types/{id}/publish` | 把 current 的 draft parse_rule 升為 published（流程見 §4.8） |

### 5.6 Field Schema

| Method | Path | 說明 |
|---|---|---|
| PUT | `/library/log_types/{id}/fields` | body: `{fields: [...]}`，整批覆蓋（先 delete 後 insert，包在 transaction） |

### 5.7 Parse Rule

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/log_types/{id}/parse_rules` | list 所有版本 |
| GET | `/library/parse_rules/{id}` | 單一版本 |
| POST | `/library/log_types/{id}/parse_rules` | body: `{vrl_code, engine_version, notes?}`；自動 `version = max + 1`、`status = draft`，並把 log_type.current_parse_rule_id 指向新 row |
| PATCH | `/library/parse_rules/{id}` | 限 `status == draft` 才允許改 |

### 5.8 Sample Log

| Method | Path | 說明 |
|---|---|---|
| GET | `/library/log_types/{id}/samples` | list |
| POST | `/library/log_types/{id}/samples` | body: `{raw_log, label?, description?}` |
| DELETE | `/library/samples/{id}` | |

---

## 6. Migration

### 6.1 Alembic 設置

- 用 `alembic init -t async` 建 async 模板
- `alembic/env.py` 從 `app.core.config.settings.database_url` 取 URL
- env.py 自動 import 所有 models（透過 `app.modules.library.models import *`、`app.modules.auth.models import *`）讓 autogenerate 能掃描

### 6.2 第一個 Migration（手動撰寫，不靠 autogenerate）

順序：

1. 建表（依 FK 依賴）：`users` → `vendors` → `products` → `log_types`（不含 `current_parse_rule_id` 約束） → `parse_rules` → `field_schemas` → `sample_logs`
2. 為 `log_types` ALTER ADD COLUMN `current_parse_rule_id UUID` + FK constraint（解循環）
3. 建立 `set_updated_at()` PL/pgSQL function
4. 為每張有 `updated_at` 的表建 BEFORE UPDATE trigger
5. Seed admin user：用 env var `LOGSCOPE_ADMIN_EMAIL` / `LOGSCOPE_ADMIN_PASSWORD` 計算 bcrypt hash 後 insert

### 6.3 共用 helper（在 `app/alembic/helpers.py`）

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
```

`set_updated_at()` 在第一個 migration 建立一次：

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 7. 前端設計

### 7.1 主要技術

| 項目 | 選型 |
|---|---|
| 框架 | Next.js 14+ App Router |
| 語言 | TypeScript |
| 樣式 | Tailwind + shadcn/ui |
| Server state | TanStack Query v5 |
| Client state | v1 不引入；之後 Copilot panel 開放時再決定（Zustand 或 Context） |
| API 型別 | openapi-typescript（`npm run gen:api` 從 `/openapi.json` 產出） |
| Lint / Format | biome |

### 7.2 全站 Layout

`web/app/layout.tsx`：

```
┌─────────────────────────────────────────────────────────────┐
│ TopNav: [LogScope]   Library | Analyzer* | Copilot*    User │
├─────────────────────────────────┬───────────────────────────┤
│                                 │ Copilot panel             │
│ <main>                          │ (固定右側、可收合，        │
│   ...page content...            │  v1 顯示「即將開放」)      │
│                                 │                           │
│                                 │                           │
└─────────────────────────────────┴───────────────────────────┘
```

Copilot panel：
- 預設**收合**，只顯示 toggle button（fixed 在右下或 nav 上的 ✦ 按鈕）
- 展開時 panel 寬約 380px，用 CSS transition
- v1 內容是空殼：標題「Copilot」+ 訊息「將於 spec D 開放」+ disabled chat input

### 7.3 認證

- `web/middleware.ts`：未登入訪問受保護路由 → redirect `/login?next=<path>`
- `/login` 表單成功後：依 `next` 跳回，否則去 `/library`
- 已登入時訪問 `/login` → redirect `/library`
- Server component 透過 `cookies()` 拿 `session` 後直接 fetch backend `/auth/me` 驗證；client component 透過 TanStack Query

### 7.4 頁面

#### `/`（root）
- Server component，redirect 到 `/library`

#### `/login`
- Email + password form
- 失敗顯示 inline error
- 成功 redirect

#### `/library`（列表頁）
- Server component 預先 fetch `/library/overview`（帶上 query 條件）
- 左側 sidebar：
  - `Log 類型`：全部 / network / endpoint / auth / other（從 `category` 來，含計數）
  - `狀態`：published / draft / 未建庫（`is_empty`）
- Vendor 分組顯示 product cards
- Product card 三種樣式：
  - `published`（log_type 全 published）
  - `draft`（有 draft）
  - `未建庫`（`is_empty`，虛線邊框）
- 「新增」按鈕 → modal，建立 Vendor 或 Product（v1 簡單表單）
- 「✦ AI 建庫」按鈕：disabled，hover 顯示「將於 spec E 開放」
- 空狀態：當完全無資料時顯示置中訊息「還沒有任何 vendor，從右上「新增」開始」

#### `/library/[vendor]/[product]`（詳情頁）
- Server component fetch nested product detail
- Hero 區：vendor avatar（首字）+ product name + version + status pill + meta（更新時間、log type 數、來源）
- Log Type tabs：水平 tabs，切換時更新下方內容（client component handle 切換）
- 欄位表：sort_order 排序，identifier 欄位紫色標籤
- VRL 區塊：唯讀 code block 顯示 current_parse_rule.vrl_code，含 version / engine_version
  - 「載入 Analyzer」按鈕：disabled「Spec C」
  - 「編輯」按鈕：disabled「Spec C」
- Sample logs 區塊：list 顯示 raw_log + label
  - 「在 Analyzer 試打」按鈕：disabled「Spec C」
- 右側 Copilot panel 卡片：v1 是空殼

#### `/analyzer`、`/copilot`
- 簡單 placeholder 頁面：「即將於 spec C / D 開放」

### 7.5 API client 與型別

- `npm run gen:api` 跑 `openapi-typescript http://localhost:8000/openapi.json -o lib/api/types.ts`
- `lib/api/client.ts`：`fetch` wrapper，預設 `credentials: 'include'`
- `lib/api/queries/`：每個資源一個檔，匯出 TanStack Query hooks
  - 例：`useLibraryOverview(filters)`、`useProductDetail(vendor, product)`、`useCreateVendor()`

---

## 8. 測試

### 8.1 結構

```
tests/
├── conftest.py
├── unit/
│   ├── common/
│   │   └── test_mixins.py
│   ├── core/
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   └── test_exception_handlers.py
│   └── modules/
│       ├── auth/
│       │   ├── test_auth_service.py
│       │   ├── test_password_service.py
│       │   └── test_auth_router.py
│       └── library/
│           ├── test_vendor_service.py
│           ├── test_product_service.py
│           ├── test_log_type_service.py     # 含 publish 流程
│           ├── test_parse_rule_service.py
│           ├── test_field_schema_service.py
│           ├── test_sample_log_service.py
│           ├── test_library_overview_service.py
│           └── test_*_router.py
└── integration/
    ├── conftest.py
    └── modules/
        └── library/
            └── test_library_flow.py
```

### 8.2 AAA pattern（Arrange–Act–Assert）— 強制風格

範例（仿 growin）：

```python
class TestVendorServiceCreate:
    """Tests for VendorService.create()."""

    async def test_create_returns_vendor_with_generated_slug(self):
        """Should auto-generate slug from name when slug omitted."""
        # Arrange
        service, mock_repo = _make_service(get_by_slug_returns=None)
        request = VendorCreate(name="Palo Alto Networks")
        user = _make_user()

        # Act
        result = await service.create(request, current_user=user)

        # Assert
        assert result.slug == "palo-alto-networks"
        mock_repo.create.assert_awaited_once()

    async def test_create_raises_conflict_when_slug_exists(self):
        """Should raise ConflictError when slug collides."""
        # Arrange
        existing = _make_vendor(slug="palo-alto-networks")
        service, _ = _make_service(get_by_slug_returns=existing)
        request = VendorCreate(name="Palo Alto Networks")

        # Act / Assert
        with pytest.raises(ConflictError):
            await service.create(request, current_user=_make_user())
```

每個測試三段註解 `# Arrange` / `# Act` / `# Assert` 必寫。

### 8.3 Conftest fixtures

`tests/conftest.py` 提供：
- `mock_db`、`mock_cache`：仿 growin 的 MagicMock + AsyncMock 組合
- `app`：呼叫 `create_app()`
- `client`：`AsyncClient(transport=ASGITransport(app=app))`，with no-op lifespan
- helper：`create_mock_db_for_single` / `_for_list` / `_for_side_effect`（給需要直接 mock SQLAlchemy session 的場景）

### 8.4 Integration test

`tests/integration/conftest.py`：
- 啟動 docker compose 的 postgres + redis（或假設 user 自己啟）
- 每個 test 用獨立 schema（或交易包覆 + rollback）
- 真實 Alembic upgrade head

`test_library_flow.py`：一條 happy path
1. POST `/auth/login`（admin）
2. POST 建 vendor、product、log_type、fields、parse_rule
3. POST publish
4. GET `/library/vendors/{slug}/products/{slug}` → 確認 nested 結構正確
5. GET `/library/overview` → 確認彙總計數正確

### 8.5 覆蓋率目標

- 每個 service method 至少 1 happy path + 1 edge case
- 每個 router 至少 1 success + 1 unauthorized + 1 validation error 測試
- Integration 至少跑 1 次完整流程

---

## 9. 本地開發

### 9.1 `docker-compose.yml`

只啟用 v1 需要的服務：

```yaml
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: logscope
      POSTGRES_PASSWORD: logscope
      POSTGRES_DB: logscope
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U logscope"]
      interval: 5s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

ClickHouse v1 不啟用（從 spec C 才加）。

### 9.2 `Makefile`

```makefile
.PHONY: setup up down migrate api web test test-int lint gen-api

setup:
	uv sync
	cd web && npm install

up:
	docker compose up -d

down:
	docker compose down

migrate:
	uv run alembic upgrade head

api:
	uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

test:
	uv run pytest tests/unit -v

test-int:
	uv run pytest tests/integration -v

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	cd web && npm run lint

gen-api:
	cd web && npx openapi-typescript http://localhost:8000/openapi.json -o lib/api/types.ts
```

### 9.3 `.env.example`

```
# DB / Redis
DATABASE_URL=postgresql+asyncpg://logscope:logscope@localhost:5432/logscope
REDIS_URL=redis://localhost:6379/0

# Session
SESSION_COOKIE_SECURE=false
SESSION_TTL_SECONDS=2592000

# Initial admin（migration 時 seed）
LOGSCOPE_ADMIN_EMAIL=admin@logscope.local
LOGSCOPE_ADMIN_PASSWORD=changeme

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 10. 驗收標準

- [ ] `make setup` → `make up` → `make migrate` → `make api` 與 `make web` 全部跑得起來
- [ ] http://localhost:3000 訪問時，未登入 redirect 到 `/login`
- [ ] 用 admin 帳號登入後 redirect 到 `/library`
- [ ] `/library` 在無資料時顯示空狀態
- [ ] 透過 curl 或前端 modal 建立完整的 Vendor → Product → LogType → Fields → ParseRule（draft）→ publish → SampleLog 後，詳情頁顯示完整資料
- [ ] Sidebar `category` 與 `status` 篩選器能正確過濾
- [ ] 「未建庫」product 顯示虛線邊框
- [ ] 詳情頁 Log Type tabs 切換正常
- [ ] VRL 區塊顯示 `version + engine_version`，「編輯」「載入 Analyzer」按鈕為 disabled
- [ ] Copilot panel 收合/展開動畫正常，內容為「即將於 spec D 開放」
- [ ] Top nav 的 Analyzer / Copilot tabs 為 disabled
- [ ] 登出後 cookie 清除、再訪問 `/library` 跳 `/login`
- [ ] `make test` 與 `make test-int` 全綠
- [ ] `make lint` 全綠
- [ ] OpenAPI 自動生成的型別檔同步前端
- [ ] DB 中所有表 `updated_at` 在 ORM 與 raw SQL 兩種更新路徑下都會自動刷新

---

## 11. 風險與待確認

| 議題 | 處理 |
|---|---|
| 文件 ERD 寫 `VENDOR.category`，但用戶在 Q5(2) 選 PRODUCT 層級 | 本 spec 採 PRODUCT.category 單值；vendor 不加 category |
| 文件 mockup 顯示 PAN-OS card 有兩個 tag（Network + Auth） | v1 採單值，UI 只顯示一個 tag；若日後要 multi-tag 改成 `categories text[]` 或 M2M |
| 循環 FK（log_types ↔ parse_rules） | Migration 內用 `use_alter=True` + 兩階段建 constraint |
| Library response cache（Redis） | v1 不做，待真有 latency 問題再加 |
| 文件 8.6 提到的 fingerprint 比對 / SSE streaming / pipeline queue | 全部留給後續 spec |
| Engine 版本同時支援 0.25 / 0.32 | DB 欄位 `engine_version` v1 已具備；實際載入哪個引擎是 spec C 的決定 |
| Alembic 與 ORM autogenerate 對 trigger 的支援 | 第一版 migration 手寫，避免 autogenerate 漏掉 trigger |

---

## 12. 後續 Spec 預告

| 編號 | 標題 | 摘要 |
|---|---|---|
| 2 | C — Analyzer | 整合 pyvrl-playground、三欄 UI、Library 比對列、雙向閉環、ClickHouse 開始寫入 parse 統計 |
| 3 | D — Copilot | SSE streaming chat、各頁面 prompt 注入、三技能、Copilot panel 真正開放 |
| 4 | E — LLM Pipeline | 爬取、草稿生成、Review 三欄 diff、`in_review` / `rejected` 狀態、`source = llm_generated` |
| 5 | 後續優化 | Library cache、fingerprint index、全文搜尋、Dashboard 頁、OAuth、Multi-tag |
