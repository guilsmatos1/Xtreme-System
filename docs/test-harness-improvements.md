# Melhorias no harness de testes

Análise do harness de testes (`tests/`, CI, pre-commit) — pytest + Postgres/SQLite,
factories com `polyfactory`, e2e com Playwright.

## 1. Engine/schema recriados por teste em Postgres — maior gargalo de performance ✅ implementado

`tests/database.py:create_test_engine()` é chamado a partir de fixtures
`function`-scoped (`db_session` em `tests/conftest.py`, e o `client`/`session`
redefinidos em cada arquivo de teste). Quando `TEST_DATABASE_URL` aponta pro
Postgres — é o que a CI faz no job `test:` — cada teste individual:

1. `DROP SCHEMA public CASCADE` + `CREATE SCHEMA public`
2. Roda `alembic upgrade head` do zero

Com ~236 `def test_` na suíte, isso significa até 236 execuções completas do
Alembic contra Postgres real por run de CI. Passa despercebido localmente
(SQLite in-memory é rápido), mas domina o tempo de execução contra Postgres.

**Sugestão:** engine/schema `session`-scoped (migra uma vez), isolamento por
teste via transação + `SAVEPOINT`/rollback (padrão clássico do SQLAlchemy para
testes), em vez de recriação de schema a cada teste.

**Implementado** em `tests/database.py`: `create_test_engine()` agora memoiza
(por processo, via `_migrated_urls`) quais `TEST_DATABASE_URL` já passaram por
`DROP SCHEMA` + `alembic upgrade head`. Chamadas seguintes para a mesma URL
pulam isso e apenas rodam `_truncate_all_tables()` (`TRUNCATE ... RESTART
IDENTITY CASCADE` em todas as tabelas), preservando isolamento entre testes
sem re-rodar as migrations a cada teste. Optou-se por TRUNCATE em vez do
padrão `SAVEPOINT`/rollback puro para não precisar alterar os ~11 arquivos de
teste que chamam `create_test_engine()` diretamente — a mudança fica contida
em `tests/database.py`. Caminho SQLite (usado localmente) não foi alterado.

## 2. Fixture `client` duplicada em ~8 arquivos, quase idêntica ✅ implementado

`test_api_auth.py`, `test_fechamento_venda.py`, `test_venda_whatsapp.py`,
`test_api_compras.py`, `test_api_vendas.py`, `test_ui.py`,
`test_api_rate_limit.py` e `test_api_health.py` cada um redefine seu próprio
`client` fixture repetindo: `create_test_engine()` → seed de `usuario` admin
(às vezes + `funcionario`/`vendedor`) → override do `get_session` →
`TestClient(app)` → cleanup. `test_route_factories_ui.py` repete o mesmo
bootstrap inline em funções de teste.

Isso é duplicação de harness — qualquer mudança na forma de autenticar/seedar
(ex.: novo campo obrigatório em `Usuario`) exige editar 8+ arquivos. Já há
variações sutis entre cópias (quais usuários são seedados) que sugerem drift.

**Sugestão:** centralizar em `tests/conftest.py` um `client` fixture
parametrizável (ex.: aceitando lista de usuários a seedar, ou fixtures
separadas `admin_client`/`funcionario_client`), reaproveitando `db_session`.
Isso também resolve o item 1 ao consolidar a criação do engine num único lugar.

**Implementado**: `tests/conftest.py` ganhou a fixture `make_client`, uma
fábrica de `TestClient` que cria o engine/sessão de teste, seeda o usuário
`seed` + uma lista opcional de usuários autenticáveis (`usuarios=[(username,
papel), ...]`), sobrescreve `get_session` e opcionalmente dispara
`_invoke_post_commit` (`invoke_post_commit=True`) ou popula dados extras via
callback (`seed=...`). Os 8 arquivos listados acima agora têm um `client`
fixture de poucas linhas que só declara os parâmetros específicos daquele
arquivo, delegando a criação para `make_client`.

## 3. Testes e2e não rodam na CI ✅ implementado

`pyproject.toml` tem `addopts = ["--ignore=tests/e2e"]`, e `.github/workflows/ci.yml`
só roda `pytest tests/ -q --cov=...` (que já ignora e2e) — não há job chamando
`make test-e2e-headless`. A suíte Playwright existe (`tests/e2e/conftest.py`
com `live_server_url`, seed de dados, servidor real) mas fica sem verificação
automática — regressões de UI só aparecem se alguém rodar localmente.

