.PHONY: help \
        setup install install-fe \
        dev dev-all dev-be dev-fe \
        stop-all stop-be stop-fe \
        status logs logs-be logs-fe \
        api web web-build \
        test test-int test-fe test-fe-e2e \
        lint lint-fe fmt typecheck typecheck-fe \
        up down dev-stats migrate revision \
        gen-api build-engines

LOG_DIR := .runtime/logs

# ──────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────
help:
	@echo "Dev orchestration:"
	@echo "  dev-all     - start docker + backend + frontend (background, returns terminal)"
	@echo "  dev-be      - start backend only (uvicorn :8000, background)"
	@echo "  dev-fe      - start frontend only (next dev :3000, background)"
	@echo "  stop-all    - stop frontend + backend + docker"
	@echo "  stop-be     - stop backend"
	@echo "  stop-fe     - stop frontend"
	@echo "  status      - show what's running"
	@echo "  logs-be     - tail backend log"
	@echo "  logs-fe     - tail frontend log"
	@echo ""
	@echo "Foreground (block terminal, log streams interleaved):"
	@echo "  dev         - foreground uvicorn + next dev with [api]/[web] prefixes"
	@echo "  api         - foreground uvicorn only"
	@echo "  web         - foreground next dev only"
	@echo ""
	@echo "Docker:"
	@echo "  up          - docker compose up -d (postgres + redis only)"
	@echo "  dev-stats   - docker compose --profile stats up -d clickhouse (Stats feature)"
	@echo "  down        - docker compose down"
	@echo "  logs        - docker compose logs -f"
	@echo ""
	@echo "Install:"
	@echo "  setup       - uv sync + npm install"
	@echo "  install     - uv sync (backend)"
	@echo "  install-fe  - npm install (frontend)"
	@echo ""
	@echo "Test / quality:"
	@echo "  test        - pytest unit (backend)"
	@echo "  test-int    - pytest integration (requires up)"
	@echo "  test-fe     - vitest (frontend)"
	@echo "  test-fe-e2e - Playwright e2e (requires backend up)"
	@echo "  lint        - ruff + pyright (backend) + biome (frontend)"
	@echo "  lint-fe     - biome only"
	@echo "  fmt         - ruff format + biome format"
	@echo "  typecheck   - pyright (backend only)"
	@echo "  typecheck-fe- tsc --noEmit (frontend)"
	@echo ""
	@echo "Migrations / misc:"
	@echo "  migrate     - alembic upgrade head"
	@echo "  revision    - alembic revision -m \"...\""
	@echo "  gen-api     - regen frontend types from /openapi.json"

# ──────────────────────────────────────────────
# Install
# ──────────────────────────────────────────────
setup: install install-fe

install:
	uv sync

install-fe:
	cd web && npm install

# ──────────────────────────────────────────────
# Foreground dev (block terminal)
# ──────────────────────────────────────────────
api:
	uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

# Run backend + frontend together with prefixed logs; Ctrl+C stops both.
dev: up migrate
	@echo "==> Backend  http://localhost:8000  (docs: /docs)"
	@echo "==> Frontend http://localhost:3000"
	@echo "==> Ctrl+C 一次同時關掉兩邊"
	@trap 'echo; echo "Stopping..."; kill 0' INT TERM; \
	  uv run uvicorn app.main:app --reload --port 8000 2>&1 | sed -u 's/^/[api] /' & \
	  (cd web && npm run dev) 2>&1 | sed -u 's/^/[web] /' & \
	  wait

# ──────────────────────────────────────────────
# Background dev orchestration
# ──────────────────────────────────────────────
$(LOG_DIR):
	@mkdir -p $(LOG_DIR)

dev-all: up dev-stats migrate dev-be dev-fe
	@echo ""
	@echo "🚀 LogScope dev stack running (background)"
	@echo "  Backend:  http://localhost:8000/healthz   (docs: /docs)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Logs:     $(LOG_DIR)/{be,fe}.log"
	@echo ""
	@echo "  → make status     check what's up"
	@echo "  → make logs-be    tail backend log"
	@echo "  → make logs-fe    tail frontend log"
	@echo "  → make stop-all   stop everything"

dev-be: $(LOG_DIR)
	@if pgrep -f "uvicorn app.main" > /dev/null; then \
		echo "↻ Backend already running"; \
	else \
		echo "▶ Starting backend (uvicorn :8000)…"; \
		nohup uv run uvicorn app.main:app --reload --port 8000 \
			> $(LOG_DIR)/be.log 2>&1 & \
		sleep 2; \
		if curl -fs http://127.0.0.1:8000/healthz > /dev/null 2>&1; then \
			echo "  ✓ Backend ready at http://localhost:8000/healthz"; \
		else \
			echo "  ⚠ Backend booting (check 'make logs-be')"; \
		fi; \
	fi

