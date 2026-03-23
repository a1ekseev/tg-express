.PHONY: lint format typecheck test test-all check migrate migration

lint:
	cd src/backend && uv run --group lint ruff check app/ tests/

format:
	cd src/backend && uv run --group lint ruff format --check app/ tests/

typecheck:
	cd src/backend && uv run --group lint ty check app/

test:
	cd src/backend && uv run --group tests pytest tests/unit/

test-all:
	cd src/backend && uv run --group tests pytest

check: lint format typecheck test

migrate:
	cd src/backend && uv run alembic upgrade head

migration:
	cd src/backend && uv run alembic revision --autogenerate -m "$(name)"
