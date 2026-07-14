# Graph Report - gui-87-opportunity-8-investor-creation-hides-a-f  (2026-07-14)

## Corpus Check
- 130 files · ~48,285 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1172 nodes · 1920 edges · 235 communities (93 shown, 142 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 148 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `06e8adaa`
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
- core.py
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
- Any
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
- e1c2d3e4f5g6_add_tipo_entrada_and_revisao_to_veiculo.py
- e7f8a9b0c1d2_index_auditoria_criado_em.py
- f2a3b4c5d6e7_remove_meio_captacao.py
- core.py
- __init__.py
- test_core.py
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
- __init__.py
- __init__.py
- inventory_api
- xtreme-system
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- session
- test_api_vendas.py
- core.py
- BaseModel
- test_api_compras.py
- test_api_rate_limit.py
- HTMLResponse
- Request
- Response
- Session
- SessionDep
- UIAdmin
- Form
- HTMLResponse
- RedirectResponse
- Request
- Response
- SessionDep
- Any
- Session
- Path
- UploadFile
- Form
- HTMLResponse
- Request
- SessionDep
- UIAdmin
- Any
- HTMLResponse
- Request
- Session
- SessionDep
- UIAdmin
- HTMLResponse
- Request
- Response
- Session
- SessionDep
- UIAdmin
- UIUser
- MonkeyPatch
- Any
- HTMLResponse
- Request
- Session
- SessionDep
- UIAdmin
- Form
- HTMLResponse
- Request
- Response
- SessionDep
- UIAdmin
- Any
- HTMLResponse
- Request
- Session
- SessionDep
- UIAdmin
- UploadFile
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
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Any
- Session
- Session
- Decimal
- Session
- date
- Decimal
- Session
- Session
- Session
- TestClient
- TestClient
- TestClient
- TestClient
- TestClient
- Session
- Session
- Path
- TestClient
- Any
- MonkeyPatch
- TestClient

## God Nodes (most connected - your core abstractions)
1. `_login_admin()` - 29 edges
2. `ne()` - 28 edges
3. `se()` - 27 edges
4. `ue()` - 27 edges
5. `He()` - 26 edges
6. `e()` - 25 edges
7. `_found()` - 22 edges
8. `pt()` - 19 edges
9. `session()` - 19 edges
10. `ee()` - 18 edges

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

## Communities (235 total, 142 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.06
Nodes (46): Engine, _free_port(), live_server_url(), main(), Cria o primeiro admin: uv run python development/create_admin.py <user> <senha>., create_test_engine(), Helpers for test database bootstrap., _reset_postgres_schema() (+38 more)

### Community 2 - "test_ui.py"
Cohesion: 0.08
Nodes (59): MonkeyPatch, Path, TestClient, _admin_headers(), client(), _FakeFile, _FakeUpload, _login_admin() (+51 more)

### Community 3 - "_found"
Cohesion: 0.07
Nodes (49): default_factory, File, T, _sort_key(), _found(), Shared helpers for HTMX route modules., Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _remover_upload() (+41 more)

### Community 4 - "route_factories.py"
Cohesion: 0.07
Nodes (33): Jinja2Templates, Protocol, _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Factories genéricas de rotas CRUD (API JSON e UI HTMX) reutilizadas por entidade (+25 more)

### Community 5 - "core.py"
Cohesion: 0.07
Nodes (47): StrEnum, OrigemLancamento, TipoLancamento, TipoCliente, Papel, create(), delete(), get() (+39 more)

### Community 6 - "core.py"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (28): Cookie, Exception, JSONResponse, oauth2_scheme, get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError (+20 more)

### Community 8 - "Usuario"
Cohesion: 0.07
Nodes (49): M, commit(), create(), delete(), get(), list_all(), CRUD genérico: list_all, get, create, update, delete para qualquer model., update() (+41 more)

### Community 9 - "veiculos.py"
Cohesion: 0.09
Nodes (54): AdminUser, Any, _ctx_investidores(), _ctx_lancamentos(), _erro_lancamento(), _form_ctx_investidor(), _ok_lancamentos(), HTMX routes for investidores. (+46 more)

### Community 10 - "Base"
Cohesion: 0.16
Nodes (16): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+8 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.10
Nodes (18): `cliente`, `compra`, `documento_veiculo`, Enums, `imagem_comprovante_compra`, `imagem_comprovante_venda`, `imagem_documento_cliente`, `imagem_veiculo` (+10 more)

### Community 12 - "core.py"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 13 - "usuarios.py"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 14 - "Tabelas"
Cohesion: 0.22
Nodes (12): API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro(), test_api_usuario_management_atribui_admin_na_auditoria(), test_placa_duplicada_retorna_400() (+4 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.28
Nodes (11): atualizar_config(), _enviar(), _formatar_mensagem(), get_config(), notificar_venda(), _PlaceholderDict, Notificação de venda via WhatsApp (Evolution API): config, formatação e envio., Envia a notificação da venda para o grupo do WhatsApp, best-effort.      Nunca p (+3 more)

### Community 16 - "core.py"
Cohesion: 0.19
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 17 - "Design"
Cohesion: 0.30
Nodes (11): Compra, CompraCreate, CompraUpdate, create(), delete(), get(), get_latest_by_veiculo(), latest_by_veiculo_ids() (+3 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 19 - "auditoria.py"
Cohesion: 0.36
Nodes (10): client(), _configurar(), _payload(), Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed(), test_criar_venda_dispara_notificacao(), test_falha_no_envio_nao_impede_criacao_da_venda(), test_notificacao_ignora_placeholder_desconhecido() (+2 more)

### Community 20 - "core.py"
Cohesion: 0.30
Nodes (11): Cliente, ClienteCreate, ClienteUpdate, create(), delete(), get(), get_by_documento(), list_all() (+3 more)

### Community 21 - "perfis.py"
Cohesion: 0.33
Nodes (10): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoUpdate, get(), list_all(), list_by_veiculo() (+2 more)

### Community 22 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteUpdate, list_all(), list_by_cliente() (+2 more)

### Community 23 - "core.py"
Cohesion: 0.33
Nodes (10): create(), delete(), get(), ImagemVeiculo, ImagemVeiculoCreate, ImagemVeiculoUpdate, list_all(), list_by_veiculo() (+2 more)

### Community 24 - "core.py"
Cohesion: 0.29
Nodes (8): Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao(), test_query_filtra_por_usuario(), test_query_pagina_com_limit_offset()

### Community 25 - "factories.py"
Cohesion: 0.33
Nodes (9): create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead, list_all(), list_by_venda() (+1 more)

### Community 26 - "core.py"
Cohesion: 0.26
Nodes (11): DeclarativeBase, Base, create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead (+3 more)

### Community 27 - "core.py"
Cohesion: 0.31
Nodes (10): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+2 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.25
Nodes (7): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, Agent-Readable Workspace Map

### Community 29 - "Setup"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 31 - "ui_login"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 32 - "ui_dashboard"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 33 - "core.py"
Cohesion: 0.14
Nodes (15): BaseSettings, get_settings(), Configuração de banco: settings, engine, sessão e Base declarativa., Settings, create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI). (+7 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

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
Nodes (3): ModuleType, Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

### Community 110 - "BaseModel"
Cohesion: 0.29
Nodes (7): BaseModel, ClienteRead, CompraRead, DocumentoVeiculoRead, ImagemDocumentoClienteRead, ImagemVeiculoRead, VendaRead

## Knowledge Gaps
- **100 isolated node(s):** `inventory_api`, `xtreme-system`, `agent-finish.sh script`, `InvestidorCreateFactory`, `VendaCreateFactory` (+95 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **142 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_test_engine()` connect `create_test_engine` to `auditoria.py`, `route_factories.py`, `setup.py`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `_stub_crud_client()` connect `route_factories.py` to `create_test_engine`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `_StubSchema` connect `route_factories.py` to `BaseModel`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **What connects `HTMX routes for investidores.`, `UI HTMX: login por cookie e proteção das telas.`, `Admin pode excluir outro usuário pela UI.` to the rest of the system?**
  _198 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `create_test_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.05573770491803279 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07645687645687646 - nodes in this community are weakly interconnected._