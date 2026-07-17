# Codebase Analysis — Top 10 Improvement Opportunities

Scope: FastAPI + HTMX + Polylith monorepo (`components/xtreme_system/*`, `bases/xtreme_system/api/*`).
Ordering: highest to lowest impact. Findings prioritize correctness, reliability, and
operational risk over style.

---

## 1. `venda.search` and `compra.search` build a cartesian product (implicit cross join)

Location: components/xtreme_system/venda/core.py:207 and components/xtreme_system/compra/core.py:126
Impact: High
Category: Performance
Estimated effort: Low

Description:
Both search functions query one entity but filter on columns of other tables without
ever joining them:

```python
# venda/core.py
session.query(Venda).where(
    or_(
        Cliente.nome.ilike(pattern),      # Cliente is never joined
        Veiculo.modelo.ilike(pattern),    # Veiculo is never joined
        Veiculo.placa.ilike(pattern),
        Venda.status.ilike(pattern),
        Venda.observacoes.ilike(pattern),
    )
).all()
```

Because `Cliente` and `Veiculo` are referenced in the `WHERE` clause but not joined,
SQLAlchemy adds them to the `FROM` list as independent tables, producing
`Venda × Cliente × Veiculo`. The `lazy="joined"` relationships do not help — those eager
loads use anonymous aliases, not the base tables named in the filter.

Why it matters:
The search returns the wrong rows: a `venda` matches whenever *any* cliente or *any*
veiculo in the whole database matches the term, and each real match is duplicated by the
cross-product cardinality. Result size grows as `rows(Venda) × rows(Cliente) × rows(Veiculo)`,
so the query degrades badly as data grows. This is a correctness defect users will hit on
every non-empty search term.

Concrete fix suggestion:
Join the referenced tables explicitly (and keep results distinct):

```python
session.query(Venda)
    .join(Cliente, Venda.cliente_id == Cliente.id)
    .join(Veiculo, Venda.veiculo_id == Veiculo.id)
    .where(or_(Cliente.nome.ilike(pattern), Veiculo.modelo.ilike(pattern), ...))
    .distinct()
    .all()
```

Apply the same fix to `compra.search`.

---

## 2. Profit distribution leaves an unallocated rounding residual

Location: components/xtreme_system/fechamento_venda/core.py:229
Impact: High
Category: Code quality
Estimated effort: Low

Description:
Each investor's share is quantized independently:

```python
for item in data.participacoes:
    valor = _quantizar(lucro * item.percentual / PERCENTUAL_TOTAL)
    ...
    caixa.criar_lancamento_fechamento(..., tipo=distribuicao_lucro, valor=valor, ...)
```

The sum of the per-investor `valor` need not equal `lucro_liquido`. Example: `lucro = 1.00`
split `33.33 / 33.33 / 33.34` yields `0.33 + 0.33 + 0.33 = 0.99`, leaving `0.01`
undistributed. The full `receita` is credited to the owning investor as one lançamento,
but the `distribuicao_lucro` lançamentos silently fail to reconcile against `lucro_liquido`.

Why it matters:
This is a financial-integrity defect. Investor balances (`caixa.saldo`) drift by cents on
every closing where the split does not divide evenly, and the drift is invisible because no
invariant checks that distributions sum to the stored `lucro_liquido`.

Concrete fix suggestion:
Allocate the residual deterministically (e.g. give the last participant `lucro − sum(others)`),
and assert the total:

```python
valores = [_quantizar(lucro * p.percentual / PERCENTUAL_TOTAL) for p in participacoes]
valores[-1] += lucro - sum(valores)   # absorb the rounding remainder
assert sum(valores) == lucro
```

---

## 3. In-memory rate limiter keyed by `request.client.host` is proxy- and worker-blind

Location: bases/xtreme_system/api/setup.py:90 (`_RateLimiter`), setup.py:143
Impact: Medium
Category: Error handling and logging
Estimated effort: Medium

Description:
The limiter stores a sliding window in a per-process dict keyed by `request.client.host`
and never consults `X-Forwarded-For`:

```python
client_ip = request.client.host if request.client else "desconhecido"
```

Behind a reverse proxy or load balancer (Docker/compose is present), `client.host` is the
proxy's IP, so *every* client shares a single bucket. State also lives only in one process,
so it is not shared across uvicorn workers or replicas.

Why it matters:
The login brute-force protection (`_LOGIN_LIMIT = 5`) becomes either useless (attacker's IP
hidden behind the proxy along with everyone else) or a denial-of-service against all users
(one shared bucket throttles the whole site after 5 login attempts). With multiple workers,
the effective limit is `limit × worker_count` and non-deterministic. This is a security and
availability control that does not behave as intended in production.

