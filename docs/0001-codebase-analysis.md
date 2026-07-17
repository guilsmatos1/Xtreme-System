# Codebase Analysis — 10 Highest-Impact Opportunities

Prioritized by impact. Correctness, reliability, and operational risk are ranked above stylistic concerns. Every item is tied to a specific file, function, and line.

---

## 1. `_criar_compra` skips rollback after a duplicate-veículo IntegrityError, crashing with a 500

Location: bases/xtreme_system/api/routes/ui_routes/compras.py:334-340
Impact: High
Category: Error handling and logging
Estimated effort: Low

Description:
When a new veículo triggers an `IntegrityError` (e.g. duplicate `placa`), the handler only rolls back when a new cliente was also being created:

```python
if novo_veiculo_data is not None:
    try:
        veiculo_obj = veiculo.create(session, novo_veiculo_data)
    except IntegrityError:
        if novo_cliente_data is not None:   # <-- wrong guard
            session.rollback()
        return _erro_compra(request, session, user, "Veículo já existe")
```

After an `IntegrityError` the SQLAlchemy transaction is poisoned and any further use of the session raises `PendingRollbackError`. `_erro_compra` immediately calls `_ctx_form_compra(session)` (compras.py:278-286), which runs queries — so when an *existing* cliente is selected together with a *new duplicate* veículo, the rollback is skipped, the context query blows up, and the user gets the generic "Erro interno. Contate suporte." 500 instead of the intended "Veículo já existe" 400.

Why it matters:
This is a reachable, user-facing correctness failure on a core write path (registering a purchase). The guard encodes a misunderstanding: rollback is required because of the failed flush, not because a cliente was created.

Concrete fix suggestion:
Always roll back after the `IntegrityError`, unconditionally, before rendering the error form.

Example:
```python
    except IntegrityError:
        session.rollback()
        return _erro_compra(request, session, user, "Veículo já existe")
```

---

## 2. Audited writes depend on an implicit `session.info["usuario_id"]` that each route must remember to set

Location: components/xtreme_system/auditoria/core.py:70-83 (raise), set manually in every write route (e.g. bases/xtreme_system/api/routes/ui_routes/vendas.py:338, compras.py:302, crud_ui/routes.py:492, route_factories.py:76)
Impact: High
Category: Maintainability
Estimated effort: Medium

Description:
`crud.create/update/delete` (components/xtreme_system/crud/core.py:22-68) unconditionally call `auditar`, which raises `AuditError` when `session.info.get("usuario_id")` is absent:

```python
usuario_id = session.info.get("usuario_id")
if usuario_id is None:
    raise AuditError
```

The `usuario_id` is not part of any function signature — it is stashed into `session.info` by hand in every handler. There is no compile-time or type-level guarantee that a new write path sets it.

Why it matters:
Any new endpoint, script, or background task that writes through the CRUD layer without first setting `session.info["usuario_id"]` throws `AuditError`, which surfaces as a 500. The contract is invisible: the coupling between "I want to write a row" and "I must set this magic session key" is only discoverable by runtime failure. This is a latent operational trap that scales badly as the number of write paths grows.

Concrete fix suggestion:
Make the actor explicit. Either thread `usuario_id` (or an `Actor`) as a required parameter into the CRUD/write helpers, or provide a single context manager (`with acting_as(session, user): ...`) that all write routes must enter, so the dependency is greppable and enforced in one place rather than copy-pasted per handler.

---

## 3. In-memory rate limiter is per-process and not concurrency-safe, weakening login brute-force protection

Location: bases/xtreme_system/api/setup.py:90-160 (`_RateLimiter`, `_rate_limit`)
Impact: High
Category: Architecture and design
Estimated effort: Medium

Description:
`_RateLimiter` keeps sliding-window state in a plain `dict[str, deque]` on the app instance. Two structural problems:

1. State is per-process. Under any multi-worker deployment (`uvicorn --workers N`, gunicorn), the effective login limit becomes `5 * N` per minute and the window is not shared, so the documented "5 login attempts / 60s" is not actually enforced cluster-wide.
2. `allow()` does `pop` + mutate + reassign with no lock. Concurrent requests for the same key (same IP) interleave, dropping hits and producing inconsistent counts.

