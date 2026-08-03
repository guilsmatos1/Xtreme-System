# Improvement opportunities

- **Generated:** 2026-08-01T13:30:51-03:00
- **Total:** 13

## imp-20260801-001 — Remove `lazyload` on the DRE query that forces an N+1 over `venda → veiculo → investidor`

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** performance, n+1, orm, reports, eager-loading
- **Files affected:** `components/xtreme_system/fechamento_venda/core.py`, `bases/xtreme_system/api/routes/ui_routes/relatorios.py`, `bases/xtreme_system/api/templates/_dre_resultado.html`
- **Related opportunities:** imp-20260801-011, imp-20260801-013

### Location

`components/xtreme_system/fechamento_venda/core.py:314` — `listar_para_dre`

```python
    if not _schema_disponivel(session):
        raise FechamentoVendaError(ERRO_SCHEMA_DESATUALIZADO)
    query = session.query(FechamentoVenda).options(
        lazyload(FechamentoVenda.venda),
        lazyload(FechamentoVenda.usuario),
        lazyload(FechamentoVenda.participacoes),
    )
    if investidor_id is not None:
        query = query.join(Venda, FechamentoVenda.venda_id == Venda.id).join(
            Veiculo, Venda.veiculo_id == Veiculo.id
        )
        query = query.filter(Veiculo.investidor_id == investidor_id)
```

### Description

`listar_para_dre` explicitly overrides the model's `lazy="selectin"` relationships
(`components/xtreme_system/fechamento_venda/core.py:65-70`) with `lazyload`, so `FechamentoVenda.venda`
is not loaded with the result set. Both consumers of this query then walk the relationship chain per
row: the HTML report at `bases/xtreme_system/api/templates/_dre_resultado.html:105-107` renders
`f.venda.veiculo.modelo`, `f.venda.veiculo.investidor.nome` and `f.venda.vendedor.username`, and the
CSV export at `bases/xtreme_system/api/routes/ui_routes/relatorios.py:151-166` reads the same chain.

Each `f.venda` access issues one `SELECT venda`, and because `Venda` declares `cliente`, `veiculo`,
`veiculo_troca` and `vendedor` as `lazy="selectin"`
(`components/xtreme_system/venda/core.py:125-130`), loading a single `Venda` fires roughly four more
statements. The default DRE window is the last 12 months (`MESES_PADRAO = 11` in
`bases/xtreme_system/api/routes/ui_routes/relatorios.py:24`), so the row count grows with every sale
that gets closed.

### Why it matters

At 200 closings in the selected period the report issues on the order of 1000 statements instead of a
handful, all serialized on one connection. The DRE page and its CSV export are the two slowest admin
screens in the system and they degrade linearly with business volume — exactly the growth profile the
report is meant to summarize.

### Concrete fix

Replace the three `lazyload` options with an eager chain covering what the template and export
actually read, keeping the relationship-level `selectin` defaults for the rest.

### Example

```python
from sqlalchemy.orm import joinedload, selectinload

query = session.query(FechamentoVenda).options(
    joinedload(FechamentoVenda.venda)
    .joinedload(Venda.veiculo)
    .joinedload(Veiculo.investidor),
    joinedload(FechamentoVenda.venda).joinedload(Venda.vendedor),
    joinedload(FechamentoVenda.usuario),
    selectinload(FechamentoVenda.participacoes),
)
```

### Potential savings

Collapses roughly five queries per closing row into a constant two or three statements for the whole
report — about 1000 round trips saved on a 200-row DRE.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - The `lazyload` call, the template access, and the CSV export access were each read directly.
  - `Venda`'s four `lazy="selectin"` relationships were verified in the model, so the per-row cost is
    not speculative.
- **Weaknesses:**
  - Real DRE row counts in production are unknown; the impact scales with closings per period.
  - The `lazyload` may have been added deliberately to avoid a cartesian blow-up on
    `participacoes`; keeping that one as `selectinload` rather than `joinedload` preserves that.
- **Suggested checks:**
  - Run the DRE page with SQLAlchemy echo enabled and count statements before and after.

## imp-20260801-002 — Rate-limit middleware runs a synchronous DB transaction on the event loop for every request

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** performance, blocking-io, middleware, event-loop, rate-limit
- **Files affected:** `bases/xtreme_system/api/setup.py`, `components/xtreme_system/database/rate_limit.py`
- **Related opportunities:** imp-20260801-009

### Location

`bases/xtreme_system/api/setup.py:301` — `_rate_limit`