Concrete fix suggestion:
Derive the client IP from a trusted `X-Forwarded-For` (configure `ProxyHeadersMiddleware` /
`--forwarded-allow-ips`), and move shared limiter state to an out-of-process store (Redis) if
more than one worker/replica is deployed. If a single worker is guaranteed, at minimum honor
the forwarded header and document the single-worker assumption.

---

## 4. File writes are not transactional — orphaned files on commit failure

Location: bases/xtreme_system/api/routes/ui_routes/uploads.py:34 (`salvar_arquivos`) and
bases/xtreme_system/api/routes/ui_routes/vendas.py:221 (`_persistir_contrato_venda`)
Impact: Medium
Category: Maintainability
Estimated effort: Medium

Description:
Files are written to disk during the request, then the DB row is created; the cleanup only
covers the case where the *create call* raises:

```python
with path.open("wb") as f:
    f.write(arquivo.file.read())
try:
    create_fn(session, schema.model_validate({...}))
except Exception:
    _remover_upload(path)
    raise
```

But the actual commit happens later, in `get_session()` (database/core.py:60). If that commit
fails (or any later step in the request raises after the file is written and the row flushed),
`get_session` rolls back the DB row while the file stays on disk. `register_post_commit`
callbacks only run after a successful commit, and `after_rollback` merely discards them — there
is no rollback hook that deletes the just-written file.

Why it matters:
Disk accumulates orphaned upload/contract files with no DB reference. `remover_orfaos` handles
only the inverse (DB row whose file vanished), so these orphans are never reclaimed. Over time
this is a storage leak and an audit/consistency gap.

Concrete fix suggestion:
Register a compensating cleanup on rollback for files written during the request, mirroring
`register_post_commit`. For example track written paths in `session.info` and delete them in an
`after_rollback` listener, or move file persistence to a post-commit step that writes only once
the transaction is durable.

---

## 5. Audit trail depends on `session.info["usuario_id"]` set at runtime in 16 route files

Location: components/xtreme_system/auditoria/core.py:72 (`auditar`), set in
bases/xtreme_system/api/crud_ui/routes.py:343 and 15 other route modules
Impact: Medium
Category: Architecture and design
Estimated effort: Medium

Description:
Every audited write reads the acting user from mutable session state:

```python
usuario_id = session.info.get("usuario_id")
if usuario_id is None:
    raise AuditError
```

The contract "set `session.info['usuario_id']` before any create/update/delete" is enforced
only at runtime and is duplicated across at least 16 route files (`rg session.info['usuario_id']`).
Any new write path that forgets it fails with `AuditError` → HTTP 500. Separately, the audit
of `lancamento_investimento` deletion relies on the `before_delete=caixa.deletar_lancamento_veiculo`
hook (veiculos.py:82) to delete via the ORM *before* the DB FK `ondelete="CASCADE"` fires
(caixa/core.py:36). Any deletion of a `veiculo` that does not go through that hook lets the
database cascade remove lançamentos with no audit row.

Why it matters:
The audit invariant is invisible to the type system and easy to break silently — either as a
500 for the user, or as a silent gap in the audit trail (a compliance-relevant surface). The
coupling is implicit and spread across the whole route layer.

Concrete fix suggestion:
Thread the acting user explicitly (e.g. a small write-context object passed into the CRUD
layer, or a single dependency/middleware that binds `usuario_id` for all authenticated write
routes) so the requirement is satisfied in one place. For cascade deletes, prefer explicit ORM
deletion or database-level audit triggers rather than relying on every caller to invoke the
`before_delete` hook.

---

## 6. `whatsapp.get_config` performs a write during read paths and can race on lazy creation

Location: components/xtreme_system/whatsapp/core.py:49 (`get_config`)
Impact: Medium
Category: Architecture and design
Estimated effort: Low

Description:
`get_config` lazily inserts the singleton row when missing:

```python
def get_config(session):
    config = session.get(WhatsappConfig, _CONFIG_ID)
    if config is None:
        config = WhatsappConfig(id=_CONFIG_ID)
        session.add(config)
        crud.flush(session)
        session.refresh(config)
    return config
```

It is called from `notificar_venda` (a side effect of creating a venda) and from the settings
read path. Because `get_session` commits at the end of every request, a plain read that touches
this function will INSERT and commit a row. Two concurrent first-time requests can both see
`None` and both attempt to insert `id=1`, causing an `IntegrityError` on one of them.

Why it matters:
Reads with write side effects are surprising and make the endpoint non-idempotent; the race
turns the very first concurrent access into a 500. It also means a GET can fail the whole
request transaction under load.

Concrete fix suggestion:
Seed the singleton row via a migration (the config table already has a fixed `_CONFIG_ID = 1`),
and have `get_config` return the row read-only (raise or return defaults if absent). If lazy
creation must stay, use an upsert / `ON CONFLICT DO NOTHING` and re-fetch.

