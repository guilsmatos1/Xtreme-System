.PHONY: help hooks format lint test test-postgres watch coverage ci pre-commit migrate revision run db-up db-down

PYTHON := uv run python

help:
	@printf '%s\n' \
		'Targets:' \
		'  make hooks       Install pre-commit hooks' \
		'  make format      Format Python files with ruff' \
		'  make lint        Run ruff, xenon, vulture, and mypy' \
		'  make test        Run pytest' \
		'  make test-postgres  Run pytest against migrated Postgres' \
		'  make watch       Rerun pytest when Python files change' \
		'  make coverage    Run pytest with coverage and fail under 75%' \
		'  make ci          Run lint and coverage' \
		'  make pre-commit  Run all pre-commit hooks' \
		'  make migrate     Apply alembic migrations (upgrade head)' \
		'  make revision m="msg"  Autogenerate an alembic migration' \
		'  make run         Run the API with uvicorn' \
		'  make db-up       Start the local Postgres container' \
		'  make db-down     Stop the local Postgres container'

hooks:
	uv run pre-commit install

format:
	uv run ruff format .

lint:
	uv run ruff check .
	uv run ruff format . --check
	uv run xenon src bases components development projects
	uv run vulture
	uv run mypy

test:
	$(PYTHON) -m pytest tests/ -q

test-postgres:
	TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme_test $(PYTHON) -m pytest tests/ -q

watch:
	uv run ptw --runner "python -m pytest tests/ -q"

coverage:
	$(PYTHON) -m pytest tests/ -q --cov=xtreme_system --cov-report=term-missing --cov-fail-under=75

ci: lint coverage

pre-commit:
	uv run pre-commit run --all-files

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

run:
	uv run uvicorn xtreme_system.api.core:app --host 0.0.0.0 --port 8000 --proxy-headers

db-up:
	docker compose up -d

db-down:
	docker compose down