```python
@app.middleware("http")
async def _rate_limit(request: Request, call_next: Callable[[Request], Any]) -> Any:
    path = request.url.path
    if path.startswith("/static/") or path in _ROTAS_ISENTAS_RATE_LIMIT:
        return await call_next(request)

    client_ip = _client_ip(request)
    store = _get_rate_limit_store()

    if request.method == "POST" and path.endswith("/login"):
        allowed, retry_after = store.allow(
            f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
        )
```

### Description

`_rate_limit` is an `async def` middleware, so its body runs directly on the asyncio event loop. It
calls `store.allow(...)` synchronously, and `DatabaseRateLimiterStore.allow`
(`components/xtreme_system/database/rate_limit.py:47-72`) opens its own connection with
`self._bind.begin()` and executes a cleanup `DELETE` plus up to six `UPDATE`/`INSERT`/`SELECT`
statements inside a retry loop before returning.

Every non-static request pays this cost — including the HTMX partial requests that the UI fires on
sort, filter, pagination, and every form submit. While one request is inside `allow`, no other
request in the process can make progress on the loop.

### Why it matters

This serializes the whole application behind a blocking database round trip on the hottest possible
path. Under concurrent use the event loop becomes the bottleneck before any individual query does,
and latency added here is added to 100% of requests rather than to one slow screen.

### Concrete fix

Push the blocking store call off the loop with `starlette.concurrency.run_in_threadpool`, which is
what FastAPI already does for the synchronous route handlers in this codebase.

### Example

```python
from starlette.concurrency import run_in_threadpool

# login bucket
allowed, retry_after = await run_in_threadpool(
    store.allow, f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
)

# general bucket
allowed, retry_after = await run_in_threadpool(
    store.allow, bucket, _GERAL_LIMIT, _GERAL_WINDOW_SECONDS
)
```

### Potential savings

Removes a full database transaction from the event loop on every request; the same work then runs in
the threadpool where concurrent requests can overlap.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both the `async def` middleware and the synchronous, multi-statement `allow` implementation were
    read directly.
  - The in-memory fallback store (`_MemoryRateLimiterStore`, `bases/xtreme_system/api/setup.py:88`)
    confirms the DB-backed store is the deployed path only in some configurations, which is stated
    below as a caveat.
- **Weaknesses:**
  - Which store is active depends on runtime configuration (`_get_rate_limit_store`,
    `bases/xtreme_system/api/setup.py:130-138`); with the memory store the blocking cost is trivial.
  - The thread-pool fix trades event-loop blocking for connection-pool pressure under high
    concurrency.
- **Suggested checks:**
  - Confirm which store the production deployment selects, then measure p99 latency on a trivial
    endpoint under concurrent load with and without the change.

## imp-20260801-003 — Vehicle list route disables pagination and renders the whole `veiculo` table on every request

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** performance, unbounded-payload, pagination, htmx
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/crud_ui/query.py`
- **Related opportunities:** imp-20260801-004, imp-20260801-006

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos.py:161` — `register_crud_ui_routes` listing config

```python
    listing=ListingSpec(
        searchable=True,
        paginated=False,
        source="query",
        query_func=veiculo.query,
        search_query_func=veiculo.search_query,
        sort_fields={
            "modelo": SortField("modelo", veiculo.Veiculo.modelo),
            "placa": SortField("placa", veiculo.Veiculo.placa),
            "tipo": SortField("tipo", veiculo.Veiculo.tipo),
            "ano": SortField("ano", veiculo.Veiculo.ano),
            "km": SortField("km", veiculo.Veiculo.km),
```

### Description

`paginated=False` makes `query_list` force `limit = None` and `offset = 0`
(`bases/xtreme_system/api/crud_ui/query.py:137-138`), so `_query_sorted_list` emits a query with no
`LIMIT` at all. The `limit`/`offset` query parameters accepted by `_list`
(`bases/xtreme_system/api/crud_ui/routes.py:467-468`) are silently ignored for this resource.

Every `/ui/veiculos` render — including each HTMX sort and filter round trip — loads the entire
non-cancelled fleet joined to `investidor`, plus a `selectin` load of every related `Investidor`
(`components/xtreme_system/veiculo/core.py:112`). The list context then calls
`compra.latest_debitos_by_veiculo_ids` with every returned id
(`bases/xtreme_system/api/routes/ui_routes/veiculos.py:96-97`), running the window-function query over
the whole `compra` table, and the template renders one row per vehicle.

### Why it matters

This is the most-used screen in the application and its cost grows linearly with total inventory
ever registered, not with what the user is looking at. Each sort click re-fetches and re-renders
everything, so response size and time degrade steadily as the dealership accumulates vehicles.

### Concrete fix

Drop `paginated=False` so the resource uses the same server-side `LIMIT`/`OFFSET` path as `vendas`,
`compras`, `clientes`, and `custos_veiculos`, all of which already declare `source="query"` without
disabling pagination.

### Potential savings