dev-fe: $(LOG_DIR)
	@if pgrep -f "next-server" > /dev/null || pgrep -f "next dev" > /dev/null; then \
		echo "↻ Frontend already running"; \
	else \
		echo "▶ Starting frontend (next dev :3000)…"; \
		( cd web && nohup npm run dev > ../$(LOG_DIR)/fe.log 2>&1 & ); \
		sleep 4; \
		if curl -fs http://127.0.0.1:3000 > /dev/null 2>&1; then \
			echo "  ✓ Frontend ready at http://localhost:3000"; \
		else \
			echo "  ⚠ Frontend compiling (check 'make logs-fe')"; \
		fi; \
	fi

stop-all: stop-fe stop-be down
	@echo "🛑 LogScope dev stack stopped"

stop-be:
	@if pkill -f "uvicorn app.main" 2>/dev/null; then \
		echo "■ Backend stopped"; \
	else \
		echo "  Backend was not running"; \
	fi

stop-fe:
	@stopped=0; \
	pkill -f "next-server" 2>/dev/null && stopped=1; \
	pkill -f "next dev" 2>/dev/null && stopped=1; \
	pkill -f "node .*\.next" 2>/dev/null && stopped=1; \
	if [ $$stopped -eq 1 ]; then \
		echo "■ Frontend stopped"; \
	else \
		echo "  Frontend was not running"; \
	fi

status:
	@echo "Stack status:"
	@printf "  %-12s " "Backend"
	@if pgrep -f "uvicorn app.main" > /dev/null; then \
		if curl -fs http://127.0.0.1:8000/healthz > /dev/null 2>&1; then \
			echo "✓ healthy (http://localhost:8000)"; \
		else \
			echo "⚠ running but /healthz not responding"; \
		fi; \
	else \
		echo "✗ stopped"; \
	fi
	@printf "  %-12s " "Frontend"
	@if pgrep -f "next-server" > /dev/null || pgrep -f "next dev" > /dev/null; then \
		if curl -fs http://127.0.0.1:3000 > /dev/null 2>&1; then \
			echo "✓ healthy (http://localhost:3000)"; \
		else \
			echo "⚠ running but :3000 not responding"; \
		fi; \
	else \
		echo "✗ stopped"; \
	fi
	@printf "  %-12s " "Docker"
	@if docker compose ps --format json 2>/dev/null | grep -q '"State":"running"'; then \
		count=$$(docker compose ps --format json 2>/dev/null | grep -c '"Health":"healthy"'); \
		echo "✓ $$count containers healthy"; \
	else \
		echo "✗ stopped"; \
	fi

# ──────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────
up:
	docker compose up -d

dev-stats:
	docker compose --profile stats up -d clickhouse
	@echo "ClickHouse on :8123 (CLICKHOUSE_URL in .env.example is enabled by default)"

down:
	docker compose --profile stats down

logs:
	docker compose logs -f

logs-be:
	@touch $(LOG_DIR)/be.log
	tail -f $(LOG_DIR)/be.log

logs-fe:
	@touch $(LOG_DIR)/fe.log
	tail -f $(LOG_DIR)/fe.log

# ──────────────────────────────────────────────
# Test / quality
# ──────────────────────────────────────────────
test:
	uv run pytest tests/unit -v

test-int:
	uv run pytest tests/integration -v

test-fe:
	cd web && npm test

test-fe-e2e:
	cd web && npm run test:e2e

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	cd web && npm run lint

lint-fe:
	cd web && npm run lint

fmt:
	uv run ruff format .
	uv run ruff check . --fix
	cd web && npm run format

typecheck:
	uv run pyright

typecheck-fe:
	cd web && npx tsc --noEmit

# ──────────────────────────────────────────────
# Migrations
# ──────────────────────────────────────────────
migrate:
	uv run alembic upgrade head

revision:
	@read -p "Message: " msg; \
	uv run alembic revision -m "$$msg"

# ──────────────────────────────────────────────
# VRL engines (Rust + maturin)
# ──────────────────────────────────────────────
build-engines:
	cd engine/v25 && uv run maturin develop --release
	cd engine/v32 && uv run maturin develop --release

# ──────────────────────────────────────────────
# Misc
# ──────────────────────────────────────────────
web-build:
	cd web && npm run build

gen-api:
	cd web && npm run gen:api
