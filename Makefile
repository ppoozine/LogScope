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