Bounds each vehicle-list request to the 50-row default page instead of the full table, and shrinks
the `latest_debitos_by_veiculo_ids` input from every vehicle to one page's worth of ids.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The `paginated=False` flag and the `query_list` branch that turns it into an unbounded query were
    both read directly.
  - Four sibling resources use the same factory with pagination enabled, so the fix is a
    configuration change, not a new abstraction.
- **Weaknesses:**
  - Pagination may have been disabled deliberately to support client-side filtering or an "all
    vehicles" view in the template; enabling it could change visible behavior.
  - Current fleet size is unknown, so the present-day latency cost is not quantified.
- **Suggested checks:**
  - Inspect `veiculos.html` / `_linhas_veiculos.html` for client-side filtering that assumes the full
    dataset before flipping the flag.

## imp-20260801-004 — Vehicle form context loads every vehicle id and the debits of the entire fleet on each form open

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** performance, unbounded-payload, form, reference-lookup
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-005

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos.py:57` — `_ctx_form_veiculo`

```python
def _ctx_form_veiculo(session: Session) -> dict[str, Any]:
    veiculo_ids = veiculo.list_ids(session)
    debitos_por_veiculo = compra.latest_debitos_by_veiculo_ids(session, veiculo_ids)
    return {
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidor.list_all(session),
        "clientes": cliente.list_all(session),
        "tipos_cliente": list(cliente.TipoCliente),
        "debitos_por_veiculo": debitos_por_veiculo,
    }
```

### Description

Opening the "novo veículo" or "editar veículo" form runs `veiculo.list_ids`, which selects every id in
the table (`components/xtreme_system/veiculo/core.py:245-246`), feeds all of them into
`compra.latest_debitos_by_veiculo_ids` — a window-function scan over `compra` partitioned by
`veiculo_id` (`components/xtreme_system/compra/core.py:151-173`) — and additionally materializes the
complete `cliente` and `investidor` tables for the form's select fields.

None of these are bounded by what the form displays. The same module already registers the bounded
alternative: `register_reference_lookup_routes`
(`bases/xtreme_system/api/crud_ui/routes.py:400-447`) is documented as "bounded, server-side lookups
used by foreign-key form fields" and caps each page at 50 rows.

### Why it matters

A modal that shows one vehicle costs a full scan of two tables plus a window aggregation over a
third, on a route users hit constantly. The client select in particular grows with the customer base
— the fastest-growing table in a dealership — so form-open latency and HTML size worsen indefinitely.

### Concrete fix

Move the `clientes` and `investidores` selects to the existing reference-lookup endpoint, and scope
the debits lookup to the vehicle being edited (`compra.get_latest_by_veiculo`) instead of the whole
fleet; for the create form there is no vehicle yet, so the map can be omitted entirely.

### Potential savings

Removes one full-table id scan, one full `cliente` scan, and one fleet-wide window aggregation from
every vehicle form open.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - `list_ids`, `latest_debitos_by_veiculo_ids`, and the bounded lookup route were each read directly.
  - The codebase already contains the intended pattern, so the fix reuses existing machinery.
- **Weaknesses:**
  - The template may index `debitos_por_veiculo` for a vehicle picker rather than a single vehicle;
    that usage was not read.
  - `cliente.list_all` may be required by an inline "novo cliente" sub-form in the same template.
- **Suggested checks:**
  - Read `_form_veiculo.html` to confirm which keys are consumed and whether the selects can be
    switched to the lookup endpoint.

## imp-20260801-005 — `_ok_compra` re-lists the entire `compra` table after every purchase write

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** performance, unbounded-payload, htmx, write-path
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-004, imp-20260801-008

### Location

`bases/xtreme_system/api/routes/ui_routes/compras.py:354` — `_ok_compra`

```python
def _ok_compra(request: Request, session: Session, user: Any) -> HTMLResponse:
    compras = compra.list_all(session)
    return ok_response(
        templates,
        request,
        "_compras_ok.html",
        user=user,
        list_key="compras",
        lista=compras,
        ctx_list={},
    )
