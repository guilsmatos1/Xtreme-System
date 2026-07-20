# Codebase Analysis — Top 10 Improvement Opportunities

Scope: FastAPI + HTMX + Polylith application (`bases/xtreme_system`, `components/xtreme_system`).
Ordered from highest to lowest impact. Findings prioritize correctness, reliability, and
operational risk over style.

---

## 1. Login rate limiter keys on the raw socket IP — behind a proxy it locks out every user

Location: bases/xtreme_system/api/routes/json.py:62; bases/xtreme_system/api/routes/ui_routes/auth.py:32

Impact: High

Category: Architecture and design

Estimated effort: Low

Description:
Both login handlers derive the throttling bucket with
`client_ip = request.client.host if request.client else "desconhecido"` and pass it to
`allow_login_attempt(session, client_ip, 5, 60)`. The general-purpose limiter in the middleware
uses a *different* helper, `_client_ip` (setup.py:153-159), which honors `X-Forwarded-For`. The
project ships a Docker/CasaOS/GHCR deployment and `make run` starts uvicorn with
`--proxy-headers`, so the intended topology is behind a reverse proxy. In that topology
`request.client.host` is the proxy's address for *every* request, and the 5-attempt window
becomes global: five bad passwords from anyone lock out the entire dealership for 60 seconds.

A second defect compounds it: `allow_login_attempt` is called before credentials are checked and
is never reset on success, so successful logins consume the same 5/minute budget. Even without a
proxy, a shared office NAT hits the limit during normal morning sign-in.

Why it matters:
A security control silently converts into a self-inflicted denial of service on the one endpoint
that has no alternative path — nobody can get into the system, including admins.

Concrete fix suggestion:
Use the same client-identity helper the middleware uses, and scope the login bucket by username
in addition to IP so one account's failures cannot lock the tenant. Clear the counter on a
successful authentication.

Example:
```python
from xtreme_system.api.setup import _client_ip

client_ip = _client_ip(request)
bucket = f"{client_ip}|{form.username.lower()}"
retry_after = allow_login_attempt(session, bucket, _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS)
...
# after a successful verify_password:
reset_login_attempts(session, bucket)
```

Tradeoff worth naming: honoring `X-Forwarded-For` unconditionally (which `_client_ip` already
does) is itself spoofable when the app is reachable directly. The correct end state is a single
helper that trusts the header only from a configured set of proxy hops, used by both limiters.

---

## 2. Two independent rate-limiting subsystems, one of which is unreachable dead code

Location: bases/xtreme_system/api/setup.py:40-47 and 162-190; components/xtreme_system/auth/rate_limit.py:36

Impact: High

Category: Maintainability

Estimated effort: Medium

Description:
`_rate_limit` exempts a fixed path set before doing anything else:

```python
_ROTAS_ISENTAS_RATE_LIMIT = {"/health", "/docs", "/redoc", "/openapi.json", "/login", "/ui/login"}
...
if path.startswith("/static/") or path in _ROTAS_ISENTAS_RATE_LIMIT:
    return await call_next(request)

if request.method == "POST" and path.endswith("/login"):   # unreachable
    allowed, retry_after = store.allow(f"login:{client_ip}", _LOGIN_LIMIT, ...)
```

Because `/login` and `/ui/login` are in the exemption set, the login branch below can never
execute. Login throttling actually happens inside the route handlers via
`auth/rate_limit.allow_login_attempt`, backed by a *second* table (`login_attempt_rate_limit`)
with a *different* algorithm (fixed window with a counter) than the middleware store
(`rate_limit_state`, sliding window of timestamps in JSON). `ARCHITECTURE.md` documents only the
middleware version, describing behavior the code does not have.

Why it matters:
Two tables, two algorithms, and one dead branch for a single concern. A future change to
"the rate limiter" has a better-than-even chance of landing in the half that never runs, and the
architecture doc actively misleads anyone auditing the control. The `login:` bucket prefix in the
dead branch also means the two systems would not even share state if it were reactivated.

Concrete fix suggestion:
Pick one. The simplest surgical change: delete the dead branch and the `/login` entries from
`_ROTAS_ISENTAS_RATE_LIMIT` are *not* the fix — removing the exemption would double-throttle.
Instead, delete lines 171-181 and the `_LOGIN_LIMIT` import cycle from `setup.py`, keep
`allow_login_attempt` as the single login limiter, and correct the middleware section of
`ARCHITECTURE.md` to say login throttling lives in the handlers. If consolidation is preferred,
drop `login_attempt_rate_limit` and route login through `RateLimiterStore.allow` — but then item 1
must be fixed at the same time, since the two paths disagree on client identity.

