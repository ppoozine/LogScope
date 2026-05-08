.PHONY: setup up down migrate api web dev web-build web-lint test test-int lint format gen-api

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

# Start backend + frontend together (with docker + migration)
# Logs are prefixed [api] / [web]; Ctrl+C stops both.
dev: up migrate
	@echo "==> Backend  http://localhost:8000  (docs: /docs)"
	@echo "==> Frontend http://localhost:3000"
	@echo "==> Ctrl+C 一次同時關掉兩邊"
	@trap 'echo; echo "Stopping..."; kill 0' INT TERM; \
	  uv run uvicorn app.main:app --reload --port 8000 2>&1 | sed -u 's/^/[api] /' & \
	  (cd web && npm run dev) 2>&1 | sed -u 's/^/[web] /' & \
	  wait

web-build:
	cd web && npm run build

web-lint:
	cd web && npm run lint

test:
	uv run pytest tests/unit -v

test-int:
	uv run pytest tests/integration -v

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	cd web && npm run lint

format:
	uv run ruff format .
	uv run ruff check . --fix
	cd web && npm run format

gen-api:
	cd web && npm run gen:api