Additionally the key is `request.client.host`; behind a reverse proxy every client shares the proxy IP, so the general 100/min limit becomes a single global bucket (legitimate users lock each other out) unless `X-Forwarded-For` is honored.

Why it matters:
Login throttling is a security control. Silently multiplying the limit by the worker count, or collapsing all users into one proxy IP, means the control does not behave as specified in production. The race is unlikely to corrupt memory but makes the limit non-deterministic under load.

Concrete fix suggestion:
Back the limiter with a shared store (Redis) for multi-worker correctness, or explicitly document/enforce single-worker operation. At minimum, guard `allow()` with a `threading.Lock` and derive the client IP from a trusted `X-Forwarded-For` when running behind a proxy.

---

## 4. Duplicated, hand-written "create with nested cliente/veículo" transaction logic diverges between vendas and compras

Location: bases/xtreme_system/api/routes/ui_routes/compras.py:298-378 and bases/xtreme_system/api/routes/ui_routes/vendas.py:334-374
Impact: Medium
Category: Code quality
Estimated effort: Medium

Description:
Both handlers reimplement the same multi-step flow (resolve/create cliente, optionally create veículo, validate FKs, create the record, handle `IntegrityError`) with slightly different rollback bookkeeping. The divergence is exactly what produced Finding #1: `compras` guards its rollback with `if novo_cliente_data is not None`, `vendas` guards with `if novo_cliente_data is not None` in a different branch, and neither consistently rolls back after a poisoned flush.

Why it matters:
This is the root cause family of the correctness bug above. As long as the transaction/rollback choreography is copy-pasted per entity, the two copies will keep drifting and each new nested-create endpoint re-introduces the same class of bug.

Concrete fix suggestion:
Extract a single helper that owns the "optionally create dependency, create entity, on `IntegrityError` roll back and return a typed error" sequence, and have both routes call it. Centralizing the rollback removes the per-site guards entirely.

---

## 5. N+1 query building the comprovantes map for the compras list

Location: bases/xtreme_system/api/routes/ui_routes/compras.py:97-105 (`_ctx_lista_compras`)
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
The list context issues one query per row:

```python
"comprovantes_por_compra": {
    item.id: imagem_comprovante_compra.list_by_compra(session, item.id)
    for item in compras
}
```

For a page of N compras this is N separate `SELECT ... WHERE compra_id = ?` round-trips (`imagem_comprovante_compra/core.py:40`), on top of the query that fetched the compras.

Why it matters:
List pages grow with the dataset; this turns a bounded page render into O(N) DB round-trips and gets slower precisely as the business accumulates records. It is the classic N+1 that list views must avoid.

Concrete fix suggestion:
Fetch all comprovantes for the visible compra IDs in one query and group in Python:

```python
ids = [c.id for c in compras]
rows = session.query(ImagemComprovanteCompra).filter(
    ImagemComprovanteCompra.compra_id.in_(ids)
).all()
mapa: dict[int, list] = defaultdict(list)
for r in rows:
    mapa[r.compra_id].append(r)
```

---

## 6. `_schema_disponivel` caches "table missing" per-engine and never re-checks, silently disabling the fechamento feature

Location: components/xtreme_system/fechamento_venda/core.py:131-146
Impact: Medium
Category: Error handling and logging
Estimated effort: Low

Description:
`_schema_disponivel` memoizes the result in a process-lifetime `WeakKeyDictionary` keyed by engine. If the app process starts before `make migrate` has created `fechamento_venda`, the first call caches `False`, and every subsequent call returns `False` for the life of the process — even after the migration runs. `list_all`/`get`/`get_by_venda`/`confirmar` then quietly report "no fechamentos" or raise `ERRO_SCHEMA_DESATUALIZADO` until the process is restarted.

Why it matters:
A feature can be silently off in production with no log line explaining why. The failure mode (start order vs. migration) is easy to hit in container orchestration and produces confusing "the button does nothing" reports.

Concrete fix suggestion:
Only cache the positive result, or drop the cache entirely (`inspector.has_table` is cheap against an existing connection). If a negative is cached, emit a warning log so the disabled state is observable, and re-check on the next call instead of pinning it for the process lifetime.

---

## 7. `pode_ver_campo` defaults to visible while `pode_acessar`/`pode_operacao` default to denied — inconsistent permission posture