---

## 7. `_schema_disponivel` caches availability per-engine for the process lifetime

Location: components/xtreme_system/fechamento_venda/core.py:131
Impact: Medium
Category: Maintainability
Estimated effort: Low

Description:
Schema availability is cached in a module-level `WeakKeyDictionary` keyed by engine:

```python
try:
    return _SCHEMA_DISPONIVEL_POR_ENGINE[engine]
except KeyError:
    pass
...
_SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel
```

Once computed `False` (tables absent), the value is cached until the process restarts. If the
app is running before `make migrate` and the migration is applied while it is up, the fechamento
feature stays disabled (`list_all` returns `[]`, `confirmar` raises `ERRO_SCHEMA_DESATUALIZADO`)
until a restart. It also introduces global mutable state that leaks between tests that build
their own engines/sessions unless carefully isolated.

Why it matters:
"Feature silently stays off after the migration that enables it" is an operationally confusing
failure mode, and the permanent negative cache is a maintenance trap. The whole mechanism exists
to tolerate a not-yet-migrated DB, which is itself a smell.

Concrete fix suggestion:
Either drop the runtime schema probe entirely and treat migrations as a hard precondition
(simplest), or only cache the positive result and re-probe when it is `False`.

---

## 8. Cross-module reliance on private symbols weakens Polylith component boundaries

Location: components/xtreme_system/crud/core.py:7, caixa/core.py:12,
fechamento_venda/core.py:12 (all import `_snapshot`, `auditar` from `auditoria.core`)
Impact: Low
Category: Architecture and design
Estimated effort: Medium

Description:
`_snapshot` is an underscore-prefixed (private) function, yet it is imported and called across
component boundaries (`crud`, `caixa`, `fechamento_venda`). Similarly, route modules import
`_found`, `_NaoAutenticadoError`, etc. across base boundaries. The leading underscore signals
"internal", but these are de-facto public contracts used repo-wide.

Why it matters:
Changing `_snapshot`'s signature or behavior silently affects audit output for every component.
The privacy marker is misleading and undermines the modular boundaries Polylith is meant to
provide, making safe local edits harder to reason about.

Concrete fix suggestion:
Promote the genuinely shared helpers to public names (`snapshot`, and an explicit `__all__` in
`auditoria.core`), and keep truly private helpers underscored and unimported. This is a rename,
not a redesign — do it in one pass to avoid churn.

---

## 9. Near-duplicated create/update route registration blocks in `crud_ui/routes.py`

Location: bases/xtreme_system/api/crud_ui/routes.py:339 (`register_create_route`) and
routes.py:423 (`register_update_route`)
Impact: Low
Category: Code quality
Estimated effort: Medium

Description:
`register_create_route` and `register_update_route` share ~60 lines of nearly identical
control flow: same `ValidationError`/`HTTPException` → `error_response`, same `IntegrityError`
→ `session.rollback()` + `conflict_form_response`, same `query_list` + `ok_response` tail. The
only differences are the presence of `item_id`/`obj` and which hook runs.

Why it matters:
The error-handling policy (which exceptions map to which response, when to roll back) is
duplicated, so the two paths can drift — e.g. a fix to conflict handling applied to one and not
the other. This is exactly the kind of divergence that produces inconsistent API behavior over
time.

Concrete fix suggestion:
Extract the shared validate → write → respond pipeline into one helper parameterized by the
write callable and the `item` context, so create and update differ only in what they pass in.
Keep the change surgical — one internal helper, no behavior change — and cover it with the
existing `test_route_factories_*` tests.

---

## 10. No test asserts search *excludes* non-matching rows

Location: tests/ (no coverage for `venda.search` / `compra.search` filtering correctness)
Impact: Low
Category: Testing
Estimated effort: Low

Description:
There is broad CRUD/API test coverage, but nothing exercises that a search term returns
*only* matching rows. This is why the cartesian-product defect in Finding #1 went unnoticed:
a test that inserts one matching and one non-matching venda and asserts a single result would
fail today.

Why it matters:
Search correctness is user-facing and currently wrong (Finding #1). Without a negative-case
test, the fix can regress silently, and similar join bugs in future search functions will not
be caught.

Concrete fix suggestion:
Add a focused test per searchable entity: seed two rows (one matching, one not), assert the
result contains exactly the matching row and no duplicates. Add it before fixing Finding #1 so
it reproduces the bug first, then passes.

Example:

```python
def test_venda_search_excludes_non_matching(session):
    match = make_venda(session, cliente_nome="Alice")
    make_venda(session, cliente_nome="Bob")
    result = venda.search(session, "Alice")
    assert [v.id for v in result] == [match.id]
```