---

## 3. `remover_orfaos` deletes document rows whenever the file is missing from disk

Location: bases/xtreme_system/api/routes/ui_routes/uploads.py:77-93; called at compras.py:128, clientes.py:121, veiculos_imagens.py:43, veiculos_procuracao.py:43, veiculos_cliente_vendedor.py:46

Impact: High

Category: Error handling and logging

Estimated effort: Medium

Description:
Every time a user merely *opens* an attachments modal, the handler runs:

```python
for doc in list(docs):
    path = _uploaded_file_path(doc.url or "")
    if path is not None and str(path) in pending_paths:
        continue
    if path is not None and not path.exists():
        delete_fn(session, doc)
```

The premise is that a missing file means a stale row. But `path.exists()` returning `False` has
several causes that are not "the row is stale": the uploads volume was not mounted, the container
was rebuilt without the bind mount, the app runs on a different replica than the one that wrote
the file, or the post-commit write in `salvar_arquivos` failed and only logged a warning
(`database/core.py:144-150`). In any of those cases, a read-only user action silently issues
audited `DELETE`s for every attachment record on the page, and `get_session` commits them.

Why it matters:
This is unrecoverable data loss triggered by an infrastructure hiccup, performed by a GET-shaped
interaction, with no confirmation and no way to distinguish "file genuinely gone" from "storage
temporarily unavailable". The blast radius is every document of every entity a user browses while
the volume is detached.

Concrete fix suggestion:
Do not mutate on read. Render missing files as unavailable and leave the row alone; move
reconciliation to an explicit, admin-triggered (or scheduled) cleanup that also verifies the
uploads root is present before deleting anything.

Example:
```python
def marcar_orfaos(session, docs):
    """Flags docs whose file is missing — does not delete."""
    uploads_root = (_ui_dir / "static" / "uploads")
    if not uploads_root.is_dir():
        return {}          # storage unavailable: assume nothing is orphaned
    return {doc.id: not _existe(doc) for doc in docs}
```

---

## 4. Vehicle-availability validation on venda diverges between the JSON API and the HTMX UI

Location: bases/xtreme_system/api/routes/json.py:252-275 vs bases/xtreme_system/api/routes/ui_routes/vendas.py:146-148

Impact: High

Category: Code quality

Estimated effort: Low

Description:
The JSON registration validates both FKs and availability on create *and* update:

```python
def _validate_venda_update(session, obj, data):
    validate_cliente_veiculo_fks(session, data)
    if data.veiculo_id is not None and data.veiculo_id != obj.veiculo_id:
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)
```

The UI registration passes only `before_update=validate_cliente_veiculo_fks`. The create path is
consistent (the UI hand-rolls `_criar_venda` and calls
`validate_veiculo_disponivel_para_venda` at vendas.py:337), but on **update** the UI has no
availability check at all: editing a sale to point at a vehicle already marked `vendido` succeeds
through `/ui/vendas/{id}` and is rejected through `PATCH /vendas/{id}`.

Two related smells sit in the same registration: `after_create=whatsapp.notificar_venda`
(vendas.py:149) is dead configuration because `register_create=False` disables that route, and
`compras.py:203-241` carries a near-verbatim copy of `common.resolver_cliente` — the two have
already drifted apart in their error strings.

Why it matters:
The same business rule has two answers depending on which door the request came through. Whoever
adds the next rule has no signal that a second copy exists, so the divergence widens.

Concrete fix suggestion:
Pass the same hook to both registrations, and delete the dead `after_create`.

Example:
```python
# vendas.py
before_update=_validate_venda_update,   # imported from the shared workflows module
# remove: after_create=whatsapp.notificar_venda   (register_create=False)
```
Move `_validate_venda_create` / `_validate_venda_update` out of `routes/json.py` into
`routes/workflows.py`, which is already the designated home for cross-router rules, and delete
`compras._resolver_cliente` in favor of `common.resolver_cliente`.

---

## 5. Vehicle availability is a check-then-act with no lock and no constraint — two sales can win

Location: bases/xtreme_system/api/routes/workflows.py:45-50; components/xtreme_system/venda/core.py:154-183

Impact: Medium

Category: Architecture and design

Estimated effort: Medium

Description:
`validate_veiculo_disponivel_para_venda` reads `veiculo.status` and raises 409 if it is not
`disponivel`; the write that flips the status to `vendido` happens afterwards in
`_sincronizar_status_veiculo`. Nothing serializes the two steps: no `SELECT ... FOR UPDATE`, no
unique index preventing a second `venda` row with `status = concluido` for the same
`veiculo_id`. Two concurrent requests both read `disponivel`, both pass validation, and both
commit. The `venda` table has no constraint that would catch it, so the `IntegrityError`
handlers in the routes never fire.