Location: components/xtreme_system/perfil/core.py:183-210
Impact: Medium
Category: Architecture and design
Estimated effort: Low

Description:
The three permission predicates disagree on the "no profile / unlisted page" default:

- `pode_acessar` → `False` (deny page)
- `pode_operacao` → `False` (deny operation)
- `pode_ver_campo` → `True` (show every field, including sensitive ones like `preco`, `lucro`, `participacao`)

`campos_ocultos` is a denylist, so a profile that simply omits an entry for a page exposes all of that page's protected fields by default.

Why it matters:
Sensitive financial fields are gated by an allow-nothing model everywhere except field visibility, which is fail-open. A profile misconfiguration (page granted, `campos_ocultos` not populated) leaks cost/profit data rather than hiding it. Divergent defaults across three sibling functions are also an ongoing source of "which rule wins?" confusion when adding endpoints.

Concrete fix suggestion:
Make the default posture explicit and consistent. If field visibility is intentionally fail-open, document it prominently next to the function; otherwise flip it to deny-by-default for users/pages without an explicit grant, matching `pode_operacao`.

---

## 8. Audit secret-masking is a hardcoded column allowlist that new sensitive fields will silently bypass

Location: components/xtreme_system/auditoria/core.py:14 (`MASK`) and `_snapshot` at 39-57
Impact: Medium
Category: Maintainability
Estimated effort: Low

Description:
`_snapshot` serializes *every* column of a row into the audit `dados_antes`/`dados_depois` JSON, masking only the two names in `MASK = {"senha_hash", "evolution_api_key"}`. Any future sensitive column (a new token, a secret, a document number treated as PII) is captured verbatim into audit rows unless someone remembers to add its exact attribute name to this set.

Why it matters:
Audit tables are long-lived and widely readable (there is an auditoria UI). A silent, opt-out-by-name masking policy means the safe default is "log the secret," and the failure is invisible until a secret is found sitting in an audit record.

Concrete fix suggestion:
Invert to opt-in, or mark sensitive columns at the model level (e.g. `mapped_column(info={"audit": "mask"})`) and have `_snapshot` read that metadata, so a field declares its own sensitivity rather than relying on a central name list staying in sync.

---

## 9. Error/rollback branches of the create flows are untested, so regressions like Finding #1 pass CI

Location: tests/test_api_compras.py, tests/test_ui.py (no coverage for the existing-cliente + duplicate-veículo path in compras.py:334-340)
Impact: Medium
Category: Testing
Estimated effort: Medium

Description:
The nested-create handlers have several `except IntegrityError: session.rollback()` branches with per-branch conditions, but the suite exercises the happy paths and simple conflicts, not the specific combination (existing cliente selected + new duplicate veículo) that triggers the 500 in Finding #1. The bug is only possible because no test drives that branch.

Why it matters:
These rollback branches are the highest-risk part of the write paths (they run against a poisoned session) and the least covered. Without tests pinning each branch, the divergence described in Finding #4 will keep producing 500s that ship unnoticed.

Concrete fix suggestion:
Add table-driven tests over the create matrix for both vendas and compras: {new cliente, existing cliente} × {new veículo dup, existing veículo, valid} asserting the 400 + error message (never a 500) and that the session remains usable afterward. These tests would fail today on the compras case and lock the fix in place.

---

## 10. `get_session` opens a write transaction and commits on every request, including read-only GETs

Location: components/xtreme_system/database/core.py:56-66
Impact: Low
Category: Performance
Estimated effort: Low

Description:
The single request-scoped dependency always ends with `session.commit()` followed by `_invoke_post_commit`. Every GET (list pages, CSV export, dashboard queries) therefore issues a `COMMIT` even though it wrote nothing, and read paths are indistinguishable from write paths at the session boundary.

Why it matters:
It is not incorrect, but it means read endpoints hold a read/write transaction for their whole duration and pay a commit round-trip they do not need; it also makes it impossible to grant read-only DB roles to read paths. Low priority, but a cheap consistency win and it clarifies which handlers actually mutate state.

Concrete fix suggestion:
Either accept it explicitly (it is a deliberate simplification — worth a one-line comment), or offer a read-only session dependency for pure GET routes that closes without committing. Given the app's size, documenting the intent is likely the right, minimal move rather than splitting the dependency.
