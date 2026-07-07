# Ad Intelligence

Python project managed with `uv`.

## Development

Install dependencies:

```bash
uv sync
```

Run the quality checks:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv run xenon src
uv run vulture
```

Install the Git hooks:

```bash
uv run pre-commit install
```

Run all pre-commit hooks manually:

```bash
uv run pre-commit run --all-files
```

Format code:

```bash
uv run ruff format .
uv run ruff check --fix .
```
