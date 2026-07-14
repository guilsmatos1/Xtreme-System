# Graph Report - xtreme-system  (2026-07-14)

## Corpus Check
- 132 files · ~46,940 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1201 nodes · 2497 edges · 123 communities (109 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 130 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6efddc50`
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
- 2c9d4e1e7a31_cliente.py
- 3e65ccbaa06a_add_imagem_veiculo_and_documento_.py
- 5c6914b729c6_index_fks_veiculo.py
- 5dc6beff16d0_add_vendedor_id_to_venda.py
- codebase-analysis.md
- agent-finish.sh
- test_core.py
- test_core.py
- inventory_api
- xtreme-system
- Base
- _RateLimiter
- _guard_lancamento_veiculo
- Form
- Response
- UploadFile
- date
- Decimal
- MonkeyPatch
- Path

## God Nodes (most connected - your core abstractions)
1. `_login_admin()` - 29 edges
2. `ne()` - 28 edges
3. `se()` - 27 edges
4. `ue()` - 27 edges
5. `He()` - 26 edges
6. `e()` - 25 edges
7. `Usuario` - 21 edges
8. `session()` - 20 edges
9. `create_test_engine()` - 20 edges
10. `_found()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `main()` --indirect_call--> `session()`  [INFERRED]
  development/create_admin.py → tests/test_crud.py
- `_stub_crud_client()` --calls--> `register_crud_ui_routes()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_aceita_templates_injetado()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_rolls_back_when_write_fails_late()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `_reset_rate_limiters()` --calls--> `reset_rate_limiters()`  [INFERRED]
  tests/conftest.py → bases/xtreme_system/api/setup.py

## Import Cycles
- None detected.

## Communities (123 total, 14 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.15
Nodes (27): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Any, FastAPI, HTMLResponse (+19 more)

### Community 2 - "test_ui.py"
Cohesion: 0.08
Nodes (59): MonkeyPatch, Path, _admin_headers(), client(), _FakeFile, _FakeUpload, _login_admin(), TestClient (+51 more)

### Community 3 - "_found"
Cohesion: 0.10
Nodes (56): _found(), _csv_response(), Response, _sort_key(), _ctx_investidores(), _ctx_lancamentos(), _erro_lancamento(), _form_ctx_investidor() (+48 more)

### Community 4 - "route_factories.py"
Cohesion: 0.06
Nodes (50): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+42 more)

### Community 5 - "core.py"
Cohesion: 0.10
Nodes (43): agregados_investidores(), create(), criar_lancamento_veiculo(), deletar_lancamento_veiculo(), delete(), _descricao_veiculo(), get(), LancamentoInvestimento (+35 more)

### Community 6 - "core.py"
Cohesion: 0.07
Nodes (63): Base, Cliente, ClienteCreate, ClienteRead, ClienteUpdate, create(), delete(), get() (+55 more)

### Community 7 - "setup.py"
Cohesion: 0.15
Nodes (22): _NaoAdminError, _NaoAutenticadoError, _NaoAutorizadoError, _handle_erro_interno(), _handle_nao_admin(), _handle_nao_autenticado(), _handle_nao_autorizado(), _limite_request_size() (+14 more)

### Community 8 - "Usuario"
Cohesion: 0.17
Nodes (25): auditar(), Auditoria, AuditoriaRead, count(), _filtros(), get(), Any, date (+17 more)

### Community 9 - "veiculos.py"
Cohesion: 0.22
Nodes (33): _atualizar_veiculo(), _cliente_vendedor_modal(), _criar_veiculo(), _ctx_form_veiculo(), _ctx_lista_veiculos(), _documentos_modal(), _erro_veiculo(), _imagem_modal() (+25 more)

### Community 10 - "Base"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.26
Nodes (12): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilUpdate, pode_acessar() (+4 more)

### Community 12 - "core.py"
Cohesion: 0.19
Nodes (16): AdminUser, criar_usuario(), deletar_usuario(), health(), listar_auditoria(), listar_usuarios(), login(), CurrentUser (+8 more)

### Community 13 - "usuarios.py"
Cohesion: 0.24
Nodes (15): _ctx_auditoria(), _nomes_usuarios(), _pretty(), Any, date, HTMLResponse, Request, Response (+7 more)

### Community 14 - "Tabelas"
Cohesion: 0.10
Nodes (18): `cliente`, `compra`, `documento_veiculo`, Enums, `imagem_comprovante_compra`, `imagem_comprovante_venda`, `imagem_documento_cliente`, `imagem_veiculo` (+10 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.18
Nodes (24): HTMLResponse, Request, SessionDep, UIAdmin, HTMX routes for usuarios., ui_usuario_criar(), ui_usuario_excluir(), ui_usuario_perfil_alterar() (+16 more)

### Community 17 - "Design"
Cohesion: 0.27
Nodes (12): atualizar_config(), _enviar(), _formatar_mensagem(), get_config(), notificar_venda(), _PlaceholderDict, Session, Notificação de venda via WhatsApp (Evolution API): config, formatação e envio. (+4 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.17
Nodes (12): get_current_user(), get_ui_user(), CurrentUser, Depends, Request, SessionDep, UIUser, Dependências compartilhadas: sessão, autenticação (Bearer/cookie) e templates. (+4 more)

### Community 19 - "auditoria.py"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.27
Nodes (16): client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro() (+8 more)

### Community 21 - "perfis.py"
Cohesion: 0.20
Nodes (10): BaseModel, LancamentoInvestimentoRead, CompraRead, DocumentoVeiculoRead, ImagemComprovanteCompraRead, ImagemComprovanteVendaRead, ImagemVeiculoRead, PerfilRead (+2 more)

### Community 22 - "core.py"
Cohesion: 0.36
Nodes (15): client(), _configurar(), _payload(), Any, MonkeyPatch, TestClient, Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed() (+7 more)

### Community 23 - "core.py"
Cohesion: 0.38
Nodes (11): change_password(), create(), delete(), get(), get_by_username(), list_all(), Session, Usuário: enum de papel, model, schemas e CRUD. (+3 more)

### Community 24 - "core.py"
Cohesion: 0.36
Nodes (11): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoUpdate, get(), list_all(), list_by_veiculo() (+3 more)

### Community 25 - "factories.py"
Cohesion: 0.36
Nodes (11): create(), delete(), get(), ImagemVeiculo, ImagemVeiculoCreate, ImagemVeiculoUpdate, list_all(), list_by_veiculo() (+3 more)

### Community 26 - "core.py"
Cohesion: 0.40
Nodes (13): client(), TestClient, API vendas: CRUD via TestClient., Cria investidor, cliente e veiculo., _seed(), test_admin_cria_venda(), test_admin_lista_vendas(), test_atualizar_venda_concluida_para_pendente_libera_veiculo() (+5 more)

### Community 27 - "core.py"
Cohesion: 0.23
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.42
Nodes (9): create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, list_all(), list_by_compra(), Session (+1 more)

### Community 29 - "Setup"
Cohesion: 0.32
Nodes (11): Base, create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, list_all(), list_by_venda() (+3 more)

### Community 30 - "test_auditoria.py"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 31 - "ui_login"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.38
Nodes (11): Session, Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_auditoria_read_serializa_usuario_id_none(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao() (+3 more)

### Community 33 - "core.py"
Cohesion: 0.12
Nodes (17): BaseSettings, create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings, TokenData, get_session() (+9 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.22
Nodes (10): Form, HTMLResponse, RedirectResponse, Request, Response, SessionDep, HTMX routes for auth., ui_login() (+2 more)

### Community 35 - "AGENTS.md"
Cohesion: 0.22
Nodes (8): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, 7. Merge in a Worktree, Agent-Readable Workspace Map

### Community 36 - "core.py"
Cohesion: 0.22
Nodes (9): _ctx_dashboard(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for dashboard. (+1 more)

### Community 37 - "vendas.py"
Cohesion: 0.33
Nodes (8): Form, HTMLResponse, Request, SessionDep, UIAdmin, HTMX routes for configuracoes., ui_configuracoes(), ui_configuracoes_salvar()

### Community 38 - "test_auth.py"
Cohesion: 0.53
Nodes (8): client(), TestClient, API compras: CRUD via TestClient., _seed(), test_admin_crud_compras(), test_compra_cliente_inexistente_retorna_400(), test_vendedor_nao_cria_compra(), _token()

### Community 39 - "env.py"
Cohesion: 0.29
Nodes (9): Path, UploadFile, Shared helpers for HTMX route modules., Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_dir() (+1 more)

### Community 40 - "a1b2c3d4e002_add_imagem_comprovante_venda_table.py"
Cohesion: 0.32
Nodes (12): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteRead, ImagemDocumentoClienteUpdate, list_all() (+4 more)

### Community 41 - "a1b2c3d4e004_add_debitos_to_venda.py"
Cohesion: 0.40
Nodes (5): _ctx_form_venda(), _parse_venda_form(), Any, Session, HTMX routes for vendas.

### Community 43 - "a1b2c3d4e006_add_imagem_comprovante_compra_table.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 44 - "a1b2c3d4e009_normalize_imagem_veiculo_urls.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 45 - "_UiCompatModule"
Cohesion: 0.40
Nodes (3): Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule, ModuleType

### Community 46 - "_ctx_form_cliente"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

### Community 48 - "a1b2c3d4e001_rename_lancamento_caixa_to_lancamento_.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_documento_cliente table., Drop imagem_documento_cliente table., upgrade()

### Community 49 - "2c9d4e1e7a31_cliente.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_compra table., Drop imagem_comprovante_compra table., upgrade()

### Community 50 - "3e65ccbaa06a_add_imagem_veiculo_and_documento_.py"
Cohesion: 0.40
Nodes (4): downgrade(), Rewrite legacy /media/veiculos URLs to /static/uploads/veiculos., Restore legacy /media/veiculos URLs., upgrade()

### Community 51 - "5c6914b729c6_index_fks_veiculo.py"
Cohesion: 0.25
Nodes (10): _ctx_form_cliente(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for clientes. (+2 more)

### Community 71 - "codebase-analysis.md"
Cohesion: 0.17
Nodes (11): Codebase Analysis - Xtreme Motors, Opportunity 10: Profile assignment can surface FK failures as 500s, Opportunity 1: Sale lifecycle invariants are not enforced, Opportunity 2: Upload validation trusts client metadata and unsafe paths, Opportunity 3: Deleting parent records leaves upload files behind, Opportunity 4: The rate limiter leaks per-IP buckets, Opportunity 5: Investor aggregates are computed in Python on every render, Opportunity 6: Latest purchase lookup scans too much history (+3 more)

### Community 110 - "Base"
Cohesion: 0.35
Nodes (12): Compra, CompraCreate, CompraUpdate, create(), delete(), get(), get_latest_by_veiculo(), latest_by_veiculo_ids() (+4 more)

### Community 114 - "_RateLimiter"
Cohesion: 0.33
Nodes (4): _RateLimiter, Limpa o estado dos limiters (usado em testes, que reusam o `app`)., Janela deslizante em memória, por chave (ex: IP do cliente)., reset_rate_limiters()

### Community 115 - "_guard_lancamento_veiculo"
Cohesion: 0.67
Nodes (4): _guard_lancamento_veiculo(), Any, Session, _validate_investidor_lancamento()

## Knowledge Gaps
- **110 isolated node(s):** `Overview`, `Health Check`, `Rate Limiting`, `Login`, `Create User` (+105 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Usuario` connect `core.py` to `ui_dashboard`, `_found`, `core.py`, `API - Xtreme Motors`, `core.py`, `usuarios.py`, `test_api_auth.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `_StubSchema` connect `route_factories.py` to `perfis.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `ranking_vendedores()` connect `core.py` to `core.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **What connects `Overview`, `Health Check`, `Rate Limiting` to the rest of the system?**
  _208 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `create_test_engine` be split into smaller, more focused modules?**
  _Cohesion score 0.14564564564564564 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07645687645687646 - nodes in this community are weakly interconnected._