Why it matters:
The same car can be sold twice, and the resulting state is not detectable after the fact —
`veiculo_tem_outra_venda_concluida` will simply see both. Downstream `fechamento_venda` will then
happily book receita twice against the same vehicle cost.

Concrete fix suggestion:
Lock the vehicle row inside the validation, so the second transaction blocks and then fails the
status check.

Example:
```python
def validate_veiculo_disponivel_para_venda(session: Session, veiculo_id: int) -> None:
    v = session.get(veiculo.Veiculo, veiculo_id, with_for_update=True)
    if v is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if v.status != veiculo.StatusVeiculo.disponivel:
        raise HTTPException(status_code=409, detail="veículo indisponível")
```
A partial unique index (`veiculo_id WHERE status = 'concluido'`) would be the belt-and-braces
version, but it needs a migration and a data audit first, so the row lock is the smaller useful
fix.

---

## 6. `_sincronizar_status_veiculo` recomputes vehicle status from scratch, erasing `reservado`

Location: components/xtreme_system/venda/core.py:136-139 and 154-183

Impact: Medium

Category: Code quality

Estimated effort: Medium

Description:
The mapping is binary:

```python
def _status_veiculo_para_venda(status: StatusVenda) -> StatusVeiculo:
    if status == StatusVenda.concluido:
        return StatusVeiculo.vendido
    return StatusVeiculo.disponivel
```

and `_sincronizar_status_veiculo` applies it unconditionally on every venda create and update.
`StatusVeiculo.reservado` is a declared enum value (veiculo/core.py:26), has its own badge styling
in `_macros.html:44`, and shipped in its own migration
(`d9babf49fd9b_add_vendedor_and_reservado.py`) — yet nothing in the codebase ever *sets* it, and
if it were set manually the next save of any sale touching that vehicle would overwrite it with
`disponivel`. Likewise a `pendente` sale forces the vehicle back to `disponivel`, so a car with a
deal in progress stays advertised as available.

Why it matters:
A modeled business state is unreachable and, worse, actively destroyed — the migration and the
template promise a feature the domain layer silently undoes. Anyone implementing "reserve a
vehicle" will hit this only after shipping.

Concrete fix suggestion:
Make the mapping total and treat `reservado` as a state the sync must not stomp.

Example:
```python
_STATUS_POR_VENDA = {
    StatusVenda.concluido: StatusVeiculo.vendido,
    StatusVenda.pendente:  StatusVeiculo.reservado,
    StatusVenda.aprovado:  StatusVeiculo.reservado,
    StatusVenda.cancelado: StatusVeiculo.disponivel,
}
```
If `pendente → reservado` is not the desired business rule, decide explicitly and encode it —
the current code decides by omission. Either way, remove `reservado` from the enum or start
producing it; leaving it dead is the worst of the three options.

---

## 7. Compras list page issues one query per row for its comprovantes (N+1)

Location: bases/xtreme_system/api/routes/ui_routes/compras.py:97-105

Impact: Medium

Category: Performance

Estimated effort: Low

Description:
```python
def _ctx_lista_compras(session, compras):
    return {
        "comprovantes_por_compra": {
            item.id: imagem_comprovante_compra.list_by_compra(session, item.id)
            for item in compras
        }
    }
```
`ctx_list` runs on every list render, every search, every create, every update, and every delete
(`crud_ui/routes.py:261, 465, 565, 619`). With N compras that is N+1 round trips. It compounds
with the fact that the list route has no pagination at all — `query_list` returns
`module.list_all(session)` (crud_ui/query.py:63) and `sorted_list` then sorts the entire table in
Python (query.py:33-42), so the row count is unbounded and the per-row query count tracks it.

Why it matters:
The cost is quadratic in user-visible latency terms: more compras means both a bigger list and
more queries per page load. It is the cheapest real performance win in the codebase.

Concrete fix suggestion:
Fetch all comprovantes for the visible ids in one query and group in Python.

Example:
```python
def _ctx_lista_compras(session, compras):
    ids = [c.id for c in compras]
    rows = imagem_comprovante_compra.list_by_compras(session, ids)  # one IN (...) query
    agrupado: dict[int, list] = {cid: [] for cid in ids}
    for row in rows:
        agrupado[row.compra_id].append(row)
    return {"comprovantes_por_compra": agrupado}
```
Pagination for the list routes is the larger follow-up; flagging it here rather than proposing it
as part of this fix, since it changes the HTMX templates too.

---

## 8. `/auditoria` accepts unbounded `limit` and `offset`

