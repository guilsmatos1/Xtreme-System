# Graph Report - plaice  (2026-07-14)

## Corpus Check
- 154 files · ~57,871 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1460 nodes · 3028 edges · 132 communities (119 shown, 13 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 153 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d378b90a`
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
- default_factory
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
- File
- UploadFile
- TestClient

## God Nodes (most connected - your core abstractions)
1. `_login_admin()` - 34 edges
2. `create_test_engine()` - 31 edges
3. `ne()` - 28 edges
4. `_found()` - 27 edges
5. `se()` - 27 edges
6. `ue()` - 27 edges
7. `He()` - 26 edges
8. `e()` - 25 edges
9. `_admin_headers()` - 22 edges
10. `Base` - 22 edges

## Surprising Connections (you probably didn't know these)
- `test_salvar_documento_veiculo_remove_arquivo_se_create_falha()` --calls--> `salvar_arquivos()`  [INFERRED]
  tests/test_ui.py → bases/xtreme_system/api/routes/ui_routes/uploads.py
- `test_salvar_documentos_cliente_remove_arquivo_se_create_falha()` --calls--> `salvar_arquivos()`  [INFERRED]
  tests/test_ui.py → bases/xtreme_system/api/routes/ui_routes/uploads.py
- `_stub_crud_client()` --calls--> `register_crud_ui_routes()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_aceita_templates_injetado()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py
- `test_register_ui_simples_rolls_back_when_write_fails_late()` --calls--> `register_ui_simples()`  [INFERRED]
  tests/test_route_factories_ui.py → bases/xtreme_system/api/route_factories.py

## Import Cycles
- None detected.

## Communities (132 total, 13 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.22
Nodes (13): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+5 more)

### Community 2 - "test_ui.py"
Cohesion: 0.07
Nodes (66): TestClient, _admin_headers(), client(), _criar_cliente(), _FakeFile, _FakeUpload, _login_admin(), MonkeyPatch (+58 more)

### Community 3 - "_found"
Cohesion: 0.05
Nodes (61): Any, BaseModel, Path, Session, UploadFile, Helpers de upload: salvar arquivos em disco + DB e remover registros órfãos., Persiste cada arquivo em disco e cria o registro no DB.      Se ``create_fn`` la, Remove do DB registros cujo arquivo em disco não existe mais. (+53 more)

### Community 4 - "route_factories.py"
Cohesion: 0.16
Nodes (20): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+12 more)

### Community 5 - "core.py"
Cohesion: 0.24
Nodes (18): _atualizar_veiculo(), _criar_veiculo(), _ctx_form_veiculo(), _ctx_lista_veiculos(), _erro_veiculo(), _ok_veiculo(), Any, Cliente (+10 more)

