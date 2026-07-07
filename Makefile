.PHONY: help hooks format lint mypy-strict test watch coverage ci pre-commit

PYTHON := uv run python

help:
	@printf '%s\n' \
		'Targets:' \
		'  make hooks       Install pre-commit hooks' \
		'  make format      Format Python files with ruff' \
		'  make lint        Run ruff, xenon, vulture, and mypy' \
		'  make mypy-strict Run strict mypy on the xtreme_system package' \
		'  make test        Run pytest' \
		'  make watch       Rerun pytest when Python files change' \
		'  make coverage    Run pytest with coverage and fail under 75%' \
		'  make ci          Run lint and coverage' \
		'  make pre-commit  Run all pre-commit hooks'

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

mypy-strict:
	uv run mypy --strict src/xtreme_system

test:
	$(PYTHON) -m pytest tests/ -q

watch:
	uv run ptw --runner "python -m pytest tests/ -q"

coverage:
	$(PYTHON) -m pytest tests/ -q --cov=xtreme_system --cov-report=term-missing --cov-fail-under=75

ci: lint coverage

pre-commit:
	uv run pre-commit run --all-files