```

### Description

`_ok_compra` is the success response for the purchase create flow (`_criar_compra`,
`bases/xtreme_system/api/routes/ui_routes/compras.py:367-375` and its success path) and calls
`compra.list_all(session)` with no limit or offset. Each `Compra` eagerly loads `cliente`, `veiculo`,
`usuario` and `comprovantes` via `lazy="selectin"`
(`components/xtreme_system/compra/core.py:65-68`), so the whole purchase history — with all related
rows — is materialized and re-rendered to build a fragment for one newly created row.

The generic CRUD factory does this correctly: `write_ok_response`
(`bases/xtreme_system/api/crud_ui/routes.py:640-662`) reconstructs the caller's `ListState` from the
request and reuses the paginated `query_list`.

### Why it matters

Every purchase creation gets slower as the purchase history grows, and the response payload grows with
it. This is a write path a user waits on synchronously, and the cost is unbounded by design rather
than by page size.

### Concrete fix

Replace the bare `list_all` with the same state-aware listing the factory uses — read the current
list state from the request and call `query_list` with the compras `ListingSpec` already defined at
`bases/xtreme_system/api/routes/ui_routes/compras.py:535-539`.

### Potential savings

Bounds the post-create response to one page of purchases instead of the full table plus four
`selectin` loads per row.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The unbounded `list_all` call, the `selectin` relationships on `Compra`, and the correct sibling
    implementation in `write_ok_response` were all read directly.
- **Weaknesses:**
  - `_compras_ok.html` may depend on receiving the complete list to recompute a total; that template
    was not read.
  - Purchase volume in production is unknown.
- **Suggested checks:**
  - Read `_compras_ok.html` to confirm it only re-renders the visible rows.

## imp-20260801-006 — `query_list` loads the whole table into Python to sort or search `source="functions"` listings

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** performance, unbounded-payload, sorting, pagination
- **Files affected:** `bases/xtreme_system/api/crud_ui/query.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-011, imp-20260801-013

### Location

`bases/xtreme_system/api/crud_ui/query.py:186` — `query_list`

```python
        if not sort or sort not in listing.sort_fields:
            return _paginated_list(callable_list, session, limit, offset)
        result = _page_list(
            sorted_list(
                _paginated_list(callable_list, session, None, 0),
                sort,
                order,
                listing.sort_fields,
            ),
            limit,
            offset,
        )
```

### Description

When a listing uses `source="functions"` and the user clicks any sortable column, `query_list` calls
`_paginated_list(callable_list, session, None, 0)` — explicitly `limit=None`, `offset=0` — to fetch
every row, sorts the full list in Python with `sorted_list`, and only then slices one page out with
`_page_list`. The search branches at lines 158-179 behave the same way: `_search_list` and
`searchable_module.search` return unbounded lists that are sorted and sliced in memory.

`_VEICULOS_LISTING` (`bases/xtreme_system/api/routes/ui_routes/veiculos.py:124-129`) is configured
exactly this way, so any consumer of that spec pays the full-table cost per sorted or searched
request. Sorting also loses index support entirely, because ordering happens after the rows leave the
database.

### Why it matters

Page-level pagination becomes cosmetic: the database still returns every row, the ORM still
constructs every entity (with its `selectin` relationships), and the process still holds them all in
memory — only to discard all but 50. Both latency and peak memory scale with table size on a path the
user triggers by clicking a column header.

### Concrete fix

Route sortable listings through the SQL path that already exists in the same module,
`_query_sorted_list` (`bases/xtreme_system/api/crud_ui/query.py:75-101`), which applies `ORDER BY`,
`OFFSET` and `LIMIT` in the database. Where a `SortField` has no SQL expression, push at least
`LIMIT`/`OFFSET` down and treat Python-side sorting as the explicit exception rather than the default.

### Potential savings

Turns a full-table fetch plus in-memory sort into a single indexed `ORDER BY … LIMIT 50` for every
sorted or searched listing built on `source="functions"`.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The unbounded `_paginated_list(..., None, 0)` call and the SQL-side alternative live in the same
    file and were both read.
  - `SortField` already carries a `sql` expression alongside the `python` accessor, so the
    infrastructure for the fix exists.
- **Weaknesses:**
  - Only `veiculos` was confirmed to use `source="functions"`; other callers of `_VEICULOS_LISTING`
    were not enumerated, so the blast radius may be narrower than the generic code suggests.
  - Some `SortField.python` accessors sort on derived values (`sort_key` follows `.nome` and
    `.value`), which cannot always be expressed in SQL without extra joins.
- **Suggested checks:**
  - Enumerate every `ListingSpec(source="functions")` in the codebase and check which sort fields lack
    a usable SQL expression.

## imp-20260801-007 — `venda.data_venda` has no index despite driving every dashboard and report range filter

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** performance, indexing, migration, dashboard
- **Files affected:** `components/xtreme_system/venda/core.py`, `bases/xtreme_system/api/routes/ui_routes/dashboard.py`, `alembic/versions`
- **Related opportunities:** imp-20260801-010

### Location

`components/xtreme_system/venda/core.py:99` — `Venda` model columns

```python
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculo.id"), index=True)
    vendedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), index=True
    )
    data_venda: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valor_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_entrada: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    km: Mapped[int | None] = mapped_column()
```

### Description