### Community 6 - "core.py"
Cohesion: 0.05
Nodes (84): BaseModel, LancamentoInvestimentoRead, ClienteRead, Base, _calcular(), confirmar(), FechamentoVenda, FechamentoVendaCreate (+76 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (38): get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError, _NaoAutorizadoError, CurrentUser, Depends, Request (+30 more)

### Community 8 - "Usuario"
Cohesion: 0.11
Nodes (23): Engine, db_session(), Session, Sessão isolada com schema migrado em Postgres ou SQLite local., _reset_rate_limiters(), create_test_engine(), Helpers for test database bootstrap., _reset_postgres_schema() (+15 more)

### Community 9 - "veiculos.py"
Cohesion: 0.20
Nodes (18): _comprovantes_modal(), _ctx_form_compra(), _parse_compra_form(), Any, default_factory, File, HTMLResponse, Request (+10 more)

### Community 10 - "Base"
Cohesion: 0.06
Nodes (32): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Confirmar fechamento, Consulta (+24 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.14
Nodes (32): Cliente, ClienteCreate, ClienteUpdate, create(), delete(), get(), get_by_documento(), list_all() (+24 more)

### Community 12 - "core.py"
Cohesion: 0.13
Nodes (30): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Any, FastAPI, HTMLResponse (+22 more)

### Community 13 - "usuarios.py"
Cohesion: 0.18
Nodes (18): _ctx_form_custo(), _ctx_list_custos(), _parse_custo_form(), Any, Session, HTMX routes for custos de veículos., _validar_veiculo_fk(), create() (+10 more)

### Community 14 - "Tabelas"
Cohesion: 0.08
Nodes (22): `cliente`, `compra`, `custo_veiculo`, `documento_contrato_venda`, `documento_veiculo`, Enums, `fechamento_venda`, `imagem_comprovante_compra` (+14 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.36
Nodes (10): create(), delete(), DocumentoProcuracao, DocumentoProcuracaoCreate, DocumentoProcuracaoRead, get(), list_all(), list_by_veiculo() (+2 more)

### Community 17 - "Design"
Cohesion: 0.23
Nodes (14): Jinja2Templates, _ConflictModule, Any, Path, TestClient, Prova que register_ui_simples recebe Jinja2Templates como parâmetro (não mais o, _stub_crud_client(), _StubItem (+6 more)

### Community 18 - "test_api_auth.py"
Cohesion: 0.18
Nodes (26): _baixar_contrato_venda(), _confirmar_fechamento_venda(), _criar_venda(), _ctx_form_venda(), _ctx_lista_vendas(), _detalhe_fechamento_venda(), _erro_venda(), _form_fechamento_venda() (+18 more)

### Community 19 - "auditoria.py"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.07
Nodes (78): AdminUser, _found(), _csv_response(), Response, confirmar_fechamento_venda(), criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo() (+70 more)

### Community 21 - "perfis.py"
Cohesion: 0.24
Nodes (15): _ctx_auditoria(), _nomes_usuarios(), _pretty(), Any, date, HTMLResponse, Request, Response (+7 more)

### Community 22 - "core.py"
Cohesion: 0.36
Nodes (15): client(), _configurar(), _payload(), Any, MonkeyPatch, TestClient, Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed() (+7 more)

### Community 23 - "core.py"
Cohesion: 0.12
Nodes (37): auditar(), Auditoria, AuditoriaRead, count(), _filtros(), get(), Any, date (+29 more)

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
Cohesion: 0.27
Nodes (12): atualizar_config(), _enviar(), _formatar_mensagem(), get_config(), notificar_venda(), _PlaceholderDict, Session, Notificação de venda via WhatsApp (Evolution API): config, formatação e envio. (+4 more)

### Community 29 - "Setup"
Cohesion: 0.32
Nodes (12): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoRead, DocumentoVeiculoUpdate, get(), list_all() (+4 more)

### Community 30 - "test_auditoria.py"
Cohesion: 0.35
Nodes (14): client(), Decimal, TestClient, Fechamento financeiro de vendas., _seed_api(), _seed_venda(), session(), test_bloqueia_fechamento_duplicado_e_rateio_incompleto() (+6 more)

### Community 32 - "ui_dashboard"
Cohesion: 0.29
Nodes (13): _cliente_vendedor_modal(), default_factory, File, HTMLResponse, Request, Session, SessionDep, UIAdmin (+5 more)

### Community 33 - "core.py"
Cohesion: 0.30
Nodes (13): _investidor_e_veiculo(), CRUD end-to-end dos bricks, em SQLite in-memory (sem depender do Postgres)., CRUD de usuário: criar, buscar, listar, deletar e trocar senha., session(), test_atualizar_preco_ou_investidor_sincroniza_lancamento(), test_caixa_lancamento_veiculo_audit(), test_criar_veiculo_gera_lancamento_de_custo_e_reduz_saldo(), test_excluir_veiculo_apaga_lancamento_em_cascata() (+5 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.36
Nodes (10): create(), delete(), get(), ImagemComprovanteCompra, ImagemComprovanteCompraCreate, ImagemComprovanteCompraRead, list_all(), list_by_compra() (+2 more)

### Community 35 - "test_venda_whatsapp.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add trade and pending payment fields to venda table., Remove trade and pending payment fields from venda table., upgrade()

### Community 36 - "core.py"
Cohesion: 0.36
Nodes (10): create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead, list_all(), list_by_venda() (+2 more)

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
Cohesion: 0.13
Nodes (17): BaseSettings, create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings, TokenData, get_session() (+9 more)

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
Cohesion: 0.26
Nodes (12): Path, UploadFile, Shared helpers for HTMX route modules., Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_compra_dir() (+4 more)

### Community 51 - "5c6914b729c6_index_fks_veiculo.py"
Cohesion: 0.19
Nodes (24): _ctx_form_cliente(), _ctx_lista_cliente(), _documentos_modal(), Any, default_factory, File, HTMLResponse, RedirectResponse (+16 more)

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
Cohesion: 0.10
Nodes (44): agregados_investidores(), create(), criar_lancamento_fechamento(), criar_lancamento_veiculo(), deletar_lancamento_veiculo(), delete(), _descricao_veiculo(), get() (+36 more)

### Community 85 - "auditoria.py"
Cohesion: 0.40
Nodes (13): client(), TestClient, API vendas: CRUD via TestClient., Cria investidor, cliente e veiculo., _seed(), test_admin_cria_venda(), test_admin_lista_vendas(), test_atualizar_venda_concluida_para_pendente_libera_veiculo() (+5 more)

### Community 86 - "Response"
Cohesion: 0.36
Nodes (10): create(), delete(), DocumentoContratoVenda, DocumentoContratoVendaCreate, DocumentoContratoVendaRead, get(), list_all(), list_by_venda() (+2 more)

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
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `salvar_arquivos()` connect `_found` to `ui_dashboard`, `test_ui.py`, `core.py`, `veiculos.py`, `5c6914b729c6_index_fks_veiculo.py`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `Base` connect `core.py` to `create_test_engine`, `ui_configuracoes_salvar`, `core.py`, `route_factories.py`, `codebase-analysis.md`, `a1b2c3d4e004_add_debitos_to_venda.py`, `API - Xtreme Motors`, `usuarios.py`, `core.py`, `Response`, `core.py`, `Validação de Uploads Implementation Plan`, `Setup`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `_FakeSchema` connect `_found` to `core.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **What connects `Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON.`, `HTMX routes for clientes.`, `HTMX routes for compras.` to the rest of the system?**
  _237 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07343987823439878 - nodes in this community are weakly interconnected._
- **Should `_found` be split into smaller, more focused modules?**
  _Cohesion score 0.05098934550989345 - nodes in this community are weakly interconnected._