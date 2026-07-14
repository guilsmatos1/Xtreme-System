# Graph Report - xtreme-system  (2026-07-13)

## Corpus Check
- 130 files · ~47,918 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1173 nodes · 2445 edges · 107 communities (99 shown, 8 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 152 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e29d9311`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- htmx.min.js
- create_test_engine
- test_ui.py
- _found
- route_factories.py
- core.py
- core.py
- setup.py
- Usuario
- veiculos.py
- Base
- API - Xtreme Motors
- core.py
- usuarios.py
- Tabelas
- Arquitetura — Xtreme Motors
- core.py
- Design
- test_api_auth.py
- auditoria.py
- test_venda_whatsapp.py
- perfis.py
- core.py
- core.py
- core.py
- factories.py
- core.py
- core.py
- Validação de Uploads Implementation Plan
- Setup
- test_auditoria.py
- ui_login
- ui_dashboard
- core.py
- ui_configuracoes_salvar
- AGENTS.md
- core.py
- vendas.py
- test_auth.py
- env.py
- a1b2c3d4e002_add_imagem_comprovante_venda_table.py
- a1b2c3d4e004_add_debitos_to_venda.py
- a1b2c3d4e005_add_imagem_documento_cliente_table.py
- a1b2c3d4e006_add_imagem_comprovante_compra_table.py
- a1b2c3d4e009_normalize_imagem_veiculo_urls.py
- _UiCompatModule
- _ctx_form_cliente
- Page
- a1b2c3d4e001_rename_lancamento_caixa_to_lancamento_.py
- core.py
- __init__.py
- codebase-analysis.md
- agent-finish.sh
- inventory_api
- xtreme-system

## God Nodes (most connected - your core abstractions)
1. `_found()` - 32 edges
2. `create_test_engine()` - 29 edges
3. `ne()` - 28 edges
4. `_login_admin()` - 28 edges
5. `se()` - 27 edges
6. `ue()` - 27 edges
7. `He()` - 26 edges
8. `e()` - 25 edges
9. `Usuario` - 21 edges
10. `session()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_json_create_rolls_back_when_after_create_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_delete_rolls_back_when_before_delete_fails_after_writes()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_update_rolls_back_when_after_update_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `main()` --indirect_call--> `session()`  [INFERRED]
  development/create_admin.py → tests/test_crud.py
- `get_current_user()` --references--> `Usuario`  [EXTRACTED]
  bases/xtreme_system/api/deps.py → components/xtreme_system/usuario/core.py

## Import Cycles
- None detected.

## Communities (107 total, 8 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.06
Nodes (65): main(), Cria o primeiro admin: uv run python development/create_admin.py <user> <senha>., Engine, db_session(), Session, Sessão isolada com schema migrado em Postgres ou SQLite local., create_test_engine(), Helpers for test database bootstrap. (+57 more)

### Community 2 - "test_ui.py"
Cohesion: 0.07
Nodes (61): UploadFile, Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _validar_uploads(), _admin_headers(), client(), _FakeFile, _FakeUpload, _login_admin() (+53 more)

### Community 3 - "_found"
Cohesion: 0.11
Nodes (52): AdminUser, _found(), criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo(), health(), listar_auditoria(), listar_usuarios() (+44 more)

### Community 4 - "route_factories.py"
Cohesion: 0.09
Nodes (37): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _csv_response(), _delete_with_hook(), Any, FastAPI (+29 more)

### Community 5 - "core.py"
Cohesion: 0.09
Nodes (47): agregados_investidores(), create(), criar_lancamento_veiculo(), deletar_lancamento_veiculo(), delete(), _descricao_veiculo(), get(), LancamentoInvestimento (+39 more)

### Community 6 - "core.py"
Cohesion: 0.09
Nodes (44): create(), delete(), funil_status(), get(), list_all(), _mes_atual_inicio(), BaseModel, date (+36 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (39): get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError, _NaoAutorizadoError, CurrentUser, Depends, Exception (+31 more)

### Community 8 - "Usuario"
Cohesion: 0.11
Nodes (41): auditar(), Auditoria, AuditoriaRead, count(), _filtros(), get(), Any, BaseModel (+33 more)

### Community 9 - "veiculos.py"
Cohesion: 0.14
Nodes (40): Path, Shared helpers for HTMX route modules., _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_dir(), _atualizar_veiculo(), _criar_veiculo() (+32 more)

### Community 10 - "Base"
Cohesion: 0.10
Nodes (34): Base, get_session(), get_settings(), BaseSettings, Session, Configuração de banco: settings, engine, sessão e Base declarativa., Settings, create() (+26 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 12 - "core.py"
Cohesion: 0.16
Nodes (21): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+13 more)

### Community 13 - "usuarios.py"
Cohesion: 0.23
Nodes (20): _sort_key(), Form, HTMLResponse, Request, Response, SessionDep, UIAdmin, HTMX routes for usuarios. (+12 more)

### Community 14 - "Tabelas"
Cohesion: 0.10
Nodes (18): `cliente`, `compra`, `documento_veiculo`, Enums, `imagem_comprovante_compra`, `imagem_comprovante_venda`, `imagem_documento_cliente`, `imagem_veiculo` (+10 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.24
Nodes (16): Cliente, ClienteCreate, ClienteRead, ClienteUpdate, create(), delete(), get(), get_by_documento() (+8 more)

### Community 17 - "Design"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.27
Nodes (16): client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro() (+8 more)

### Community 19 - "auditoria.py"
Cohesion: 0.24
Nodes (15): _ctx_auditoria(), _nomes_usuarios(), _pretty(), Any, date, HTMLResponse, Request, Response (+7 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.36
Nodes (15): client(), _configurar(), _payload(), Any, MonkeyPatch, TestClient, Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed() (+7 more)

### Community 21 - "perfis.py"
Cohesion: 0.34
Nodes (14): _perfis_ctx(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for perfis. (+6 more)

### Community 22 - "core.py"
Cohesion: 0.30
Nodes (14): Compra, CompraCreate, CompraRead, CompraUpdate, create(), delete(), get(), get_latest_by_veiculo() (+6 more)

### Community 23 - "core.py"
Cohesion: 0.31
Nodes (13): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteRead, ImagemDocumentoClienteUpdate, list_all() (+5 more)

### Community 24 - "core.py"
Cohesion: 0.32
Nodes (12): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+4 more)

### Community 25 - "factories.py"
Cohesion: 0.23
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 26 - "core.py"
Cohesion: 0.33
Nodes (11): create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead, list_all(), list_by_compra() (+3 more)

### Community 27 - "core.py"
Cohesion: 0.33
Nodes (11): create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead, list_all(), list_by_venda() (+3 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 29 - "Setup"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 30 - "test_auditoria.py"
Cohesion: 0.38
Nodes (11): Session, Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_auditoria_read_serializa_usuario_id_none(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao() (+3 more)

### Community 31 - "ui_login"
Cohesion: 0.22
Nodes (10): Form, HTMLResponse, RedirectResponse, Request, Response, SessionDep, HTMX routes for auth., ui_login() (+2 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.22
Nodes (9): _ctx_dashboard(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for dashboard. (+1 more)

### Community 33 - "core.py"
Cohesion: 0.29
Nodes (8): create_access_token(), decode_token(), get_settings(), BaseModel, BaseSettings, Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings, TokenData

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.33
Nodes (8): Form, HTMLResponse, Request, SessionDep, UIAdmin, HTMX routes for configuracoes., ui_configuracoes(), ui_configuracoes_salvar()

### Community 35 - "AGENTS.md"
Cohesion: 0.25
Nodes (7): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, Agent-Readable Workspace Map

### Community 36 - "core.py"
Cohesion: 0.38
Nodes (6): configure_logging(), get_settings(), BaseSettings, Configuração de structlog: settings, processadores, integração com logging stdli, Configura structlog e faz o logging stdlib (uvicorn, sqlalchemy) passar     pelo, Settings

### Community 37 - "vendas.py"
Cohesion: 0.40
Nodes (5): _ctx_form_venda(), _parse_venda_form(), Any, Session, HTMX routes for vendas.

### Community 39 - "env.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 40 - "a1b2c3d4e002_add_imagem_comprovante_venda_table.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 41 - "a1b2c3d4e004_add_debitos_to_venda.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 42 - "a1b2c3d4e005_add_imagem_documento_cliente_table.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_documento_cliente table., Drop imagem_documento_cliente table., upgrade()

### Community 43 - "a1b2c3d4e006_add_imagem_comprovante_compra_table.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_compra table., Drop imagem_comprovante_compra table., upgrade()

### Community 44 - "a1b2c3d4e009_normalize_imagem_veiculo_urls.py"
Cohesion: 0.40
Nodes (4): downgrade(), Rewrite legacy /media/veiculos URLs to /static/uploads/veiculos., Restore legacy /media/veiculos URLs., upgrade()

### Community 45 - "_UiCompatModule"
Cohesion: 0.40
Nodes (3): Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule, ModuleType

### Community 46 - "_ctx_form_cliente"
Cohesion: 0.40
Nodes (4): _ctx_form_cliente(), Any, Session, HTMX routes for clientes.

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

## Knowledge Gaps
- **100 isolated node(s):** `inventory_api`, `xtreme-system`, `agent-finish.sh script`, `InvestidorCreateFactory`, `VendaCreateFactory` (+95 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Base` to `core.py`, `core.py`, `Usuario`, `core.py`, `core.py`, `core.py`, `core.py`, `core.py`, `core.py`, `core.py`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `_investidor_e_veiculo()` connect `create_test_engine` to `core.py`, `core.py`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `Veiculo` connect `core.py` to `veiculos.py`, `Base`, `core.py`, `create_test_engine`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `_found()` (e.g. with `HTTPException` and `deletar_usuario()`) actually correct?**
  _`_found()` has 30 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Run migrations in 'offline' mode.      This configures the context with just a U`, `Run migrations in 'online' mode.      In this scenario we need to create an Engi`, `Rename lancamento_caixa table and indexes to lancamento_investimento.` to the rest of the system?**
  _198 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `create_test_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.056049213943950786 - nodes in this community are weakly interconnected._