Every foreign key on `Venda` is indexed, but `data_venda` — the column all time-bounded analytics
filter on — is not, and no migration adds one (`rg "data_venda" alembic/versions` returns only the
nullability change in `d9babf49fd9b`). The unindexed column is filtered by:

- `_resumo_ticket_vendas_mes` (`bases/xtreme_system/api/routes/ui_routes/dashboard.py:82-92`), which
  runs `count`, `sum` and `avg` over `data_venda >= inicio AND data_venda < fim`
- `resumo_mes` (`components/xtreme_system/venda/core.py:451-460`)
- `tendencia_por_periodo` (`components/xtreme_system/venda/core.py:535-540`)
- `desempenho_vendas_mensal` (`components/xtreme_system/venda/core.py:614-626`)

The dashboard alone executes three of these per page load, each scanning the full `venda` table.

### Why it matters

These are the queries behind the admin landing page, so every dashboard visit performs several full
scans of the sales table. The cost grows with total sales ever recorded even though each query only
needs the last one to twelve months, and the scans do not benefit from the existing partial unique
index on `(veiculo_id)`.

### Concrete fix

Add a migration creating an index on `venda(data_venda)`; if the workload justifies it, make it a
composite `(data_venda, status)` so the ubiquitous `status != 'cancelado'` predicate is covered too.
The write-path cost is one extra index maintained on a table with modest insert volume.

### Example

```python
"""index venda.data_venda"""

revision = "<new_revision_id>"
down_revision = "<current_head>"


def upgrade() -> None:
    op.create_index(
        op.f("ix_venda_data_venda"), "venda", ["data_venda"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_venda_data_venda"), table_name="venda")
```

### Potential savings

Replaces a full `venda` scan with an index range scan on every dashboard KPI, trend, and monthly
performance query.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The absence of the index was confirmed in both the model and the full migration history.
  - Four distinct call sites filtering on `data_venda` were read directly.
- **Weaknesses:**
  - `tendencia_por_periodo` and `desempenho_vendas_mensal` group by `extract(...)` expressions, which
    an index on the raw column cannot serve for the grouping step — only for the range predicate.
  - On a small `venda` table the planner may prefer a sequential scan regardless.
- **Suggested checks:**
  - Run `EXPLAIN` on the dashboard KPI query at production row counts before and after adding the
    index.

