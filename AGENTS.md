## Quality Checks

Run in this order (`ruff format` first — it can fix lint issues):

```bash
uv run ruff format . --check   # (or `uv run ruff format .` to auto-fix formatting)
uv run ruff check .             # (or `uv run ruff check --fix .` to auto-fix)
uv run mypy                     # strict mode, only checks `ad_intelligence` package
uv run xenon src                # complexity check, excludes `tests/`
uv run vulture                  # dead code detection
uv run pytest                   # -q is omitted here for full output on failure
```

Run all at once via pre-commit:

```bash
uv run pre-commit run --all-files
```

Install git hooks: `uv run pre-commit install`

## Running Tests

```bash
uv run pytest                          # all tests
uv run pytest tests/test_package.py    # single file
uv run pytest -k "test_name_pattern"   # single test
```

## Project Conventions

- Python 3.12+, managed with **`uv`** — every command is `uv run ...`
- Package lives under `src/ad_intelligence/` (underscore, not hyphen)
- Add dependencies with `uv add <pkg>` (or `uv add --dev <pkg>` for dev deps)
- **Line length: 88** (ruff enforces)
- **No comments** unless essential — the codebase uses zero comments
- **ruff rule set**: A, ARG, B, C4, E, F, I, N, PL, PT, RET, RUF, SIM, UP, W (ignores PLR0913)
- Tests relax ruff: magic numbers (`PLR2004`) and `assert` usage (`S101`) are allowed
- Mypy is **strict** and targets only `ad_intelligence` (not tests)
- **No imports** in `__init__.py` beyond what's actually exported — keep it minimal
