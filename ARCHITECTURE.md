# Arquitetura — Xtreme Motors

## Visão geral

O sistema é uma aplicação **FastAPI** monolítica organizada como workspace
**Polylith** (namespace `xtreme_system`). A mesma base de código expõe uma API
JSON (para integrações e Swagger) e uma interface web HTMX (para uso interno
no navegador). Banco de dados **PostgreSQL**, autenticação **JWT + argon2**,
migrations com **Alembic**.

```
Cliente (browser / API) → FastAPI (core.py)
                           │
                           ├── JSON API (Bearer token)
                           ├── HTMX UI  (cookie httpOnly)
                           │
                           ├── Middleware: CORS, request-id, error logging
                           ├── Auth: JWT + argon2 (PyJWT + pwdlib)
                           └── SQLAlchemy 2.0 → PostgreSQL
```

## Estrutura Polylith

| Camada     | Localização                  | Propósito |
|------------|------------------------------|-----------|
| `bases`    | `bases/xtreme_system/api/`   | Aplicação FastAPI — ponto de entrada, rotas, templates, estáticos |
| `components` | `components/xtreme_system/` | Lógica de domínio — um brick por contexto (auth, veiculo, venda, etc.) |
| `projects` | `projects/inventory_api/`    | Projeto deployável — monta `bases` + `components` via `hatch-polylith-bricks` |

Cada componente exporta sua API pública em um arquivo `core.py`. O import
segue o padrão:

```python
from xtreme_system.veiculo import core as veiculo
```

Não há acoplamento direto entre componentes — cada um define seus próprios
modelos SQLAlchemy, schemas Pydantic e funções CRUD. O arquivo `core.py` da
base orquestra as rotas e injeta dependências (sessão, auth e autorização) nos componentes.

## Camada API (`bases/xtreme_system/api/core.py`)

### App FastAPI

```python
app = FastAPI(title="Xtreme Motors")
```

- `CORSMiddleware` — permite todas as origens (`*`)
- Middleware `_request_id` — extrai ou gera `X-Request-ID`, disponível via `ContextVar`
- Middleware `_log_errors` — captura exceções não tratadas e registra com traceback
- Middleware `_rate_limit` — janela compartilhada em banco por IP: 5 tentativas/min em `/login` e `/ui/login`, 100 requests/min nas demais rotas (exceto `/health`, `/docs`, `/redoc`, `/openapi.json` e `/static/`); responde `429` com header `Retry-After`. A chave de cliente usa o IP do peer ASGI e não confia em `X-Forwarded-For` enviado pelo cliente. O estado fica em `rate_limit_state`, então o limite funciona entre workers. Buckets antigos são limpos periodicamente.
- Arquivos estáticos montados em `/static`
- Templates Jinja2 em `templates/`
- Raiz (`/`) redireciona para `/docs`

### Dependências de autenticação

```
oauth2_scheme (OAuth2PasswordBearer)  →  get_current_user  →  CurrentUser
                                                          →  require_admin → AdminUser
```

- `CurrentUser`: usuário autenticado (qualquer papel ativo)
- `AdminUser`: usuário com papel `admin` (herda de `CurrentUser`)
- Rotas de listagem/leitura exigem `CurrentUser`; mutações exigem `AdminUser`

### Endpoints JSON

| Rota | Métodos | Auth |
|------|---------|------|
| `POST /login` | — | Form OAuth2, retorna JWT |
| `/usuarios` | GET, POST, DELETE, POST `/{id}/senha` | Admin (exceto login) |
| `/investidores` | GET, POST, PATCH, DELETE | List/Get: CurrentUser, Mutate: Admin |
| `/veiculos` | GET, POST, PATCH, DELETE | idem |
| `/lancamentos-caixa` | GET, POST, PATCH, DELETE | idem |
| `/clientes` | GET, POST, PATCH, DELETE | idem |
| `/compras` | GET, POST, PATCH, DELETE | idem |
| `/vendas` | GET, POST, PATCH, DELETE | idem |
| `/auditoria` | GET | Admin |
| `/vendas/{id}/fechamento/preview` | GET | CurrentUser |
| `/vendas/{id}/fechamento` | POST | Admin |
| `/fechamentos-vendas` | GET | CurrentUser |
| `/fechamentos-vendas/{id}` | GET | CurrentUser |

### Fábrica de CRUD (`register_crud_routes`)

Os endpoints seguem um padrão gerado por `register_crud_routes(app, module, prefix, label, schemas, hooks)`:

```
GET    /{prefix}         → module.list_all(session)
GET    /{prefix}/{id}    → module.get(session, id)
POST   /{prefix}         → module.create(session, data)
PATCH  /{prefix}/{id}    → module.update(session, obj, data)
DELETE /{prefix}/{id}     → module.delete(session, obj)
```

A fábrica aceita hooks opcionais (`before_create`, `after_create`,
`before_update`, `after_update`, `before_delete`) para validação de FKs,
operações em cascata e regras de negócio específicas.

Usuários (`/usuarios`) e login são rotas manuais (não usam a fábrica), por
terem regras próprias (troca de senha, proteção contra auto-exclusão, etc.).

### Interface HTMX

Rotas sob `/ui/` servem HTML parcial com Jinja2, usando cookie `access_token`
para autenticação (httpOnly, mesmo segredo JWT) e `perfil` para autorização de páginas:

| Rota | Descrição |
|------|-----------|
| `/ui/login` | GET exibe formulário; POST autentica e seta cookie |
| `/ui/logout` | Limpa o cookie e redireciona |
| `/ui/veiculos` | Listagem e edição de veículos |
| `/ui/clientes` | Redireciona para `/ui/clientes/compradores` |
| `/ui/clientes/compradores` | Listagem de clientes com vendas registradas |
| `/ui/clientes/vendedores` | Listagem de clientes com compras registradas |
| `/ui/compras` | Gestão de compras e comprovantes |
| `/ui/custos-veiculos` | Custos operacionais de veículos |
| `/ui/vendas` | Listagem de vendas |
| `/ui/vendas/{id}/fechamento` | Modal HTMX de fechamento financeiro |
| `/ui/fechamentos-vendas/{id}` | Modal HTMX de detalhe do fechamento |
| `/ui/perfis` | Gestão de perfis de acesso |
| `/ui/usuarios` | Gestão de usuários |
| `/ui/usuarios/{id}/editar` | Edição de usuário e vínculo com perfil |
| `/ui/usuarios/{id}/perfil` | Alteração rápida do perfil do usuário |
| `/ui/conta` | Perfil do usuário logado + troca da própria senha |
| `/ui/investidores[/{id}/lancamentos]` | Gestão de investidores + lançamentos de caixa por investidor |

Templates em `bases/xtreme_system/api/templates/`, estáticos em `static/`.

O acesso de usuário comum na UI é controlado por `perfil.pode_acessar`; `admin`
é exceção e pode entrar em qualquer página.

Dentro de uma página, o perfil também pode restringir **campos** e **operações**
via `Perfil.restricoes` (JSON por página): `perfil.pode_ver_campo` (denylist —
visível por padrão, o admin marca o que ocultar) controla campos sensíveis na
UI e na exportação CSV, e `perfil.pode_operacao` (allowlist — negado por padrão
para não-admin)
controla ações de escrita. `admin` sempre passa em ambos. Ambos são globals do
Jinja (`deps.py`) e `require_operacao(pagina, operacao)` é uma dependency
factory para bloquear no servidor, não só esconder no HTML.

Aplicado nas 6 páginas (`veiculos`, `investidores`, `clientes`, `compras`,
`custos-veiculos`, `vendas`). Dois caminhos de implementação:
- **Rotas geradas pela fábrica CRUD** (`crud_ui/routes.py`): passe
   `editar_dep`/`excluir_dep` (dependencies que substituem `UIAdmin`),
   `pagina` e `campos_form_map` (campo interno → nome do input HTML) para
   `register_crud_ui_routes`. A fábrica injeta `user` no contexto do form e
   remove do payload, antes da validação, os campos que o perfil não pode ver
   — ver `custos_veiculos.py`, `compras.py`, `vendas.py`, `clientes.py`.
- **Rotas manuais** (sem fábrica): trocar a dependency `UIAdmin` por
  `Depends(require_operacao(pagina, operacao))` diretamente — ver
  `investidores.py` e as rotas de editar/excluir de `veiculos.py` (que
  também precisou de `register_edit=False`/`register_delete=False` na
  fábrica por já ter overrides próprios de create/update).

Operações específicas fora do CRUD padrão também usam `require_operacao`:
`excluir_comprovante` (compras), `excluir_documento` (clientes) e `fechar`
(fechamento de venda, que também oculta Lucro Líquido/Participação por
investidor via `pode_ver_campo` quando o perfil não tem esses campos
liberados).

## Componentes de domínio (`components/xtreme_system/`)

