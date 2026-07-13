## Opportunity 1: Shared writes are not atomic

Location: `components/xtreme_system/crud/core.py:18-64`, `bases/xtreme_system/api/route_factories.py:90-139`
Impact: High
Category: Reliability
Estimated effort: High

Description:
`crud.create/update/delete()` commit immediately, and the route factories run follow-up hooks after that commit. That splits one request into multiple independent transactions.

Why it matters:
If a later hook fails, the primary row is already persisted. A vehicle create can succeed while the linked cash row, uploads, or notification step fails.

Concrete fix suggestion:
Keep the unit of work open until all hooks succeed, then commit once.

Example:
```py
with session.begin():
    obj = module.create(session, data)
    after_create(session, obj)
```

## Opportunity 2: Sale status sync leaves stale vehicle state

Location: `components/xtreme_system/venda/core.py:101-151`
Impact: High
Category: Correctness
Estimated effort: Medium

Description:
`_sincronizar_status_veiculo()` only updates the vehicle for `concluido` and `cancelado`. If a concluded sale is edited back to `pendente`, the vehicle stays marked as sold.

Why it matters:
The vehicle status can drift away from the sale status, which breaks inventory accuracy and downstream reporting.

Concrete fix suggestion:
Make the vehicle status derive from the current sale status on every update, including the transition away from `concluido`.

Example:
```py
if status_anterior == StatusVenda.concluido and obj.status != StatusVenda.concluido:
    old_vehicle.status = StatusVeiculo.disponivel
```

## Opportunity 3: File uploads can orphan files on failure

Location: `bases/xtreme_system/api/routes/ui.py:263-412, 668-723`
Impact: High
Category: Reliability
Estimated effort: Medium

Description:
The upload helpers write files to disk before the database work is guaranteed to finish. If a later create or commit fails, the files stay behind.

Why it matters:
Storage slowly fills with orphan files and the UI/database state diverges.

Concrete fix suggestion:
Track every written path and delete them on exception, or stage them in a temp directory and move them only after the DB work succeeds.

Example:
```py
saved = []
try:
    saved.append(path)
    ...
except Exception:
    for p in saved:
        p.unlink(missing_ok=True)
    raise
```

## Opportunity 4: User actions are missing audit attribution

Location: `bases/xtreme_system/api/routes/json.py:61-93`, `bases/xtreme_system/api/routes/ui.py:1194-1310`, `components/xtreme_system/usuario/core.py:58-114`
Impact: High
Category: Error handling and logging
Estimated effort: Low

Description:
Most write paths set `session.info["usuario_id"]`, but the manual user-management routes do not. Their audit rows end up with `usuario_id=None`.

Why it matters:
You lose the ability to answer who created, edited, or deleted users and passwords.

Concrete fix suggestion:
Set the actor in every direct user-management handler before calling the model layer.

Example:
```py
session.info["usuario_id"] = user.id
usuario.change_password(session, obj, nova_senha)
```

## Opportunity 5: Profile delete bypasses audit on linked users

Location: `components/xtreme_system/perfil/core.py:64-70`
Impact: Medium
Category: Maintainability
Estimated effort: Low

Description:
`perfil.delete()` nulls every linked user's `perfil_id` directly, then deletes the profile. Those user updates are never audited.

Why it matters:
Deleting one profile mutates multiple users, but only the profile delete itself is visible in the audit trail.

Concrete fix suggestion:
Use the audited user setter for each affected user, or record explicit audit rows for the unlink step.

Example:
```py
for user in session.query(Usuario).filter_by(perfil_id=obj.id):
    usuario.set_perfil(session, user, None)
```

## Opportunity 6: Sale routes accept invalid seller IDs

Location: `bases/xtreme_system/api/routes/json.py:99-120`, `bases/xtreme_system/api/routes/ui.py:115-133`
Impact: Medium
Category: Correctness
Estimated effort: Low

Description:
`VendaCreate` has `vendedor_id`, but `_validate_cliente_veiculo_fks()` only checks `cliente_id` and `veiculo_id`. A bad seller ID falls through to a database error.

Why it matters:
A valid-looking sale request can become a 500 instead of a clear 400.

Concrete fix suggestion:
Validate `vendedor_id` in the shared helper before calling `venda.create()`.

Example:
```py
if getattr(data, "vendedor_id", None) is not None and usuario.get(session, data.vendedor_id) is None:
    raise HTTPException(status_code=400, detail="vendedor_id inexistente")
```

## Opportunity 7: Rate limiting is process-local

Location: `bases/xtreme_system/api/setup.py:81-145`
Impact: Medium
Category: Reliability
Estimated effort: Medium

Description:
The limiter keeps counters in memory. Each worker has its own counters, so the effective limit changes with process count and resets on restart.

Why it matters:
Production behavior becomes inconsistent as soon as the app runs with more than one process or restarts often.

Concrete fix suggestion:
Move the counters to a shared store like Redis, or document that the limiter is dev-only.

Example:
```py
# store hit timestamps in Redis instead of a local deque
```

## Opportunity 8: Investor creation hides a failed initial aporte

Location: `bases/xtreme_system/api/routes/ui.py:900-943`
Impact: Medium
Category: Error handling and logging
Estimated effort: Low

Description:
`ui_investidor_criar()` catches `Exception` around the optional initial aporte and still returns success.

Why it matters:
Users can create an investor and think the initial capital entry worked when it was silently skipped.

Concrete fix suggestion:
Only catch amount parsing errors; let DB write failures roll back the request.

Example:
```py
try:
    valor = Decimal(valor_str.replace(",", "."))
except InvalidOperation:
    ...
```

## Opportunity 9: Investor dashboards do full-table work in Python

Location: `bases/xtreme_system/api/routes/ui.py:793-834`, `components/xtreme_system/caixa/core.py:192-209`
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
The investor page computes balances and aggregates by loading all vehicles and cash rows into Python, then sorting again in memory.

Why it matters:
Every dashboard render gets more expensive as rows grow, and the same scans happen again for export.

Concrete fix suggestion:
Push the sums and counts into grouped SQL and sort on the database side where possible.

Example:
```py
session.query(LancamentoInvestimento.investidor_id, func.sum(...)).group_by(...)
```

## Opportunity 10: GET requests mutate state while cleaning uploads

Location: `bases/xtreme_system/api/routes/ui.py:294-300, 436-446`
Impact: Low
Category: Correctness
Estimated effort: Low

Description:
Opening the image/document modal deletes DB rows if the underlying file is missing. That cleanup happens inside a read handler.

Why it matters:
A transient storage problem or temporary mount issue can become a data-loss event just by rendering the page.

Concrete fix suggestion:
Move orphan cleanup to an explicit maintenance path or to the delete/upload handlers, not the GET route.

Example:
```py
if path is not None and not path.exists():
    return templates.TemplateResponse(...)
```