Location: bases/xtreme_system/api/routes/json.py:353-374

Impact: Medium

Category: Performance

Estimated effort: Low

Description:
`listar_auditoria` declares `limit: int = 50` and `offset: int = 0` as plain ints with no
validation. `auditoria.query` applies them directly (`auditoria/core.py:141-142`) and
materializes the result with `list(session.scalars(stmt))`. The `auditoria` table receives one row
per write across every entity in the system, so it is the fastest-growing table in the schema, and
`dados_antes`/`dados_depois` are full JSON snapshots. `GET /auditoria?limit=10000000` will attempt
to load and serialize all of it.

Why it matters:
An authenticated admin — or anything holding an admin token, including a misbehaving script — can
exhaust process memory with a single request. The exposure grows monotonically with the age of the
deployment.

Concrete fix suggestion:
Constrain at the boundary with `Query`.

Example:
```python
from fastapi import Query

limit: Annotated[int, Query(ge=1, le=200)] = 50,
offset: Annotated[int, Query(ge=0)] = 0,
```
Worth applying the same bound to the `/ui/auditoria` route, which shares the underlying
`auditoria.query`.

---

## 9. `_schema_disponivel` caches table existence per engine for the process lifetime

Location: components/xtreme_system/fechamento_venda/core.py:31 and 131-146

Impact: Medium

Category: Maintainability

Estimated effort: Medium

Description:
Every fechamento read and write is gated on a runtime `has_table` probe whose result is memoized
in a module-level `WeakKeyDictionary` keyed by engine, with no invalidation:

```python
_SCHEMA_DISPONIVEL_POR_ENGINE: WeakKeyDictionary[Engine, bool] = WeakKeyDictionary()
```

If the app starts before `alembic upgrade head` runs — the normal order in a container that boots
alongside its database — the first request caches `False`, and `list_all` returns `[]`, `get`
returns `None`, and `confirmar` raises "Atualize o banco com `make migrate`" for the rest of the
process's life, even after the migration lands. The failure presents as an empty screen, not an
error.

Why it matters:
Domain logic is coupled to schema-introspection state, the guard is scattered across four
functions, and the sticky cache turns a transient ordering problem into a permanent one that only
a restart clears. It also normalizes running the app against a schema the code does not expect.

Concrete fix suggestion:
Treat migrations as a hard precondition and delete the gate — a missing table should be a loud
startup failure, not four silent `if` statements. If a transitional guard is genuinely required
during rollout, at minimum stop caching a negative result:

```python
if disponivel:                       # only memoize the terminal state
    _SCHEMA_DISPONIVEL_POR_ENGINE[engine] = True
return disponivel
```

---

## 10. The default test run never exercises Alembic, and the Polylith `test/` tree is never collected

Location: pyproject.toml:52-58; tests/database.py:56-70; Makefile (`test` target); test/components/xtreme_system/*/test_core.py

Impact: Medium

Category: Testing

Estimated effort: Medium

Description:
Two gaps in the harness:

1. `create_test_engine` builds the schema with `Base.metadata.create_all(engine)` on in-memory
   SQLite unless `TEST_DATABASE_URL` is set. Only `make test-postgres` runs
   `command.upgrade(cfg, "head")`. So the default `make test` and `make ci` (which calls
   `coverage`, also SQLite) validate the *models*, never the *migrations*. Any drift between an
   ORM change and its migration passes CI. The repo has already paid for this once —
   commit c9a6da6 is "reconcile audit actor contract gaps and diverging alembic heads". SQLite
   also does not enforce the native enum types, `ondelete` semantics, or `JSON`/`Numeric`
   behavior that production depends on.
2. `testpaths = ["tests"]` and `pytest tests/ -q -n auto` mean `test/components/…`, the
   Polylith-conventional component test tree, is never collected. Its five files are placeholders
   (`assert core is not None`), so nothing is currently lost — but the directory reads as covered
   component tests and is not.

Why it matters:
Migration correctness is the single riskiest thing in this codebase (13 tables, hand-written
enum `ALTER TYPE` statements, a merge-heads history) and it is the one thing the default test
command cannot catch. The dead `test/` tree gives a false impression of where component coverage
lives.

Concrete fix suggestion:
Make Postgres-with-migrations the CI path rather than an opt-in target, and delete or populate the
orphan tree.

Example:
```make
ci: lint test-postgres coverage
```
Plus a focused test that the migration chain and the models agree — run
`alembic upgrade head` then assert `compare_metadata(MigrationContext.configure(conn), Base.metadata)`
is empty. That single test would have caught the drift the recent fix commit had to repair.
Keep SQLite for the fast local loop; just stop letting it be the only thing CI sees.
