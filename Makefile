.PHONY: help hooks format lint test test-postgres test-e2e watch coverage ci pre-commit migrate revision run db-test

PYTHON := uv run python
PYTEST_ARGS ?= tests/ -q -n auto

help:
	@printf '%s\n' \
		'Targets:' \
		'  make hooks       Install pre-commit hooks' \
		'  make format      Format Python files with ruff' \
		'  make lint        Run ruff, pylint, xenon, vulture, and mypy' \
		'  make test        Run pytest against migrated Postgres' \
		'  make test-postgres  Run pytest against migrated Postgres' \
		'  make test-e2e    Run Playwright browser tests (headed)' \
		'  make watch       Rerun pytest when Python files change' \
		'  make coverage    Run pytest with coverage and fail under 75%' \
		'  make ci          Run lint and coverage' \
		'  make pre-commit  Run all pre-commit hooks' \
		'  make migrate     Apply alembic migrations (upgrade head)' \
		'  make revision m="msg"  Autogenerate an alembic migration' \
		'  make run         Run the API with uvicorn' \
		'  make db-test     Create the local xtreme_test database'

hooks:
	uv run pre-commit install

format:
	uv run ruff format .

lint:
	uv run ruff check .
	uv run ruff format . --check
	uv run pylint bases components development projects
	uv run xenon src bases components development projects
	uv run vulture
	uv run mypy
	uv run lint-imports

test: test-postgres

test-postgres: db-test
	TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme_test $(PYTHON) -m pytest $(PYTEST_ARGS)

test-e2e:
	$(PYTHON) -m pytest tests/e2e/ -q --browser chromium --headed -p pytest_playwright

test-e2e-headless:
	$(PYTHON) -m pytest tests/e2e/ -q --browser chromium -p pytest_playwright

watch:
	uv run ptw --runner "python -m pytest tests/ -q"

coverage:
	$(MAKE) test-postgres PYTHON="$(PYTHON)" PYTEST_ARGS="tests/ -q -n auto --cov=xtreme_system --cov-report=term-missing --cov-fail-under=75"

ci: lint coverage

pre-commit:
	uv run pre-commit run --all-files

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

run:
	uv run uvicorn xtreme_system.api.core:app --host 0.0.0.0 --port 8000 --proxy-headers

db-test:
	createdb -U postgres xtreme_test 2>/dev/null || true
