# Graph Report - grouper  (2026-07-14)

## Corpus Check
- 135 files · ~49,974 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1235 nodes · 2369 edges · 198 communities (99 shown, 99 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 198 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fce1520c`
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
- _UiCompatModule
- Page
- 5c6914b729c6_index_fks_veiculo.py
- e7f8a9b0c1d2_index_auditoria_criado_em.py
- f2a3b4c5d6e7_remove_meio_captacao.py
- codebase-analysis.md
- agent-finish.sh
- test_package.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- inventory_api
- xtreme-system
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- core.py
- test_api_vendas.py
- core.py
- Base
- HTMLResponse
- Request
- _RateLimiter
- _guard_lancamento_veiculo
- Form
- default_factory
- UploadFile
- date
- Decimal
- MonkeyPatch
- Path
- Any
- HTMLResponse
- Request
- Session
- SessionDep
- UIAdmin
- Any
- HTMLResponse
- Request
- Session
- SessionDep
- UIAdmin
- Any
- Session
- Any
- Session
- Any
- Exception
- HTMLResponse
- RedirectResponse
- Request
- Response
- Any
- date
- Session
- Decimal
- Session
- Session
- Any
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- TestClient
- TestClient
- Session
- FastAPI
- Session
- TestClient
- Any
- Path
- Session
- TestClient
- Any
- MonkeyPatch
- TestClient

## God Nodes (most connected - your core abstractions)
1. `_found()` - 42 edges
2. `_login_admin()` - 32 edges
3. `ne()` - 28 edges
4. `se()` - 27 edges
5. `ue()` - 27 edges
6. `He()` - 26 edges
7. `e()` - 25 edges
8. `create_test_engine()` - 24 edges
9. `session()` - 21 edges
10. `pt()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_json_create_rolls_back_when_after_create_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_delete_rolls_back_when_before_delete_fails_after_writes()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_update_rolls_back_when_after_update_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_validar_uploads_arquivo_maior_que_5mb()` --calls--> `_validar_uploads()`  [INFERRED]
  tests/test_ui.py → bases/xtreme_system/api/routes/ui_routes/common.py
- `test_validar_uploads_content_type_ausente_passa()` --calls--> `_validar_uploads()`  [INFERRED]
  tests/test_ui.py → bases/xtreme_system/api/routes/ui_routes/common.py

## Import Cycles
- None detected.

## Communities (198 total, 99 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.06
Nodes (41): Jinja2Templates, Protocol, _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Factories genéricas de rotas CRUD (API JSON e UI HTMX) reutilizadas por entidade (+33 more)

### Community 2 - "test_ui.py"
Cohesion: 0.08
Nodes (63): _admin_headers(), client(), _FakeFile, _FakeUpload, _login_admin(), MonkeyPatch, Path, TestClient (+55 more)

### Community 3 - "_found"
Cohesion: 0.15
Nodes (26): Form, HTMLResponse, Request, Response, SessionDep, UIAdmin, HTMX routes for usuarios., ui_usuario_criar() (+18 more)

### Community 4 - "route_factories.py"
Cohesion: 0.16
Nodes (20): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+12 more)

### Community 5 - "core.py"
Cohesion: 0.09
Nodes (30): AdminUser, OAuth2PasswordRequestForm, criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo(), listar_auditoria(), listar_usuarios(), login() (+22 more)

### Community 6 - "core.py"
Cohesion: 0.08
Nodes (51): TipoCliente, create(), delete(), get(), get_by_placa(), list_all(), Decimal, Session (+43 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (28): Cookie, Exception, JSONResponse, oauth2_scheme, get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError (+20 more)

### Community 8 - "Usuario"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 9 - "veiculos.py"
Cohesion: 0.09
Nodes (89): Path, UploadFile, Shared helpers for HTMX route modules., Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_compra_dir() (+81 more)

### Community 10 - "Base"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.35
Nodes (12): Cliente, ClienteCreate, ClienteUpdate, create(), delete(), get(), get_by_documento(), list_all() (+4 more)

### Community 12 - "core.py"
Cohesion: 0.36
Nodes (10): client(), _configurar(), _payload(), Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed(), test_criar_venda_dispara_notificacao(), test_falha_no_envio_nao_impede_criacao_da_venda(), test_notificacao_ignora_placeholder_desconhecido() (+2 more)

### Community 13 - "usuarios.py"
Cohesion: 0.30
Nodes (11): Compra, CompraCreate, CompraUpdate, create(), delete(), get(), get_latest_by_veiculo(), latest_by_veiculo_ids() (+3 more)

### Community 14 - "Tabelas"
Cohesion: 0.10
Nodes (18): `cliente`, `compra`, `documento_veiculo`, Enums, `imagem_comprovante_compra`, `imagem_comprovante_venda`, `imagem_documento_cliente`, `imagem_veiculo` (+10 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.42
Nodes (9): create(), delete(), DocumentoProcuracao, DocumentoProcuracaoCreate, get(), list_all(), list_by_veiculo(), Session (+1 more)

### Community 17 - "Design"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 19 - "auditoria.py"
Cohesion: 0.33
Nodes (10): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoUpdate, get(), list_all(), list_by_veiculo() (+2 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.27
Nodes (16): client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro() (+8 more)

### Community 21 - "perfis.py"
Cohesion: 0.18
Nodes (11): BaseModel, ClienteRead, DocumentoProcuracaoRead, UsuarioRead, VeiculoRead, VendaRead, LancamentoInvestimentoRead, CompraRead (+3 more)

### Community 22 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteUpdate, list_all(), list_by_cliente() (+2 more)

### Community 23 - "core.py"
Cohesion: 0.07
Nodes (48): change_password(), create(), delete(), get(), get_by_username(), list_all(), Session, Usuário: enum de papel, model, schemas e CRUD. (+40 more)

### Community 24 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemVeiculo, ImagemVeiculoCreate, ImagemVeiculoUpdate, list_all(), list_by_veiculo() (+2 more)

### Community 25 - "factories.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 26 - "core.py"
Cohesion: 0.06
Nodes (47): Engine, client(), TestClient, API compras: CRUD via TestClient., _seed(), test_admin_crud_compras(), test_compra_cliente_inexistente_retorna_400(), test_vendedor_nao_cria_compra() (+39 more)

### Community 27 - "core.py"
Cohesion: 0.21
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.29
Nodes (8): Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao(), test_query_filtra_por_usuario(), test_query_pagina_com_limit_offset()

### Community 29 - "Setup"
Cohesion: 0.33
Nodes (9): create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead, list_all(), list_by_compra() (+1 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 33 - "core.py"
Cohesion: 0.14
Nodes (15): BaseSettings, create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings, TokenData, get_settings() (+7 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 35 - "AGENTS.md"
Cohesion: 0.22
Nodes (8): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, 7. Merge in a Worktree, Agent-Readable Workspace Map

### Community 36 - "core.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_documento_cliente table., Drop imagem_documento_cliente table., upgrade()

### Community 37 - "vendas.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_compra table., Drop imagem_comprovante_compra table., upgrade()

### Community 38 - "test_auth.py"
Cohesion: 0.40
Nodes (4): downgrade(), Rewrite legacy /media/veiculos URLs to /static/uploads/veiculos., Restore legacy /media/veiculos URLs., upgrade()

### Community 42 - "a1b2c3d4e005_add_imagem_documento_cliente_table.py"
Cohesion: 0.67
Nodes (3): _ctx_dashboard(), HTMX routes for dashboard., ui_dashboard()

### Community 45 - "_UiCompatModule"
Cohesion: 0.40
Nodes (3): Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule, ModuleType

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

### Community 51 - "5c6914b729c6_index_fks_veiculo.py"
Cohesion: 0.25
Nodes (10): _ctx_form_cliente(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for clientes. (+2 more)

### Community 71 - "codebase-analysis.md"
Cohesion: 0.17
Nodes (11): Codebase Analysis - Xtreme Motors, Opportunity 10: Profile assignment can surface FK failures as 500s, Opportunity 1: Sale lifecycle invariants are not enforced, Opportunity 2: Upload validation trusts client metadata and unsafe paths, Opportunity 3: Deleting parent records leaves upload files behind, Opportunity 4: The rate limiter leaks per-IP buckets, Opportunity 5: Investor aggregates are computed in Python on every render, Opportunity 6: Latest purchase lookup scans too much history (+3 more)

### Community 116 - "Form"
Cohesion: 0.26
Nodes (11): DeclarativeBase, Base, create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead (+3 more)

### Community 117 - "default_factory"
Cohesion: 0.22
Nodes (17): _comprovantes_modal(), _ctx_form_compra(), _parse_compra_form(), Any, default_factory, File, HTMLResponse, Request (+9 more)

## Knowledge Gaps
- **110 isolated node(s):** `inventory_api`, `xtreme-system`, `agent-finish.sh script`, `InvestidorCreateFactory`, `VendaCreateFactory` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **99 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_test_engine()` connect `core.py` to `create_test_engine`, `test_ui.py`, `setup.py`, `core.py`, `test_venda_whatsapp.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `Base` connect `Form` to `core.py`, `create_test_engine`, `route_factories.py`, `core.py`, `core.py`, `API - Xtreme Motors`, `usuarios.py`, `core.py`, `auditoria.py`, `core.py`, `core.py`, `core.py`, `Setup`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `_found()` connect `veiculos.py` to `_found`, `core.py`, `setup.py`, `5c6914b729c6_index_fks_veiculo.py`, `default_factory`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `_found()` (e.g. with `_veiculos_modal()` and `_comprovantes_modal()`) actually correct?**
  _`_found()` has 40 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Run migrations in 'offline' mode.      This configures the context with just a U`, `Run migrations in 'online' mode.      In this scenario we need to create an Engi`, `Rename lancamento_caixa table and indexes to lancamento_investimento.` to the rest of the system?**
  _209 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `create_test_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.06009615384615385 - nodes in this community are weakly interconnected._