# Graph Report - char  (2026-07-14)

## Corpus Check
- 135 files · ~50,654 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1260 nodes · 2457 edges · 200 communities (99 shown, 101 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 199 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `70c0d30c`
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
- test_venda_whatsapp.py
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
- auditoria.py
- Response
- RedirectResponse
- SessionDep
- UIAdmin
- UIUser
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
- MonkeyPatch
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
- Path
- Any
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- TestClient
- CLAUDE.md
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
1. `_found()` - 41 edges
2. `_login_admin()` - 32 edges
3. `ne()` - 28 edges
4. `se()` - 27 edges
5. `ue()` - 27 edges
6. `He()` - 26 edges
7. `e()` - 25 edges
8. `_admin_headers()` - 21 edges
9. `create_test_engine()` - 21 edges
10. `Cliente` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_json_create_rolls_back_when_after_create_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_delete_rolls_back_when_before_delete_fails_after_writes()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_update_rolls_back_when_after_update_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_sort_key_nulls()` --indirect_call--> `_sort_key()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `main()` --indirect_call--> `session()`  [INFERRED]
  development/create_admin.py → tests/test_crud.py

## Import Cycles
- None detected.

## Communities (200 total, 101 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.36
Nodes (9): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorUpdate, list_all(), Investidor: model, schemas e CRUD. (+1 more)

### Community 2 - "test_ui.py"
Cohesion: 0.08
Nodes (64): MonkeyPatch, Path, TestClient, _admin_headers(), client(), _criar_cliente(), _FakeFile, _FakeUpload (+56 more)

### Community 3 - "_found"
Cohesion: 0.16
Nodes (24): _sort_key(), Form, HTMLResponse, Request, Response, SessionDep, UIAdmin, HTMX routes for usuarios. (+16 more)

### Community 4 - "route_factories.py"
Cohesion: 0.17
Nodes (19): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilUpdate, pode_acessar() (+11 more)

### Community 5 - "core.py"
Cohesion: 0.11
Nodes (27): AdminUser, criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo(), listar_auditoria(), listar_usuarios(), Rotas JSON: autenticação, usuários e CRUD dos recursos de negócio., trocar_senha_usuario() (+19 more)

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
Nodes (76): Path, UploadFile, Shared helpers for HTMX route modules., Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_compra_dir() (+68 more)

### Community 10 - "Base"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.14
Nodes (34): Base, Cliente, ClienteCreate, ClienteRead, ClienteUpdate, create(), delete(), get() (+26 more)

### Community 12 - "core.py"
Cohesion: 0.07
Nodes (40): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _csv_response(), _delete_with_hook(), Any, HTMLResponse (+32 more)

### Community 13 - "usuarios.py"
Cohesion: 0.40
Nodes (13): client(), TestClient, API vendas: CRUD via TestClient., Cria investidor, cliente e veiculo., _seed(), test_admin_cria_venda(), test_admin_lista_vendas(), test_atualizar_venda_concluida_para_pendente_libera_veiculo() (+5 more)

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
Cohesion: 0.23
Nodes (29): _ctx_investidores(), _ctx_lancamentos(), _erro_lancamento(), _form_ctx_investidor(), _ok_lancamentos(), Any, HTMLResponse, Request (+21 more)

### Community 21 - "perfis.py"
Cohesion: 0.20
Nodes (10): BaseModel, DocumentoProcuracaoRead, PerfilRead, UsuarioRead, VeiculoRead, VendaRead, DocumentoVeiculoRead, ImagemDocumentoClienteRead (+2 more)

### Community 22 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteUpdate, list_all(), list_by_cliente() (+2 more)

### Community 23 - "core.py"
Cohesion: 0.07
Nodes (49): change_password(), create(), delete(), get(), get_by_username(), list_all(), Session, Usuário: enum de papel, model, schemas e CRUD. (+41 more)

### Community 24 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemVeiculo, ImagemVeiculoCreate, ImagemVeiculoUpdate, list_all(), list_by_veiculo() (+2 more)

### Community 25 - "factories.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 26 - "core.py"
Cohesion: 0.06
Nodes (51): Engine, client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin() (+43 more)

### Community 27 - "core.py"
Cohesion: 0.21
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.29
Nodes (8): Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao(), test_query_filtra_por_usuario(), test_query_pagina_com_limit_offset()

### Community 29 - "Setup"
Cohesion: 0.26
Nodes (11): DeclarativeBase, Base, create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead (+3 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 33 - "core.py"
Cohesion: 0.11
Nodes (18): BaseSettings, OAuth2PasswordRequestForm, login(), create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings (+10 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 35 - "test_venda_whatsapp.py"
Cohesion: 0.41
Nodes (9): _configurar(), _payload(), Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed(), test_criar_venda_dispara_notificacao(), test_falha_no_envio_nao_impede_criacao_da_venda(), test_notificacao_ignora_placeholder_desconhecido(), test_notificacao_usa_template_customizado() (+1 more)

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
Cohesion: 0.21
Nodes (17): _ctx_form_cliente(), _ctx_lista_cliente(), Any, HTMLResponse, Request, Session, HTMX routes for clientes., _register_clientes_page() (+9 more)

### Community 71 - "codebase-analysis.md"
Cohesion: 0.17
Nodes (11): Codebase Analysis - Xtreme Motors, Opportunity 10: Profile assignment can surface FK failures as 500s, Opportunity 1: Sale lifecycle invariants are not enforced, Opportunity 2: Upload validation trusts client metadata and unsafe paths, Opportunity 3: Deleting parent records leaves upload files behind, Opportunity 4: The rate limiter leaks per-IP buckets, Opportunity 5: Investor aggregates are computed in Python on every render, Opportunity 6: Latest purchase lookup scans too much history (+3 more)

### Community 116 - "Form"
Cohesion: 0.33
Nodes (9): create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead, list_all(), list_by_venda() (+1 more)

### Community 176 - "CLAUDE.md"
Cohesion: 0.22
Nodes (8): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, 7. Merge in a Worktree, Agent-Readable Workspace Map

## Knowledge Gaps
- **110 isolated node(s):** `Visão geral`, `Estrutura Polylith`, `App FastAPI`, `Dependências de autenticação`, `Endpoints JSON` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **101 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_found()` connect `veiculos.py` to `_found`, `test_venda_whatsapp.py`, `core.py`, `setup.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `Base` connect `Setup` to `core.py`, `create_test_engine`, `route_factories.py`, `core.py`, `core.py`, `core.py`, `auditoria.py`, `Form`, `core.py`, `core.py`, `core.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `create_test_engine()` connect `core.py` to `core.py`, `usuarios.py`, `setup.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `_found()` (e.g. with `_comprovantes_modal()` and `ui_compra_comprovantes_excluir()`) actually correct?**
  _`_found()` has 39 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Visão geral`, `Estrutura Polylith`, `App FastAPI` to the rest of the system?**
  _209 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07565392354124749 - nodes in this community are weakly interconnected._