## imp-20260801-008 — Investor ledger renders every `lancamento` with no pagination, on read and after every write

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** performance, unbounded-payload, pagination, htmx
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`
- **Related opportunities:** imp-20260801-005

### Location

`bases/xtreme_system/api/routes/ui_routes/lancamentos.py:38` — `_ctx_lancamentos`

```python
def _ctx_lancamentos(
    session: Session, investidor_id: int, sort: str = "", order: str = "asc"
) -> dict[str, Any]:
    query = caixa.query_by_investidor(session, investidor_id)
    field = _LANCAMENTO_SORT_FIELDS.get(sort, "id")
    col = getattr(caixa.LancamentoInvestimento, field)
    order_expr = col.desc() if order == "desc" else col.asc()
    lancamentos = list(query.order_by(order_expr).all())
    return {
        "investidor": found(investidor.get(session, investidor_id), "Investidor"),
        "lancamentos": lancamentos,
        "saldo": caixa.saldo(session, investidor_id),
```

### Description

`_ctx_lancamentos` fetches the investor's complete ledger with no `LIMIT`, and the route accepts no
`limit`/`offset` parameters (`bases/xtreme_system/api/routes/ui_routes/lancamentos.py:98-114`). The
same unbounded context is rebuilt after every create, update, and delete
(lines 189, 209, 230), so each ledger mutation re-queries and re-renders the entire history.

Unlike a vehicle or client list, a ledger is append-only: entries accumulate for every vehicle
purchase, sale closing, and manual contribution tied to that investor, and are never pruned.

### Why it matters

The screen gets monotonically slower for the investors who use the system most, and each write
amplifies the cost because the full list is re-rendered as the success fragment. There is no upper
bound on response size.

### Concrete fix

Add `limit`/`offset` parameters to the route with the same 50-row default the CRUD factory uses
(`bases/xtreme_system/api/crud_ui/routes.py:467-468`), apply them to the query, and have the write
handlers pass the caller's current page through when rebuilding the fragment.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The unbounded query and all four call sites that rebuild the context were read directly.
  - The route signature was confirmed to expose only `sort`/`order`, never `limit`/`offset`.
- **Weaknesses:**
  - Ledger sizes per investor are unknown; for a small dealership this may stay in the low hundreds
    for years.
  - The CSV export at lines 117-135 is intentionally unbounded and should stay that way.
- **Suggested checks:**
  - Measure the row count of `lancamento_investimento` grouped by `investidor_id` in production.

## imp-20260801-009 — Purchase creation performs full-file reads and `fsync` writes inside an `async` handler

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** performance, blocking-io, event-loop, uploads
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/uploads.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `components/xtreme_system/upload_file/core.py`
- **Related opportunities:** imp-20260801-002

### Location

`bases/xtreme_system/api/routes/ui_routes/uploads.py:48` — `salvar_arquivos`

```python
    try:
        for arquivo in arquivos:
            if not arquivo.filename:
                continue
            suffix = Path(arquivo.filename).suffix.lower()
            filename = f"{uuid4().hex}{suffix}"
            content = arquivo.file.read()
            data = schema.model_validate(
                {fk_field: fk_id, "url": f"{url_prefix}/{filename}"}
            )
            path = escrever_upload_atomico(session, upload_dir, filename, content)
            cleanup_paths.append((path, upload_dir / f".{filename}.tmp"))
```

### Description

`_criar_compra` is declared `async def`
(`bases/xtreme_system/api/routes/ui_routes/compras.py:368`) and calls `salvar_arquivos` directly at
line 473. That helper reads each uploaded file fully into memory with `arquivo.file.read()` and hands
the bytes to `escrever_upload_atomico`
(`components/xtreme_system/upload_file/core.py:44-57`), which writes a temp file, calls `os.fsync`,
and then `os.replace` — all synchronous, all on the event loop.

The sibling upload route `ui_compra_comprovantes_upload`
(`bases/xtreme_system/api/routes/ui_routes/compras.py:225-244`) is a plain `def`, so FastAPI runs it
in the threadpool and does not have this problem.

### Why it matters

`fsync` is one of the slowest calls a request can make and its duration depends on disk contention,
not on application logic. Blocking the event loop for the duration of several receipt uploads stalls
every other in-flight request in the process. Reading whole files into memory also makes peak memory
proportional to upload size times concurrency.

### Concrete fix

Either make `_criar_compra` a synchronous `def` (matching the sibling upload route, which requires
replacing `await request.form()` with the form dependency), or wrap the `salvar_arquivos` call in
`starlette.concurrency.run_in_threadpool`.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The `async def` declaration, the direct `salvar_arquivos` call inside it, and the `fsync` in the
    write helper were each read directly.
  - A correctly-shaped sibling route exists in the same file, so the target pattern is established.
- **Weaknesses:**
  - `_criar_compra` needs `await request.form()`, so converting it to a sync handler is not a
    one-line change; the threadpool wrapper is the smaller fix.
  - Typical receipt sizes are unknown; `validar_uploads` may already cap them.
- **Suggested checks:**
  - Read `upload_validation.validar_uploads` for a size cap, and time a multi-receipt purchase
    creation while a second request is in flight.

## imp-20260801-010 — Dashboard activity feed issues one user query per audit row

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** performance, n+1, dashboard
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/dashboard.py`, `bases/xtreme_system/api/routes/ui_routes/auditoria.py`
- **Related opportunities:** imp-20260801-007

### Location

`bases/xtreme_system/api/routes/ui_routes/dashboard.py:119` — `_atividades_recentes`

```python
        usu = usuario.get(session, usuario_id)
        return usu.username if usu else "Sistema"

    return [
        {
            "titulo": _atividade_titulo(row),
            "detalhe": f"{row.tabela} · {row.tipo_acao}",
            "usuario": _nome_usuario(row.usuario_id),
            "quando": row.criado_em.strftime("%d/%m/%Y %H:%M"),
        }
        for row in auditoria.query(session, limit=8)
    ]
```

### Description

The comprehension calls `_nome_usuario` per audit row, and each call runs `usuario.get`, a primary-key
lookup issued as a separate statement. The audit query is capped at eight rows, so the cost is bounded
at eight extra round trips — but it is paid on every dashboard load, and the identity map only helps
when the same user appears twice.

The audit listing route already implements the batched version of exactly this lookup:
`_nomes_usuarios` (`bases/xtreme_system/api/routes/ui_routes/auditoria.py:56-69`) collects the distinct
`usuario_id` values and resolves them with a single `IN` query.

### Why it matters

It is a textbook N+1 sitting on the admin landing page, and the bound comes only from the hard-coded
`limit=8`. Raising that limit — a one-character change someone will eventually make — scales the query
count linearly with no other code change.

### Concrete fix

Fetch the eight audit rows first, then resolve their user names with the existing batched helper
pattern from `auditoria.py`, and look names up from the resulting dict.

### Potential savings

Collapses eight per-row primary-key lookups into one `IN` query per dashboard render.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both the N+1 and the correct batched sibling implementation were read directly.
  - The fix reuses a pattern already present in the codebase.
- **Weaknesses:**
  - Absolute impact is small at `limit=8`; this is a latent scaling problem more than a current
    bottleneck, which is why it is ranked below the unbounded findings.
- **Suggested checks:**
  - None required; the code is unambiguous.

## imp-20260801-011 — CSV export routes materialize entire tables with no limit

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** performance, unbounded-payload, export, memory
- **Files affected:** `bases/xtreme_system/api/crud_ui/routes.py`, `bases/xtreme_system/api/crud_ui/query.py`, `bases/xtreme_system/api/routes/ui_routes/relatorios.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-006

### Location

`bases/xtreme_system/api/crud_ui/routes.py:520` — `_exportar`

```python
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, user: UIUser, q: str = "") -> Response:
        lista = query_list(
            session, module, listing=config.listing, state=ListState(q=q)
        )
        if config.columns is not None:
            export_columns: list[
                tuple[ColumnSpec[EntityT], Callable[[EntityT], Any]]
            ] = []
            for column in config.columns:
                export_value = column.export
                if export_value is None or (
```

### Description

`_exportar` builds a default `ListState(q=q)` whose `limit` is `None`
(`bases/xtreme_system/api/crud_types.py:195-201`), so `query_list` emits no `LIMIT`. Every ORM entity
for the whole resource is instantiated with its `selectin` relationships, then a second full copy is
built as a list of lists of formatted strings, and `csv_response` holds the result in memory before
returning it. The same shape appears in the DRE export
(`bases/xtreme_system/api/routes/ui_routes/relatorios.py:150-166`), the investor export
(`bases/xtreme_system/api/routes/ui_routes/investidores.py:145-163`), and the ledger export
(`bases/xtreme_system/api/routes/ui_routes/lancamentos.py:117-135`).

Exporting everything is the intended behavior for a CSV, so the issue is not the row count but that
it is done fully in memory in three simultaneous representations, on a synchronous request.

### Why it matters

Peak memory is proportional to table size times concurrent exports, with no ceiling and no
back-pressure. A few users exporting large resources at once can drive the process into swap or an
OOM kill, and each export holds a database connection for its entire duration.

### Concrete fix

Stream the export instead of buffering it: iterate the query with `yield_per`, format each row as it
arrives, and return a `StreamingResponse`. That keeps the full-export semantics while making memory
constant.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - The `ListState` default of `limit=None` and the resulting unbounded `query_list` call were both
    verified in source.
  - Four separate export routes share the pattern.
- **Weaknesses:**
  - Actual table sizes are unknown, so this may be entirely harmless at current scale — it is a
    resilience ceiling rather than a measured slowdown.
  - Streaming changes error handling: a failure mid-stream cannot change the HTTP status, which is a
    real behavioral trade-off.
- **Suggested checks:**
  - Measure process RSS while exporting the largest resource at production row counts before deciding
    whether streaming is warranted.

## imp-20260801-012 — Audit page runs `SELECT DISTINCT tabela` over the fastest-growing table on every render

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** performance, caching, full-scan, auditoria
- **Files affected:** `components/xtreme_system/auditoria/core.py`, `bases/xtreme_system/api/routes/ui_routes/auditoria.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/auditoria/core.py:173` — `tabelas` (shown with surrounding context)

```python
        data_de=data_de,
        data_ate=data_ate,
    )
    return int(session.scalar(stmt) or 0)


