FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"

# Camada cacheada de dependências.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

# Código do workspace.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "xtreme_system.api.core:app", "--host", "0.0.0.0", "--port", "8000"]
