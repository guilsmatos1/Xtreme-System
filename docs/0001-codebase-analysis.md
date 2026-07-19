# Codebase Analysis — Top 10 Improvement Opportunities

Scope: FastAPI + HTMX + Polylith application (`bases/xtreme_system`, `components/xtreme_system`).
Ordered from highest to lowest impact. Findings prioritize correctness, reliability, and
operational risk over style.

---

## 1. First-admin bootstrap script is broken (raises AuditError and never commits)

Location: development/create_admin.py:14-23
Impact: High
Category: Error handling and logging
Estimated effort: Low

Description:
`main()` opens `with SessionLocal() as session:` and calls `usuario.create(session, ...)`.
`usuario.create` (usuario/core.py:79) unconditionally calls `auditar(...)`, which reads
`session.info.get("usuario_id")` and raises `AuditError` when it is `None`
(auditoria/core.py:72-74). The script never sets `session.info["usuario_id"]`, so the very
first admin creation crashes. Even if auditing were skipped, the SQLAlchemy `Session` context
manager does not commit on exit — it closes (rolling back) — so nothing would be persisted.

Why it matters:
This is the documented onboarding path (README bootstrap). A new deployment cannot create its
first user without patching the script, and the failure mode (`AuditError`) is opaque.

Concrete fix suggestion:
Set the audit actor to the row being created (self-reference) or introduce a system actor, and
commit explicitly.

Example:
```python
with SessionLocal() as session:
    if usuario.get_by_username(session, username) is not None:
        sys.exit(f"usuário '{username}' já existe")
    session.info["usuario_id"] = None  # or a dedicated SYSTEM actor id
    user = usuario.create(session, usuario.UsuarioCreate(...))
    session.commit()
    print(f"admin criado: id={user.id} username={user.username}")
```
Note: this only works after fixing item 2 (making `auditar` tolerate a system/bootstrap actor);
otherwise seed the actor row first.

---

## 2. Audit actor is an implicit session global that 500s any write path that forgets it

Location: components/xtreme_system/auditoria/core.py:60-74; components/xtreme_system/crud/core.py:22-68
Impact: High
Category: Maintainability
Estimated effort: Medium

Description:
Every write funnels through `crud.create/update/delete`, which always calls `auditar`, which
requires `session.info["usuario_id"]` to be set out-of-band by the caller. Nothing in the type
system or function signature enforces this; each route must remember
`session.info["usuario_id"] = user.id`. When a path forgets (a new endpoint, a script, a
background job — see item 1), the write raises `AuditError` (a `ValueError`) that surfaces as a
generic 500 via the catch-all handler in setup.py:193.

Why it matters:
This is a hidden global coupling between the HTTP layer and the persistence layer. It makes new
write endpoints error-prone and turns a missing assignment into a runtime 500 discovered only
when that path executes, not at review or type-check time.

Concrete fix suggestion:
Make the actor an explicit parameter threaded through the CRUD helpers (or a small
`AuditContext` passed in), so the contract is visible and enforced by the signature. At minimum,
allow a well-known system actor for non-request writes so scripts/jobs are not forced to fake a
user id.

Example:
```python
def create[M](session, model_cls, data, *, actor_id: int | None) -> M:
    ...
    auditar(session, tabela=..., actor_id=actor_id, ...)
```

---

## 3. Sale-contract PDF is written best-effort after commit while its DB row commits in-transaction

Location: bases/xtreme_system/api/routes/ui_routes/vendas.py:275-297; components/xtreme_system/database/core.py:47-53
Impact: High
Category: Error handling and logging
Estimated effort: Medium

Description:
`_persistir_contrato_venda` creates a `DocumentoContratoVenda` row (committed with the
transaction) pointing at `/static/uploads/vendas/{id}/contrato/{file}.pdf`, but the actual file
write is deferred to a post-commit callback. `_invoke_post_commit` runs callbacks inside
`try/except Exception` and only logs a warning on failure. If `mkdir`/`write_bytes` fails (disk
full, permissions, path race), the DB says the contract exists but the file never lands, and the
error is swallowed.

Why it matters:
Downstream, `_baixar_contrato_venda` (vendas.py:343) redirects to the stored URL; a missing file
yields a silent 404 for a record the system reports as present. This is a durable data/file
inconsistency with no reconciliation path and no surfaced error.