def tabelas(session: Session) -> list[str]:
    stmt = select(Auditoria.tabela).distinct().order_by(Auditoria.tabela)
    return list(session.scalars(stmt))


def get(session: Session, registro_id: int) -> Auditoria | None:
    return session.get(Auditoria, registro_id)
```

### Description

`_ctx_auditoria` (`bases/xtreme_system/api/routes/ui_routes/auditoria.py:88-116`) calls
`auditoria.tabelas(session)` on every audit page render to populate the "tabela" filter dropdown.
`Auditoria.tabela` carries a plain index (`components/xtreme_system/auditoria/core.py:33`), but the
distinct scan still traverses every entry for that column, and `auditoria` gains a row for every
create, update, and delete in the entire system — it grows faster than any business table.

The result set is tiny and near-static: it is the list of audited table names, which only changes when
a new model is added to the system.

### Why it matters

The most expensive scan on the page exists to fill a dropdown with roughly twenty fixed values, and
its cost grows with total system write volume forever. The same render also runs a filtered
`count(*)` (`components/xtreme_system/auditoria/core.py:152-170`) and `usuario.list_all`, so the page
already carries several table-wide reads.

### Concrete fix

Derive the dropdown from the registered model metadata instead of from the data, or memoize the
distinct query for the process lifetime — the staleness window only matters when a new audited model
is deployed, which coincides with a restart.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - The distinct query and its per-render call site were read directly.
  - The index on `tabela` was confirmed in both the model and migration `a1b2c3d4e007`.
- **Weaknesses:**
  - On PostgreSQL an index-only scan over a low-cardinality column can be cheap enough that this
    never shows up in a profile.
  - Audit table size in production is unknown.
- **Suggested checks:**
  - `EXPLAIN ANALYZE` the distinct query against a production-sized `auditoria` table.

## imp-20260801-013 — No query-count or timing regression guard on the paths most prone to N+1

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** performance, testing, n+1, observability, regression
- **Files affected:** `tests`
- **Related opportunities:** imp-20260801-001, imp-20260801-006

### Location

Not verified

### Description

A sweep of the test suite for query-count assertions, `before_cursor_execute` instrumentation, or any
N+1 guard (`rg -l "query_count|assert_num_queries|before_cursor_execute" tests/`) returns nothing.
Nothing in the suite fails when a listing starts issuing one query per row.

This matters more than usual here because the ORM configuration makes eager/lazy behavior easy to
change accidentally: `Venda`, `Compra`, `Veiculo` and `FechamentoVenda` all declare `lazy="selectin"`
relationships, and a single `lazyload` option — exactly what
`components/xtreme_system/fechamento_venda/core.py:316-320` does — silently converts a batched load
into a per-row one with no visible test failure. The same is true in reverse: fixing the DRE N+1
described in `imp-20260801-001` can be undone by any later `options(...)` change.

### Why it matters

Every N+1 in this report is invisible to CI. Without a counter assertion, these regressions surface as
a user complaint about a slow page months after the commit that caused them, and bisecting them is
expensive because the change that caused it was semantically correct.

### Concrete fix

Add a pytest fixture that counts statements via a SQLAlchemy `before_cursor_execute` event listener,
and assert an upper bound in the tests that already exercise the DRE report, the vehicle list, and the
purchase list — one assertion per path, pinned generously so it only fires on order-of-magnitude
changes.

### Example

```python
@pytest.fixture
def query_counter(engine):
    counts = []
    def _count(conn, cursor, statement, params, context, executemany):
        counts.append(statement)
    event.listen(engine, "before_cursor_execute", _count)
    yield counts
    event.remove(engine, "before_cursor_execute", _count)
