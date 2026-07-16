# Xtreme Motors

Sistema de gestão de estoque e vendas de veículos para a **Xtreme Motors**.
Desenvolvido em Python 3.12+, gerenciado com `uv` e estruturado como um
workspace [Polylith](https://polylith.gitbook.io/polylith) (namespace: `xtreme_system`).

## Negócio

- **Descrição**: plataforma interna para centralizar a operação da revenda, com gestão de estoque, compras, vendas, clientes, caixa e investidores.
- **Problema que resolve**: elimina o uso de planilhas e controles dispersos, reduz retrabalho e ajuda a manter estoque, vendas e financeiro consistentes entre si.

- API REST (JSON) com documentação Swagger em `/docs`
- Interface web com HTMX e Jinja2 para uso interno
- Autenticação JWT + argon2 com dois modos: Bearer token (API) e cookie httpOnly (UI)
- PostgreSQL via SQLAlchemy 2.0 + Alembic
- Deployável via Docker Compose

## Setup

### Opção 1: PostgreSQL via Docker (recomendado)

```bash
make db-up    # docker compose up -d (Postgres 16 na porta 5432)
```

### Opção 2: PostgreSQL via brew

```bash
brew services start postgresql@16    # ou a versão instalada
createuser -s postgres               # role usada na DATABASE_URL
createdb -O postgres xtreme          # database usada na DATABASE_URL
```

### Ambiente e dependências

```bash
uv sync              # instala dependências
make hooks           # instala git hooks (uv run pre-commit install)
cp .env.example .env # DATABASE_URL + AUTH_SECRET_KEY (veja abaixo)
make migrate         # aplica migrations do Alembic
```

### Chave de autenticação

Gere a chave JWT:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Preencha `AUTH_SECRET_KEY` no `.env` com o valor gerado.

### Usuário admin

```bash
uv run python development/create_admin.py <usuario> <senha>
```

Autentique em `POST /login` com `Content-Type: application/x-www-form-urlencoded`
(campos `username` e `password`). Use `Authorization: Bearer <token>` nas chamadas
seguintes.

## Rodando

```bash
make run  # uvicorn xtreme_system.api.core:app --host 0.0.0.0 --port 8000
```

Acesse `http://localhost:8000/docs` para o Swagger UI.

Autenticação dual:

- **JSON API**: Bearer token via cabeçalho `Authorization`
- **HTMX UI**: cookie httpOnly `access_token` (login em `/ui/login`, logout em `/ui/logout`)

## Comandos comuns

Use `make help` para a lista completa. Atalhos:

```bash
make format      # ruff format .
make lint        # ruff check + format --check, xenon, vulture, mypy
make test        # pytest
make test-postgres  # pytest usando TEST_DATABASE_URL e migrations Alembic
make watch       # rerun pytest on file change
make coverage    # pytest with coverage, fail under 75%
make ci          # lint + coverage
make pre-commit  # run all pre-commit hooks
make migrate     # alembic upgrade head
make revision m="msg"  # alembic revision --autogenerate
make run         # uvicorn xtreme_system.api.core:app
make db-up       # docker compose up -d (Postgres)
make db-down     # docker compose down
```

Comandos crus equivalentes:

```bash
uv run ruff format . --check    # ou `uv run ruff format .` para auto-fix
uv run ruff check .             # ou `uv run ruff check --fix .` para auto-fix
uv run mypy                     # strict mode, package xtreme_system
uv run xenon src bases components development projects  # complexidade
uv run vulture                  # detecção de código morto
uv run pytest
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/xtreme_test uv run pytest
```

## Estrutura do projeto

Workspace Polylith (`workspace.toml`):


| Pasta                       | Propósito                                                                                                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bases/xtreme_system/api/`  | App FastAPI, templates Jinja2, arquivos estáticos                                                                                                                            |
| `components/xtreme_system/` | Domínio: `auth`, `database`, `usuario`, `veiculo`, `cliente`, `venda`, `caixa`, `investidor`, `compra`, `custo_veiculo`, `perfil`, `crud` e submódulos de imagens/documentos |
| `projects/inventory_api/`   | Projeto deployável — monta os bricks Polylith                                                                                                                                |
| `development/`              | Scripts auxiliares: `create_admin.py`                                                                                                                                        |
| `tests/`                    | Suite de testes com SQLite in-memory                                                                                                                                         |
| `alembic/`                  | Configuração do Alembic + migrations em `versions/`                                                                                                                          |
| `docker-compose.yml`        | Serviço `db` (postgres:16) + `app`                                                                                                                                           |


Polylith namespace: `xtreme_system`. Cada componente (`auth`, `veiculo`, etc.)
é um brick independente importado via `from xtreme_system.<nome> import core`.

## Convenções do projeto

- Python 3.12+, gerenciado com `**uv**` — sempre `uv run ...`
- Polylith namespace é `xtreme_system` (underscore, não hífen)
- Adicione dependências com `uv add <pkg>` (ou `uv add --dev <pkg>` para dev deps)
- **Line length: 88** (ruff)
- **Sem comentários** a menos que essencial
- **ruff rule set**: A, ARG, B, C4, E, F, I, N, PL, PT, RET, RUF, SIM, UP, W (ignora PLR0913)
- Tests relaxam ruff: magic numbers (`PLR2004`) e `assert` (`S101`) são permitidos
- Mypy é **strict** e verifica apenas `xtreme_system` (não tests)
- **Sem importações** no `__init__.py` além do que é realmente exportado — mantenha mínimo