Concrete fix suggestion:
Write the file to a temp path and fsync/rename before commit so the row and file commit together
(or fail together), or record a "pending" state and reconcile. If the file write must stay
post-commit, at least escalate failures (structured error + a repair job) rather than a warning.

---

## 4. Rate limiter keys on request.client.host and lives in-process — breaks behind a proxy and across workers

Location: bases/xtreme_system/api/setup.py:90-160
Impact: High
Category: Architecture and design
Estimated effort: Medium

Description:
`_RateLimiter` is an in-memory sliding window keyed by `request.client.host`
(setup.py:143). The project ships a Docker/CasaOS/GHCR deployment, which typically places the app
behind a reverse proxy. Behind a proxy, `request.client.host` is the proxy's IP for every
request, so the login limiter (5/60s) becomes a global lockout: five bad logins from anyone lock
out all users. Conversely, with more than one uvicorn worker, each process keeps its own window,
so the effective limit is N× and inconsistent.

Why it matters:
Both a security control (login throttling) and an availability control (general 100/60s) silently
misbehave in the intended deployment topology — either locking out legitimate users or failing to
throttle attackers.

Concrete fix suggestion:
Derive the client IP from a trusted `X-Forwarded-For` (configured proxy hops) instead of
`client.host`, and move the counter to a shared store (e.g. Redis) if more than one worker/replica
is ever used. If single-worker is guaranteed, document and enforce that assumption.

---

## 5. `/auditoria` accepts unbounded `limit` and `offset`

Location: bases/xtreme_system/api/routes/json.py:339-360
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
`listar_auditoria` exposes `limit: int = 50` and `offset: int = 0` with no upper bound. A client
can request `/auditoria?limit=100000000`, and `auditoria.query` will `limit(...).offset(...)` and
materialize the full result set into a list (auditoria/core.py:143-144). The audit table grows
unbounded over time (one row per write), so this scales with total history.

Why it matters:
An authenticated admin (or a scripted client) can trigger large memory allocation and a slow query
per call — an availability/DoS risk that worsens as the audit log grows.

Concrete fix suggestion:
Cap and validate the pagination parameters at the API boundary.

Example:
```python
limit: int = Query(50, ge=1, le=200),
offset: int = Query(0, ge=0),
```

---

## 6. `_sincronizar_status_veiculo` unconditionally overwrites vehicle status, clobbering `reservado`

Location: components/xtreme_system/venda/core.py:154-188
Impact: Medium
Category: Code quality
Estimated effort: Medium

Description:
On every venda create/update, the vehicle status is recomputed purely from the venda status:
non-`concluido` maps to `disponivel` unless another concluded sale exists (venda/core.py:136-139,
175-180). A `StatusVeiculo.reservado` (a valid enum value, veiculo/core.py:26) is never produced
and is silently overwritten to `disponivel`. Creating or editing a `pendente` sale also forces the
vehicle back to `disponivel`, even though a sale is in progress.

Why it matters:
Any manual/reserved state on a vehicle is lost the next time any sale touching it is saved, and a
pending sale leaves the vehicle advertised as available — a correctness/business-logic gap that is
easy to hit and hard to notice.

Concrete fix suggestion:
Only transition the vehicle when the venda status actually changes to/from `concluido`, and treat
`reservado` as a state the sync must not stomp. Make the mapping explicit about the `pendente`
case rather than defaulting it to `disponivel`.

---

## 7. Venda creation and validation are duplicated across the JSON factory and the custom UI handler

Location: bases/xtreme_system/api/routes/json.py:239-262; bases/xtreme_system/api/routes/ui_routes/vendas.py:127-148, 300-340
Impact: Medium
Category: Architecture and design
Estimated effort: Medium

Description:
The JSON API registers venda via `register_crud_routes` with `before_create=_validate_venda_create`
(which runs both FK validation and `validate_veiculo_disponivel_para_venda`). The UI opts out
(`register_create=False`) and reimplements creation in `_criar_venda`, repeating FK validation,
availability checks, whatsapp notification, and contract persistence by hand. Additionally, the UI
registration still passes `after_create=whatsapp.notificar_venda` even though the create route is
disabled, so that hook is dead configuration.