**Sugestão:** adicionar um job de e2e na CI (`make test-e2e-headless`), mesmo
que não-bloqueante inicialmente se for lento/flaky.

**Implementado**: novo job `test-e2e` em `.github/workflows/ci.yml`, com o
mesmo serviço Postgres do job `test`, instalando o Chromium do Playwright
(`uv run playwright install --with-deps chromium`) e rodando `make
test-e2e-headless` contra `TEST_DATABASE_URL`. Marcado com
`continue-on-error: true` por ora (item ainda não observado rodando
repetidamente na CI para avaliar flakiness) — pode virar bloqueante depois de
alguns runs estáveis.

## 4. Sem paralelização (`pytest-xdist`) ✅ implementado

`pytest-randomly` já está instalado (randomiza ordem, ajuda a pegar
acoplamento entre testes), mas não há `pytest-xdist`. Com o fix do item 1
(schema migrado uma vez), rodar com `-n auto` passa a ser viável e pode
reduzir bastante o tempo de CI.

**Implementado**: `pytest-xdist` adicionado em `pyproject.toml`, e `-n auto`
habilitado em `make test`, `make test-postgres`, `make coverage` e no job
`test:` da CI. No caminho SQLite (`create_test_engine()` sem
`TEST_DATABASE_URL`) cada worker já tem seu próprio banco in-memory, então
não precisou de mudança. No caminho Postgres, `tests/database.py` agora
isola cada worker num schema próprio (`test_<worker_id>`, ex. `test_gw0`),
via `-c search_path=...` na URL de conexão — evita que workers colidam no
mesmo `public` compartilhado ao rodar `DROP SCHEMA`/`TRUNCATE` em paralelo.

Três bugs pré-existentes, não causados por este item mas que impediam
verificar/usar a suíte contra Postgres (mesmo sem xdist, sequencialmente —
confirmado reproduzindo no `master` antes desta mudança), foram corrigidos
no processo:

- `alembic/env.py`: `config.set_main_option("sqlalchemy.url", ...)` quebrava
  com `ValueError: invalid interpolation syntax` sempre que a URL continha
  `%` (como a querystring `options=-c%20search_path%3D...` usada para o
  isolamento por schema) — `ConfigParser` trata `%` como início de
  interpolação. Corrigido escapando `%` como `%%` antes de passar a URL.
- `tests/conftest.py`: a fixture `make_client` nunca fechava a `Session`
  usada para sobrescrever `get_session` — ao contrário do `get_session` real
  (que fecha a sessão após cada request), o `override()` de teste só dava
  `yield session` e nunca chamava `session.close()`. Como `engine.dispose()`
  no teardown não força o fechamento de uma conexão ainda em uso por uma
  `Session` viva, a conexão ficava "idle in transaction" no Postgres até o
  GC eventualmente coletá-la — o que travava o próximo `TRUNCATE`/`DROP
  SCHEMA` indefinidamente. Corrigido guardando as sessões criadas e
  fechando-as explicitamente no teardown, antes de `engine.dispose()`.
- `tests/test_route_factories_ui.py`: três testes (e o helper
  `_stub_crud_client`, usado por mais quatro) criavam engine/sessão via
  `create_test_engine()` diretamente, sem fixture, e nunca chamavam
  `session.close()`/`engine.dispose()` — mesmo problema de conexão
  vazada/travando o próximo teste. Corrigido registrando
  `request.addfinalizer(session.close)` / `request.addfinalizer(engine.dispose)`.

Com os três fixes, `TEST_DATABASE_URL=... uv run pytest tests/ -q -n auto`
roda a suíte completa sem travar. Restam 4 falhas pré-existentes e não
relacionadas (confirmadas reproduzindo em `master`, sem as mudanças deste
item), específicas de Postgres — divergências de comportamento
SQLite-vs-Postgres em constraint de FK e em `ILIKE` sobre coluna enum — que
ficam de fora do escopo deste item.

## 5. Cobertura sem config declarada em `pyproject.toml`

O `--cov-fail-under=75` só existe embutido em `Makefile`/`ci.yml`, não há
`[tool.coverage.run]`/`[tool.coverage.report]` (ex.: `omit`, `exclude_lines`
para `if TYPE_CHECKING`, `# pragma: no cover`). Ganho pequeno, mas centraliza
threshold e exclusões num único lugar versionado.
