# Graph Report - xtreme-system  (2026-07-14)

## Corpus Check
- 148 files · ~57,396 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1408 nodes · 3059 edges · 129 communities (120 shown, 9 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 206 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `492e0211`
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
- a1b2c3d4e009_normalize_imagem_veiculo_urls.py
- _UiCompatModule
- _ctx_form_cliente
- Page
- a1b2c3d4e001_rename_lancamento_caixa_to_lancamento_.py
- 2c9d4e1e7a31_cliente.py
- 3e65ccbaa06a_add_imagem_veiculo_and_documento_.py
- 5c6914b729c6_index_fks_veiculo.py
- 5dc6beff16d0_add_vendedor_id_to_venda.py
- 74df76569f91_usuario_e_auth.py
- 98400e393a26_lancamento_caixa.py
- a1b2c3d4e003_add_compra_table.py
- a1b2c3d4e007_add_auditoria_table.py
- a1b2c3d4e008_add_whatsapp_config_table.py
- codebase-analysis.md
- agent-finish.sh
- __init__.py
- __init__.py
- __init__.py
- auditoria.py
- Response
- RedirectResponse
- SessionDep
- UIAdmin
- __init__.py
- inventory_api
- xtreme-system

## God Nodes (most connected - your core abstractions)
1. `_found()` - 50 edges
2. `create_test_engine()` - 34 edges
3. `_login_admin()` - 34 edges
4. `ne()` - 28 edges
5. `se()` - 27 edges
6. `ue()` - 27 edges
7. `He()` - 26 edges
8. `e()` - 25 edges
9. `Venda` - 23 edges
10. `Base` - 22 edges

## Surprising Connections (you probably didn't know these)
- `_stub_crud_client()` --calls--> `register_crud_ui_routes()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_aceita_templates_injetado()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_rolls_back_when_write_fails_late()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `_reset_rate_limiters()` --calls--> `reset_rate_limiters()`  [INFERRED]
  tests/conftest.py → bases/xtreme_system/api/setup.py
- `get_current_user()` --references--> `Usuario`  [EXTRACTED]
  bases/xtreme_system/api/deps.py → components/xtreme_system/usuario/core.py

## Import Cycles
- None detected.

## Communities (129 total, 9 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.20
Nodes (14): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+6 more)

### Community 2 - "test_ui.py"
Cohesion: 0.07
Nodes (69): UploadFile, Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _validar_uploads(), _admin_headers(), client(), _criar_cliente(), _FakeFile, _FakeUpload (+61 more)

### Community 3 - "_found"
Cohesion: 0.29
Nodes (17): Form, HTMLResponse, Request, Response, SessionDep, UIAdmin, HTMX routes for usuarios., ui_usuario_criar() (+9 more)

### Community 4 - "route_factories.py"
Cohesion: 0.16
Nodes (21): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+13 more)

### Community 5 - "core.py"
Cohesion: 0.09
Nodes (46): AdminUser, confirmar_fechamento_venda(), criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo(), health(), listar_auditoria(), listar_fechamentos_vendas() (+38 more)

### Community 6 - "core.py"
Cohesion: 0.10
Nodes (46): create(), delete(), funil_status(), get(), list_all(), list_by_cliente(), _mes_atual_inicio(), BaseModel (+38 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (38): get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError, _NaoAutorizadoError, CurrentUser, Depends, Exception (+30 more)

### Community 8 - "Usuario"
Cohesion: 0.14
Nodes (16): Engine, db_session(), Session, Sessão isolada com schema migrado em Postgres ou SQLite local., _reset_rate_limiters(), create_test_engine(), Helpers for test database bootstrap., _reset_postgres_schema() (+8 more)

### Community 9 - "veiculos.py"
Cohesion: 0.09
Nodes (76): _found(), Path, Shared helpers for HTMX route modules., _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_compra_dir(), _uploads_contrato_venda_dir() (+68 more)

### Community 10 - "Base"
Cohesion: 0.06
Nodes (32): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Confirmar fechamento, Consulta (+24 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.09
Nodes (45): Cliente, ClienteCreate, ClienteRead, ClienteUpdate, create(), delete(), get(), get_by_documento() (+37 more)

### Community 12 - "core.py"
Cohesion: 0.13
Nodes (30): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Any, FastAPI, HTMLResponse (+22 more)

### Community 13 - "usuarios.py"
Cohesion: 0.18
Nodes (19): _ctx_form_custo(), _ctx_list_custos(), _parse_custo_form(), Any, Session, HTMX routes for custos de veículos., _validar_veiculo_fk(), create() (+11 more)

### Community 14 - "Tabelas"
Cohesion: 0.08
Nodes (22): `cliente`, `compra`, `custo_veiculo`, `documento_contrato_venda`, `documento_veiculo`, Enums, `fechamento_venda`, `imagem_comprovante_compra` (+14 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.33
Nodes (11): create(), delete(), DocumentoProcuracao, DocumentoProcuracaoCreate, DocumentoProcuracaoRead, get(), list_all(), list_by_veiculo() (+3 more)

### Community 17 - "Design"
Cohesion: 0.22
Nodes (15): Jinja2Templates, _ConflictModule, Any, BaseModel, Path, TestClient, Prova que register_ui_simples recebe Jinja2Templates como parâmetro (não mais o, _stub_crud_client() (+7 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.21
Nodes (23): _baixar_contrato_venda(), _confirmar_fechamento_venda(), _criar_venda(), _ctx_form_venda(), _ctx_lista_vendas(), _detalhe_fechamento_venda(), _erro_venda(), _form_fechamento_venda() (+15 more)

### Community 19 - "auditoria.py"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.21
Nodes (31): _csv_response(), Response, _ctx_investidores(), _ctx_lancamentos(), _erro_lancamento(), _form_ctx_investidor(), _ok_lancamentos(), Any (+23 more)

### Community 21 - "perfis.py"
Cohesion: 0.24
Nodes (15): _ctx_auditoria(), _nomes_usuarios(), _pretty(), Any, date, HTMLResponse, Request, Response (+7 more)

### Community 22 - "core.py"
Cohesion: 0.36
Nodes (15): client(), _configurar(), _payload(), Any, MonkeyPatch, TestClient, Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed() (+7 more)

### Community 23 - "core.py"
Cohesion: 0.11
Nodes (40): auditar(), Auditoria, AuditoriaRead, count(), _filtros(), get(), Any, BaseModel (+32 more)

### Community 24 - "core.py"
Cohesion: 0.34
Nodes (14): _perfis_ctx(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for perfis. (+6 more)

### Community 25 - "factories.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 26 - "core.py"
Cohesion: 0.27
Nodes (16): client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro() (+8 more)

### Community 27 - "core.py"
Cohesion: 0.23
Nodes (11): ClienteCreateFactory, _documento(), InvestidorCreateFactory, _next_id(), PerfilCreateFactory, _placa(), Factories de schemas Pydantic para testes., UsuarioCreateFactory (+3 more)

### Community 28 - "Validação de Uploads Implementation Plan"
Cohesion: 0.25
Nodes (13): atualizar_config(), _enviar(), _formatar_mensagem(), get_config(), notificar_venda(), _PlaceholderDict, BaseModel, Session (+5 more)

### Community 29 - "Setup"
Cohesion: 0.31
Nodes (13): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoRead, DocumentoVeiculoUpdate, get(), list_all() (+5 more)

### Community 30 - "test_auditoria.py"
Cohesion: 0.31
Nodes (13): create(), delete(), get(), ImagemDocumentoCliente, ImagemDocumentoClienteCreate, ImagemDocumentoClienteRead, ImagemDocumentoClienteUpdate, list_all() (+5 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.31
Nodes (13): create(), delete(), get(), ImagemVeiculo, ImagemVeiculoCreate, ImagemVeiculoRead, ImagemVeiculoUpdate, list_all() (+5 more)

### Community 33 - "core.py"
Cohesion: 0.30
Nodes (13): _investidor_e_veiculo(), CRUD end-to-end dos bricks, em SQLite in-memory (sem depender do Postgres)., CRUD de usuário: criar, buscar, listar, deletar e trocar senha., session(), test_atualizar_preco_ou_investidor_sincroniza_lancamento(), test_caixa_lancamento_veiculo_audit(), test_criar_veiculo_gera_lancamento_de_custo_e_reduz_saldo(), test_excluir_veiculo_apaga_lancamento_em_cascata() (+5 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.33
Nodes (11): create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead, list_all(), list_by_compra() (+3 more)

### Community 35 - "test_venda_whatsapp.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add trade and pending payment fields to venda table., Remove trade and pending payment fields from venda table., upgrade()

### Community 36 - "core.py"
Cohesion: 0.33
Nodes (11): create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead, list_all(), list_by_venda() (+3 more)

### Community 37 - "vendas.py"
Cohesion: 0.17
Nodes (11): Codebase Analysis - Xtreme Motors, Opportunity 10: Profile assignment can surface FK failures as 500s, Opportunity 1: Sale lifecycle invariants are not enforced, Opportunity 2: Upload validation trusts client metadata and unsafe paths, Opportunity 3: Deleting parent records leaves upload files behind, Opportunity 4: The rate limiter leaks per-IP buckets, Opportunity 5: Investor aggregates are computed in Python on every render, Opportunity 6: Latest purchase lookup scans too much history (+3 more)

### Community 38 - "test_auth.py"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 39 - "env.py"
Cohesion: 0.38
Nodes (11): Session, Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory., _seed_admin(), test_auditoria_read_serializa_usuario_id_none(), test_count_bate_com_query_sem_limit(), test_count_respeita_filtros(), test_query_filtra_por_data_de(), test_query_filtra_por_tabela_e_acao() (+3 more)

### Community 40 - "a1b2c3d4e002_add_imagem_comprovante_venda_table.py"
Cohesion: 0.22
Nodes (10): Form, HTMLResponse, RedirectResponse, Request, Response, SessionDep, HTMX routes for auth., ui_login() (+2 more)

### Community 41 - "a1b2c3d4e004_add_debitos_to_venda.py"
Cohesion: 0.27
Nodes (9): create_access_token(), decode_token(), get_settings(), BaseModel, BaseSettings, Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings, Token (+1 more)

### Community 42 - "a1b2c3d4e005_add_imagem_documento_cliente_table.py"
Cohesion: 0.22
Nodes (9): _ctx_dashboard(), Any, HTMLResponse, Request, Session, SessionDep, UIAdmin, HTMX routes for dashboard. (+1 more)

### Community 43 - "a1b2c3d4e006_add_imagem_comprovante_compra_table.py"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 44 - "a1b2c3d4e009_normalize_imagem_veiculo_urls.py"
Cohesion: 0.33
Nodes (8): Form, HTMLResponse, Request, SessionDep, UIAdmin, HTMX routes for configuracoes., ui_configuracoes(), ui_configuracoes_salvar()

### Community 45 - "_UiCompatModule"
Cohesion: 0.40
Nodes (3): Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule, ModuleType

### Community 46 - "_ctx_form_cliente"
Cohesion: 0.53
Nodes (8): client(), TestClient, API compras: CRUD via TestClient., _seed(), test_admin_crud_compras(), test_compra_cliente_inexistente_retorna_400(), test_vendedor_nao_cria_compra(), _token()

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

### Community 48 - "a1b2c3d4e001_rename_lancamento_caixa_to_lancamento_.py"
Cohesion: 0.39
Nodes (7): client(), TestClient, Rate limiting: tentativas de login e requests gerais da API., test_health_isento_de_rate_limit(), test_login_bloqueia_apos_limite(), test_requests_gerais_bloqueiam_apos_limite(), test_ui_login_bloqueia_apos_limite_e_retorna_html()

### Community 49 - "2c9d4e1e7a31_cliente.py"
Cohesion: 0.38
Nodes (6): configure_logging(), get_settings(), BaseSettings, Configuração de structlog: settings, processadores, integração com logging stdli, Configura structlog e faz o logging stdlib (uvicorn, sqlalchemy) passar     pelo, Settings

### Community 51 - "5c6914b729c6_index_fks_veiculo.py"
Cohesion: 0.21
Nodes (17): _ctx_form_cliente(), _ctx_lista_cliente(), Any, HTMLResponse, RedirectResponse, Request, Session, SessionDep (+9 more)

### Community 52 - "5dc6beff16d0_add_vendedor_id_to_venda.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_venda table., Drop imagem_comprovante_venda table., upgrade()

### Community 53 - "74df76569f91_usuario_e_auth.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 54 - "98400e393a26_lancamento_caixa.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_documento_cliente table., Drop imagem_documento_cliente table., upgrade()

### Community 55 - "a1b2c3d4e003_add_compra_table.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create imagem_comprovante_compra table., Drop imagem_comprovante_compra table., upgrade()

### Community 56 - "a1b2c3d4e007_add_auditoria_table.py"
Cohesion: 0.40
Nodes (4): downgrade(), Rewrite legacy /media/veiculos URLs to /static/uploads/veiculos., Restore legacy /media/veiculos URLs., upgrade()

### Community 71 - "codebase-analysis.md"
Cohesion: 0.09
Nodes (48): agregados_investidores(), create(), criar_lancamento_fechamento(), criar_lancamento_veiculo(), deletar_lancamento_veiculo(), delete(), _descricao_veiculo(), get() (+40 more)

### Community 85 - "auditoria.py"
Cohesion: 0.40
Nodes (13): client(), TestClient, API vendas: CRUD via TestClient., Cria investidor, cliente e veiculo., _seed(), test_admin_cria_venda(), test_admin_lista_vendas(), test_atualizar_venda_concluida_para_pendente_libera_veiculo() (+5 more)

### Community 86 - "Response"
Cohesion: 0.33
Nodes (11): create(), delete(), DocumentoContratoVenda, DocumentoContratoVendaCreate, DocumentoContratoVendaRead, get(), list_all(), list_by_venda() (+3 more)

### Community 87 - "RedirectResponse"
Cohesion: 0.22
Nodes (8): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, 7. Merge in a Worktree, Agent-Readable Workspace Map

### Community 88 - "SessionDep"
Cohesion: 0.48
Nodes (5): Session, Custos de veículos: CRUD e validações do componente., test_crud_custo_veiculo(), test_custo_veiculo_remove_em_cascata_ao_excluir_veiculo(), _veiculo()

### Community 89 - "UIAdmin"
Cohesion: 0.40
Nodes (4): downgrade(), Add km column to venda table., Remove km column from venda table., upgrade()

## Knowledge Gaps
- **117 isolated node(s):** `inventory_api`, `xtreme-system`, `agent-finish.sh script`, `InvestidorCreateFactory`, `VendaCreateFactory` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `API - Xtreme Motors` to `ui_dashboard`, `create_test_engine`, `ui_configuracoes_salvar`, `core.py`, `core.py`, `route_factories.py`, `codebase-analysis.md`, `core.py`, `usuarios.py`, `core.py`, `Response`, `core.py`, `Validação de Uploads Implementation Plan`, `Setup`, `test_auditoria.py`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `create_test_engine()` connect `Usuario` to `core.py`, `test_ui.py`, `core.py`, `core.py`, `_ctx_form_cliente`, `a1b2c3d4e001_rename_lancamento_caixa_to_lancamento_.py`, `Design`, `auditoria.py`, `core.py`, `core.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `_found()` connect `veiculos.py` to `_found`, `core.py`, `setup.py`, `test_api_auth.py`, `5c6914b729c6_index_fks_veiculo.py`, `test_venda_whatsapp.py`, `perfis.py`, `core.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 48 inferred relationships involving `_found()` (e.g. with `HTTPException` and `confirmar_fechamento_venda()`) actually correct?**
  _`_found()` has 48 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Run migrations in 'offline' mode.      This configures the context with just a U`, `Run migrations in 'online' mode.      In this scenario we need to create an Engi`, `Add km column to venda table.` to the rest of the system?**
  _229 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07157894736842105 - nodes in this community are weakly interconnected._