| Componente | Entidade(s) | Descrição |
|------------|-------------|-----------|
| `auth/` | — (JWT, argon2) | `create_access_token`, `decode_token`, `verify_password`, `hash_password`, `Settings` (`AUTH_SECRET_KEY`) |
| `database/` | — (SQLAlchemy) | Engine + session factory configurados via `DATABASE_URL`, dependency `get_session` |
| `perfil/` | `Perfil` | Permissões por página da UI, listas permitidas e checagem de acesso; `restricoes` para campos ocultos e operações permitidas por página, incluindo `debitos` em veículos |
| `usuario/` | `Usuario` | `id`, `username`, `senha_hash`, `papel` (admin/funcionario), `ativo`, `perfil_id` |
| `investidor/` | `Investidor` | `id`, `nome` |
| `veiculo/` | `Veiculo` | `modelo`, `placa`, `tipo` (carro/moto), `ano`, `km`, `preco`, `status`, `tipo_entrada`, `revisao`, FK para `investidor` |
| `cliente/` | `Cliente` | `nome`, `documento`, `tipo` (PF/PJ), `cidade`, `estado` |
| `venda/` | `Venda` | `cliente_id`, `veiculo_id`, `data_venda`, `valor_venda`, `valor_entrada`, `forma_pagamento`, `parcelas`, `status`, `observacoes` |
| `caixa/` | `LancamentoCaixa` | `investidor_id`, `tipo` (aporte/retirada), `valor`, `descricao`, `origem` (manual/veiculo) |
| `compra/` | `Compra` | Compras de veículos, status e comprovantes |
| `custo_veiculo/` | `CustoVeiculo` | Custos operacionais por veículo, sem impacto em saldo de investidor |
| `fechamento_venda/` | `FechamentoVenda`, `ParticipacaoFechamentoVenda` | Fecha financeiramente vendas concluídas, calcula lucro líquido, persiste snapshots e gera lançamentos automáticos no caixa |
| `crud/` | — | Helpers CRUD compartilhados |
| `documento_veiculo/` | — | Documentos de veículos (arquivos/imagens) |
| `documento_procuracao/` | — | Documentos de procuração de veículos |
| `imagem_veiculo/` | — | Imagens de veículos |
| `imagem_comprovante_venda/` | — | Comprovantes de venda |
| `imagem_comprovante_compra/` | — | Comprovantes de compra |
| `imagem_documento_cliente/` | — | Documentos de clientes |

Cada componente segue o mesmo padrão interno: `core.py` exporta as funções
públicas (CRUD e helpers), `models.py` define os modelos SQLAlchemy, e
`schemas.py` (quando presente) define os schemas Pydantic.

## Banco de dados

- **SQLAlchemy 2.0** com engine síncrono (`psycopg`)
- `DATABASE_URL` configurada via `.env` (ex: `postgresql+psycopg://postgres:postgres@localhost:5432/xtreme`)
- Sessão por request via `get_session` dependency
- **Alembic** para migrations em `alembic/versions/`
  - `make migrate` → `alembic upgrade head`
  - `make revision m="msg"` → autogenerate
- Testes usam **SQLite in-memory** (`sqlite://`) via fixture `db_session`, sem dependência de Postgres

## Autenticação

### JWT (PyJWT)

- `create_access_token(username, papel)` → token com expiração configurável
- `decode_token(token)` → payload com `sub` (username) e `papel`
- Segredo: `AUTH_SECRET_KEY` do `.env`

### Argon2 (pwdlib)

- `hash_password(senha)` → hash argon2id
- `verify_password(senha, hash)` → bool

### Dois modos de transporte

| Modo | Transporte | Uso |
|------|------------|-----|
| **API JSON** | Header `Authorization: Bearer <token>` | Integrações, Swagger UI |
| **HTMX UI** | Cookie `access_token` httpOnly | Navegador, formulários internos |

Ambos usam o mesmo segredo e payload JWT. A diferença está apenas no
transporte e na extração do token.

## Deploy

O projeto deployável está em `projects/inventory_api/`. O `pyproject.toml`
usa `hatch-polylith-bricks` para montar o ambiente a partir dos bricks:

```
[build-system]
requires = ["hatchling", "hatch-polylith-bricks"]
build-backend = "hatchling.build"
```

Docker Compose (`docker-compose.yml`) define dois serviços:
- `db` — `postgres:16`
- `app` — `xtreme_system.api.core:app` na porta 8000

## Testes

- Suite em `tests/` organizada por componente
- **pytest** com fixture `db_session` — recria tabelas em SQLite in-memory a cada teste
- Cobertura via `pytest-cov`, fail under 75% (`make coverage`)
- Watch mode: `make watch` (usa `pytest-watch`)
- Lint + coverage em CI: `make ci`

Para rodar:

```bash
uv run pytest                          # todos os testes
uv run pytest tests/test_package.py    # arquivo específico
uv run pytest -k "test_name_pattern"   # teste específico
```