```

### Self-critique

- **Confidence:** 7/10
- **Uncertain:** Yes
- **Strengths:**
  - The absence of any query-count instrumentation in `tests/` was confirmed by search.
  - The concrete regression risk is grounded in a specific `lazyload` call verified in this review.
- **Weaknesses:**
  - No location can be cited because the finding is the absence of code; existing test files covering
    the DRE and list routes were not enumerated, so the effort estimate is rough.
  - Query-count assertions are themselves a maintenance cost and can become flaky if pinned too
    tightly.
- **Suggested checks:**
  - Identify which existing tests already render the DRE and vehicle list routes, and attach the
    counter there rather than writing new tests.

## Discarded candidates

### WhatsApp sale notification performs an outbound HTTP call

`components/xtreme_system/whatsapp/core.py:147-181` already defers the send: the message is formatted
in the request thread, but the HTTP call is registered as a post-commit callback and dispatched to a
thread pool executor, with a 10-second timeout. This is the correct pattern, not a finding.

### Missing index on `auditoria.criado_em`

The model does not declare `index=True`, but migration
`alembic/versions/60358370bf3c_fix_compra_status_enum_fechamento_venda_.py:46` creates
`ix_auditoria_criado_em` as a descending index, which matches the
`ORDER BY criado_em DESC, id DESC` used by `auditoria.query`. The model/migration divergence is a
schema-hygiene concern, not a performance one.

### `compra.latest_debitos_by_veiculo_ids` per-vehicle debits lookup

Already implemented as a single window-function query partitioned by `veiculo_id`
(`components/xtreme_system/compra/core.py:151-173`) rather than a loop. The problem with its callers is
the unbounded id list they pass in, which is covered by `imp-20260801-003` and `imp-20260801-004`.

### `_investidor_padrao_id` linear scan

`bases/xtreme_system/api/routes/ui_routes/compras.py:90-94` scans the investor list in Python, but
`investidor` is a small configuration-scale table. Micro-optimization with no measurable effect.

### Caixa investor aggregates

`components/xtreme_system/caixa/core.py:260-277` and `venda.resumo_estoque` /
`venda.funil_status` / `venda.ranking_vendedores` are all single grouped aggregate queries returning
dicts keyed by id — the batched pattern this review would otherwise recommend.

### Deep-offset pagination on the audit listing

`auditoria.query` uses `LIMIT/OFFSET`, which degrades at large offsets. The UI does not expose deep
paging and the descending `criado_em` index covers the common case, so the realistic impact is low.