Why it matters:
The same business rules (which FKs to check, when a vehicle counts as available, when to notify)
must be maintained in two places and can drift — the JSON `before_create` bundles the availability
check while the UI performs it inline, so a change to one path can silently diverge from the other.

Concrete fix suggestion:
Extract a single `create_venda(session, data, user)` workflow used by both routers, or make the UI
route reuse the same `before_create`/`after_create` hooks instead of re-inlining them. Remove the
dead `after_create` argument from the vendas UI registration.

---

## 8. `_schema_disponivel` caches table existence per engine forever and feature-gates on it

Location: components/xtreme_system/fechamento_venda/core.py:31, 131-165
Impact: Medium
Category: Maintainability
Estimated effort: Medium

Description:
Fechamento reads/writes are gated by `_schema_disponivel`, which inspects whether the
`fechamento_venda` tables exist and caches the result per engine in a module-level
`WeakKeyDictionary` for the process lifetime. If the tables are created by a migration while the
process is running, the cached `False` persists and fechamento stays disabled until restart. More
broadly, gating a feature on runtime table-existence (rather than assuming migrations ran) is a
workaround that hides migration-ordering debt and scatters `if not _schema_disponivel(...)` guards
through the module (list_all/get/get_by_venda/confirmar).

Why it matters:
It couples domain logic to schema-introspection state, produces a confusing "silently returns
[]/None" behavior when the cache is stale, and normalizes running the app against a schema the
code does not fully expect.

Concrete fix suggestion:
Treat the migration as a hard precondition: remove the runtime table-existence gating and let the
app require an up-to-date schema (fail fast at startup if a required table is missing). If a
transitional guard is truly needed, do not cache it for the process lifetime.

---

## 9. Transaction/rollback handling is fragmented across four layers with three different patterns

Location: bases/xtreme_system/api/crud_writes.py:19-23; bases/xtreme_system/api/crud_ui/routes.py:426-450, 538-551, 601-606; bases/xtreme_system/api/routes/json.py:323-333; components/xtreme_system/database/core.py:56-66
Impact: Medium
Category: Maintainability
Estimated effort: Medium

Description:
There are three coexisting conventions for handling write failures: (a) `safe_write` catches
`IntegrityError` and re-raises `HTTPException`, relying on `get_session` to roll back; (b) HTMX
handlers catch `IntegrityError`, call `session.rollback()` themselves, and return a rendered
response; (c) some handlers let errors propagate. The project's own CLAUDE.md documents this as a
footgun ("if a handler catches internally and returns a response, it must call
`session.rollback()`"), which is a signal the invariant is enforced by discipline, not structure.

Why it matters:
Whether `rollback` is required depends on whether the handler raises or returns — a subtle rule
that is easy to violate when adding a new HTMX endpoint, leaving the session in a failed state that
`get_session` then tries to commit.

Concrete fix suggestion:
Centralize the "catch IntegrityError → rollback → build conflict response" flow into one helper
used by all HTMX write routes, so no route open-codes the rollback decision. Keep `get_session` as
the single rollback authority for the raise path.

---

## 10. Dashboard issues many independent full-table aggregate queries per request, uncached

Location: bases/xtreme_system/api/routes/ui_routes/dashboard.py:28-78; components/xtreme_system/venda/core.py:233-374
Impact: Low
Category: Performance
Estimated effort: Medium

Description:
`_ctx_dashboard` runs `resumo_estoque`, `resumo_mes`, `receita_por_tipo`, `funil_status`,
`ticket_medio`, `ranking_vendedores`, and `tendencia_por_periodo` — each a separate aggregate scan
over `venda`/`veiculo` — on every dashboard load, with no caching. `tendencia_por_periodo` for
30d/90d additionally pulls per-day grouped rows and re-buckets them into ISO weeks in Python.

Why it matters:
At a single dealership's data volume this is currently fine, but it is the heaviest read path and
scales linearly with sales history; there is no memoization or short-TTL cache, so repeated
refreshes repeatedly rescan the tables.

Concrete fix suggestion:
This is a scale-ahead concern, not a present defect — flagged as low priority. If dashboard latency
becomes an issue, add a short-TTL cache keyed by `periodo` (invalidated on venda writes) or combine
the independent aggregates where they share the same base filter.
