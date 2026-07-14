# Graph Report - tilefish  (2026-07-14)

## Corpus Check
- 144 files · ~54,350 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1338 nodes · 2600 edges · 204 communities (109 shown, 95 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 204 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0498dd64`
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
- Path
- test_venda_whatsapp.py
- perfis.py
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
- RedirectResponse
- Any
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Session
- Request
- SessionDep
- UIAdmin
- UIUser
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
- date
- Decimal

## God Nodes (most connected - your core abstractions)
1. `_found()` - 43 edges
2. `_login_admin()` - 34 edges
3. `ne()` - 28 edges
4. `se()` - 27 edges
5. `ue()` - 27 edges
6. `He()` - 26 edges
7. `e()` - 25 edges
8. `create_test_engine()` - 24 edges
9. `_admin_headers()` - 22 edges
10. `session()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `test_json_create_rolls_back_when_after_create_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_delete_rolls_back_when_before_delete_fails_after_writes()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `test_json_update_rolls_back_when_after_update_fails()` --calls--> `register_crud_routes()`  [INFERRED]
  tests/test_route_factories_atomicity.py → bases/xtreme_system/api/route_factories.py
- `main()` --indirect_call--> `session()`  [INFERRED]
  development/create_admin.py → tests/test_crud.py
- `ui_perfil_editar()` --calls--> `_found()`  [INFERRED]
  bases/xtreme_system/api/routes/ui_routes/perfis.py → bases/xtreme_system/api/deps.py

## Import Cycles
- None detected.

## Communities (204 total, 95 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (101): A(), ae(), an(), at(), B(), be(), bn(), bt() (+93 more)

### Community 1 - "create_test_engine"
Cohesion: 0.31
Nodes (10): create(), delete(), get(), Investidor, InvestidorCreate, InvestidorRead, InvestidorUpdate, list_all() (+2 more)

### Community 2 - "test_ui.py"
Cohesion: 0.07
Nodes (69): UploadFile, Retorna mensagem de erro do primeiro arquivo inválido, ou None.      Lote inteir, _validar_uploads(), _admin_headers(), client(), _criar_cliente(), _FakeFile, _FakeUpload (+61 more)

### Community 3 - "_found"
Cohesion: 0.36
Nodes (15): Form, HTMLResponse, Request, Response, SessionDep, UIAdmin, HTMX routes for usuarios., ui_usuario_criar() (+7 more)

### Community 4 - "route_factories.py"
Cohesion: 0.16
Nodes (20): create(), delete(), get(), list_all(), Perfil, PerfilCreate, PerfilRead, PerfilUpdate (+12 more)

### Community 5 - "core.py"
Cohesion: 0.10
Nodes (29): AdminUser, _csv_response(), Response, criar_usuario(), deletar_usuario(), _guard_lancamento_veiculo(), listar_auditoria(), listar_usuarios() (+21 more)

### Community 6 - "core.py"
Cohesion: 0.06
Nodes (59): Base, _baixar_contrato_venda(), _criar_venda(), _ctx_form_venda(), _erro_venda(), _gerar_contrato_pdf(), _ok_venda(), _parse_venda_form() (+51 more)

### Community 7 - "setup.py"
Cohesion: 0.07
Nodes (28): Cookie, Exception, JSONResponse, oauth2_scheme, get_current_user(), get_ui_user(), _NaoAdminError, _NaoAutenticadoError (+20 more)

### Community 8 - "Usuario"
Cohesion: 0.12
Nodes (16): Bug pre-existente — fora de escopo, Constantes, Contexto, Design, Design — Validação de uploads de imagens e documentos, Endpoints afetados, Error handling, Fluxo (+8 more)

### Community 9 - "veiculos.py"
Cohesion: 0.10
Nodes (71): Path, Shared helpers for HTMX route modules., _remover_upload(), _uploaded_file_path(), _uploads_cliente_dir(), _uploads_compra_dir(), _uploads_contrato_venda_dir(), _uploads_dir() (+63 more)

### Community 10 - "Base"
Cohesion: 0.07
Nodes (28): API - Xtreme Motors, Authentication, Authorization, Available Resources, Change Password, Clientes (Clients), Create Resource, Create User (+20 more)

### Community 11 - "API - Xtreme Motors"
Cohesion: 0.15
Nodes (31): Cliente, ClienteCreate, ClienteUpdate, create(), delete(), get(), get_by_documento(), list_all() (+23 more)

### Community 12 - "core.py"
Cohesion: 0.08
Nodes (39): _atomic_write(), _conflict_form_response(), _create_with_hook(), CrudModule, _delete_with_hook(), Any, FastAPI, HTMLResponse (+31 more)

### Community 13 - "usuarios.py"
Cohesion: 0.18
Nodes (18): _ctx_form_custo(), _ctx_list_custos(), _parse_custo_form(), Any, Session, HTMX routes for custos de veículos., _validar_veiculo_fk(), create() (+10 more)

### Community 14 - "Tabelas"
Cohesion: 0.09
Nodes (20): `cliente`, `compra`, `custo_veiculo`, `documento_contrato_venda`, `documento_veiculo`, Enums, `imagem_comprovante_compra`, `imagem_comprovante_venda` (+12 more)

### Community 15 - "Arquitetura — Xtreme Motors"
Cohesion: 0.11
Nodes (17): App FastAPI, Argon2 (pwdlib), Arquitetura — Xtreme Motors, Autenticação, Banco de dados, Camada API (`bases/xtreme_system/api/core.py`), Componentes de domínio (`components/xtreme_system/`), Dependências de autenticação (+9 more)

### Community 16 - "core.py"
Cohesion: 0.42
Nodes (9): create(), delete(), DocumentoProcuracao, DocumentoProcuracaoCreate, get(), list_all(), list_by_veiculo(), Session (+1 more)

### Community 17 - "Design"
Cohesion: 0.17
Nodes (11): File Structure, Global Constraints, Self-Review Notes, Task 1: Helper `_validar_uploads` + constants, Task 2: Middleware `_limite_request_size` (20 MB por request), Task 3: Wire validation into `ui_veiculo_imagens_upload`, Task 4: Wire validation into `ui_cliente_documentos_upload`, Task 5: Wire validation into `_criar_veiculo` (documents + vehicle doc) (+3 more)

### Community 19 - "auditoria.py"
Cohesion: 0.33
Nodes (10): create(), delete(), DocumentoVeiculo, DocumentoVeiculoCreate, DocumentoVeiculoUpdate, get(), list_all(), list_by_veiculo() (+2 more)

### Community 20 - "test_venda_whatsapp.py"
Cohesion: 0.23
Nodes (29): _ctx_investidores(), _ctx_lancamentos(), _erro_lancamento(), _form_ctx_investidor(), _ok_lancamentos(), Any, HTMLResponse, Request (+21 more)

### Community 21 - "perfis.py"
Cohesion: 0.18
Nodes (11): BaseModel, ClienteRead, CompraRead, DocumentoContratoVendaRead, DocumentoProcuracaoRead, UsuarioRead, VeiculoRead, VendaRead (+3 more)

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
Cohesion: 0.27
Nodes (16): client(), TestClient, API auth: login, proteção por autenticação e por papel., Create/trocar-senha/delete de usuário pela API JSON devem atribuir o admin     c, test_admin_escreve(), test_admin_nao_pode_se_autoexcluir(), test_admin_pode_excluir_outro_admin(), test_admin_pode_trocar_senha_de_outro() (+8 more)

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
Cohesion: 0.11
Nodes (18): BaseSettings, OAuth2PasswordRequestForm, login(), create_access_token(), decode_token(), get_settings(), Auth: settings, hash de senha e JWT (puro, sem FastAPI)., Settings (+10 more)

### Community 34 - "ui_configuracoes_salvar"
Cohesion: 0.40
Nodes (4): downgrade(), Add debitos column to venda table., Remove debitos column from venda table., upgrade()

### Community 35 - "test_venda_whatsapp.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add trade and pending payment fields to venda table., Remove trade and pending payment fields from venda table., upgrade()

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

### Community 43 - "a1b2c3d4e006_add_imagem_comprovante_compra_table.py"
Cohesion: 0.17
Nodes (11): Ambiente e dependências, Chave de autenticação, Comandos comuns, Convenções do projeto, Estrutura do projeto, Opção 1: PostgreSQL via Docker (recomendado), Opção 2: PostgreSQL via brew, Rodando (+3 more)

### Community 45 - "_UiCompatModule"
Cohesion: 0.40
Nodes (3): Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON., _UiCompatModule, ModuleType

### Community 47 - "Page"
Cohesion: 0.70
Nodes (4): Page, _login(), test_login_admin_abre_veiculos(), test_wizard_htmx_cria_veiculo()

### Community 51 - "5c6914b729c6_index_fks_veiculo.py"
Cohesion: 0.21
Nodes (17): _ctx_form_cliente(), _ctx_lista_cliente(), Any, HTMLResponse, RedirectResponse, Request, Session, SessionDep (+9 more)

### Community 71 - "codebase-analysis.md"
Cohesion: 0.17
Nodes (11): Codebase Analysis - Xtreme Motors, Opportunity 10: Profile assignment can surface FK failures as 500s, Opportunity 1: Sale lifecycle invariants are not enforced, Opportunity 2: Upload validation trusts client metadata and unsafe paths, Opportunity 3: Deleting parent records leaves upload files behind, Opportunity 4: The rate limiter leaks per-IP buckets, Opportunity 5: Investor aggregates are computed in Python on every render, Opportunity 6: Latest purchase lookup scans too much history (+3 more)

### Community 85 - "auditoria.py"
Cohesion: 0.06
Nodes (47): Engine, client(), TestClient, API compras: CRUD via TestClient., _seed(), test_admin_crud_compras(), test_compra_cliente_inexistente_retorna_400(), test_vendedor_nao_cria_compra() (+39 more)

### Community 86 - "Response"
Cohesion: 0.42
Nodes (9): create(), delete(), DocumentoContratoVenda, DocumentoContratoVendaCreate, get(), list_all(), list_by_venda(), Session (+1 more)

### Community 87 - "RedirectResponse"
Cohesion: 0.22
Nodes (8): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, 5. Graphify, 6. RTK, 7. Merge in a Worktree, Agent-Readable Workspace Map

### Community 88 - "SessionDep"
Cohesion: 0.48
Nodes (5): Session, Custos de veículos: CRUD e validações do componente., test_crud_custo_veiculo(), test_custo_veiculo_remove_em_cascata_ao_excluir_veiculo(), _veiculo()

### Community 89 - "UIAdmin"
Cohesion: 0.40
Nodes (4): downgrade(), Add km column to venda table., Remove km column from venda table., upgrade()

### Community 116 - "Form"
Cohesion: 0.26
Nodes (11): DeclarativeBase, Base, create(), delete(), get(), ImagemComprovanteVenda, ImagemComprovanteVendaCreate, ImagemComprovanteVendaRead (+3 more)

### Community 136 - "Path"
Cohesion: 0.16
Nodes (23): TipoCliente, Papel, create(), delete(), get(), get_by_placa(), list_all(), Decimal (+15 more)

### Community 137 - "test_venda_whatsapp.py"
Cohesion: 0.36
Nodes (10): client(), _configurar(), _payload(), Notificação de venda via WhatsApp: disparo best-effort no after_create., _seed(), test_criar_venda_dispara_notificacao(), test_falha_no_envio_nao_impede_criacao_da_venda(), test_notificacao_ignora_placeholder_desconhecido() (+2 more)

### Community 138 - "perfis.py"
Cohesion: 0.31
Nodes (7): _perfis_ctx(), HTMX routes for perfis., ui_perfil_atualizar(), ui_perfil_criar(), ui_perfil_editar(), ui_perfil_excluir(), ui_perfis()

## Knowledge Gaps
- **112 isolated node(s):** `Visão geral`, `Enums`, ``investidor``, ``veiculo``, ``cliente`` (+107 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **95 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Form` to `core.py`, `create_test_engine`, `route_factories.py`, `core.py`, `Path`, `API - Xtreme Motors`, `usuarios.py`, `core.py`, `auditoria.py`, `Response`, `core.py`, `core.py`, `core.py`, `Setup`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `_found()` connect `veiculos.py` to `_found`, `core.py`, `setup.py`, `perfis.py`, `5c6914b729c6_index_fks_veiculo.py`, `test_venda_whatsapp.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `create_test_engine()` connect `auditoria.py` to `test_ui.py`, `setup.py`, `test_venda_whatsapp.py`, `core.py`, `core.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `_found()` (e.g. with `_veiculos_comprador_modal()` and `_veiculos_vendedor_modal()`) actually correct?**
  _`_found()` has 41 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Visão geral`, `Enums`, ``investidor`` to the rest of the system?**
  _221 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `htmx.min.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0793040293040293 - nodes in this community are weakly interconnected._
- **Should `test_ui.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07157894736842105 - nodes in this community are weakly interconnected._