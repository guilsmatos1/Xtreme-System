# Xtreme System

Extreme system tooling and experiments. Python project managed with `uv`,
structured as a [Polylith](https://polylith.gitbook.io/polylith) workspace
(namespace: `xtreme_system`).

## Setup

```bash
uv sync              # install dependencies
make hooks            # install git hooks (uv run pre-commit install)
cp .env.example .env  # then fill in AUTH_SECRET_KEY
make migrate           # apply database migrations
```

`.env` precisa de `DATABASE_URL` e `AUTH_SECRET_KEY` (JWT), veja `.env.example`.
Gere a chave com `python -c "import secrets; print(secrets.token_hex(32))"`.
Crie o primeiro admin com `uv run python development/create_admin.py <usuario> <senha>`.
Autentique em `POST /login` e mande `Authorization: Bearer <token>`.

## Common tasks

Run `make help` for the full list. Shortcuts:

```bash
make format      # ruff format .
make lint        # ruff check + format --check, xenon, vulture, mypy
make test        # pytest
make watch       # rerun pytest on file change
make coverage    # pytest with coverage, fail under 75%
make ci          # lint + coverage
make pre-commit  # run all pre-commit hooks
make migrate     # alembic upgrade head
make revision m="msg"  # alembic revision --autogenerate
```

Equivalent raw commands, in order (`ruff format` first — it can fix issues
that would otherwise fail lint):

```bash
uv run ruff format . --check    # or `uv run ruff format .` to auto-fix
uv run ruff check .             # or `uv run ruff check --fix .` to auto-fix
uv run mypy                     # strict mode, checks the `xtreme_system` package only
uv run xenon src bases components development projects  # complexity check, thresholds in pyproject.toml
uv run vulture                  # dead code detection
uv run pytest                   # -q omitted here for full output on failure
```

## Running tests

```bash
uv run pytest                          # all tests
uv run pytest tests/test_package.py    # single file
uv run pytest -k "test_name_pattern"   # single test
```

## Project layout

Polylith workspace (see `workspace.toml`):

- `src/xtreme_system/` — package namespace root
- `components/`, `bases/`, `development/` — Polylith bricks and dev environment (scaffolded, currently empty)
- `tests/` — test suite

## Project Conventions

- Python 3.12+, managed with **`uv`** — every command is `uv run ...`
- Polylith namespace is `xtreme_system` (underscore, not hyphen)
- Add dependencies with `uv add <pkg>` (or `uv add --dev <pkg>` for dev deps)
- **Line length: 88** (ruff enforces)
- **No comments** unless essential — the codebase uses zero comments
- **ruff rule set**: A, ARG, B, C4, E, F, I, N, PL, PT, RET, RUF, SIM, UP, W (ignores PLR0913)
- Tests relax ruff: magic numbers (`PLR2004`) and `assert` usage (`S101`) are allowed
- Mypy is **strict** and targets only `xtreme_system` (not tests)
- **No imports** in `__init__.py` beyond what's actually exported — keep it minimal
