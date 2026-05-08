.PHONY: setup up down migrate api web web-build web-lint test test-int lint format gen-api

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
