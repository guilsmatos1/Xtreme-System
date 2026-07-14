# Codebase Analysis - Xtreme Motors

## Opportunity 1: Sale lifecycle invariants are not enforced

Location: `components/xtreme_system/venda/core.py:101-152`, `bases/xtreme_system/api/routes/json.py:177-192`, `bases/xtreme_system/api/routes/ui_routes/vendas.py:46-100`
Impact: High
Category: Correctness
Estimated effort: Medium

Description:
`venda.create()` and `venda.update()` only sync the vehicle status from the sale status. They never reject a sale for a non-`disponivel` vehicle, and `venda.delete()` does not restore the vehicle state at all.

Why it matters:
A pending sale can reopen a sold vehicle, and deleting a concluded sale leaves the vehicle stuck as `vendido`. That breaks the core business invariant.

Concrete fix suggestion:
Validate vehicle availability in the shared workflow, and recompute vehicle status on delete from the remaining sales for that vehicle.

Example:
```python
v = session.get(Veiculo, data.veiculo_id)
if v is None:
    raise HTTPException(400, "veiculo_id inexistente")
if v.status != StatusVeiculo.disponivel:
    raise HTTPException(409, "veículo indisponível")
```

## Opportunity 2: Upload validation trusts client metadata and unsafe paths

Location: `bases/xtreme_system/api/routes/ui_routes/common.py:30-58`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py:86-195`
Impact: Medium
Category: Security
Estimated effort: Medium

Description:
`_validar_uploads()` only checks filename extension and the browser-supplied `content_type`. `_uploaded_file_path()` rebuilds a path from the stored URL without resolving it back under the uploads root.

Why it matters:
A renamed payload can bypass the MIME check, and a tampered stored URL can escape the intended directory when files are later deleted.

Concrete fix suggestion:
Sniff magic bytes before persisting and resolve uploaded paths against a fixed root with an `is_relative_to()` guard.

Example:
```python
root = (_ui_dir / "static" / "uploads").resolve()
p = (_ui_dir / url.lstrip("/")).resolve()
if not p.is_relative_to(root):
    return None
```

## Opportunity 3: Deleting parent records leaves upload files behind

Location: `bases/xtreme_system/api/route_factories.py:188-206`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py:64-144,219-283`
Impact: Medium
Category: Maintainability
Estimated effort: Medium

Description:
DB rows for vehicle/client uploads are deleted, but the corresponding files are only removed on explicit single-file delete or when a modal happens to open and notices a missing file. Parent deletes do not clean the filesystem.

Why it matters:
Orphaned files accumulate indefinitely and make storage usage and recovery behavior unpredictable.

Concrete fix suggestion:
Add `before_delete` cleanup hooks for vehicles and clients that iterate child URLs and unlink files before the ORM delete.

Example:
```python
for img in list(item.imagens):
    path = _uploaded_file_path(img.url or "")
    if path is not None:
        path.unlink(missing_ok=True)
```

## Opportunity 4: The rate limiter leaks per-IP buckets

Location: `bases/xtreme_system/api/setup.py:81-145`
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
`_RateLimiter._hits` grows forever because empty deques are never removed after their window expires.

Why it matters:
A long-lived process behind scanners, proxies, or NAT can accumulate unbounded in-memory keys.

Concrete fix suggestion:
Drop empty keys during pruning and document that the limiter is process-local.

Example:
```python
if not hits:
    self._hits.pop(key, None)
```

## Opportunity 5: Investor aggregates are computed in Python on every render

Location: `components/xtreme_system/caixa/core.py:192-209`, `bases/xtreme_system/api/routes/ui_routes/investidores.py:83-170`
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
`agregados_investidores()` loads every vehicle and every cash launch into Python, then loops to build the totals used by the investor page and CSV export.

Why it matters:
The cost grows linearly with data size and hits every page load, sort, and export.

Concrete fix suggestion:
Replace both loops with grouped SQL queries and reuse the existing `saldos()` pattern.

Example:
```python
session.query(Veiculo.investidor_id, func.count(), func.sum(Veiculo.preco)).group_by(Veiculo.investidor_id)
```

## Opportunity 6: Latest purchase lookup scans too much history

Location: `components/xtreme_system/compra/core.py:78-92`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py:41-61`
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
`latest_by_veiculo_ids()` fetches all purchases for the selected vehicles, orders them, and deduplicates them in Python.

Why it matters:
Vehicle list pages and forms pay for the full purchase history even though they only need the newest row per vehicle.

Concrete fix suggestion:
Use a window function or subquery that selects only the newest purchase per vehicle.

Example:
```python
row_number().over(partition_by=Compra.veiculo_id, order_by=(Compra.data_compra.desc(), Compra.id.desc()))
```

## Opportunity 7: Dashboard trend grouping does full-row aggregation in Python

Location: `components/xtreme_system/venda/core.py:231-270`, `bases/xtreme_system/api/routes/ui_routes/dashboard.py:28-78`
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
`tendencia_por_periodo()` loads all matching sales and groups them in Python by week or month.

Why it matters:
The dashboard is a hot path; this gets slower as sale history grows.

Concrete fix suggestion:
Push the date bucketing into SQL or cap the rows returned before grouping.

Example:
```python
session.query(func.date_trunc("month", Venda.data_venda), func.count(), func.sum(Venda.valor_venda))
```

## Opportunity 8: List and export flows always load whole tables

Location: `components/xtreme_system/crud/core.py:16-17`, `bases/xtreme_system/api/route_factories.py:282-348,473-521`
Impact: Medium
Category: Performance
Estimated effort: Medium

Description:
The generic UI factories call `list_all()` and then sort/filter in memory, and CSV exports always materialize the full result set.

Why it matters:
This is fine for small tables but scales poorly and makes every page pay for rows it may never show.

Concrete fix suggestion:
Let components expose query methods with limit/offset/order, and stream or page CSV generation.

Example:
```python
def list_page(session, *, limit: int, offset: int, order_by: str) -> list[M]: ...
```

## Opportunity 9: WhatsApp notifications block the sale request thread

Location: `components/xtreme_system/whatsapp/core.py:91-123`, `bases/xtreme_system/api/routes/json.py:177-192`, `bases/xtreme_system/api/routes/ui_routes/vendas.py:46-100`
Impact: Medium
Category: Performance
Estimated effort: Low

Description:
`notificar_venda()` calls a synchronous `urlopen(..., timeout=10)` inside the request path. It is best-effort, but it still runs before the request finishes.

Why it matters:
A slow upstream can hold the worker for up to 10 seconds on every sale create.

Concrete fix suggestion:
Move the send into a `BackgroundTasks` job or a small outbox table.

Example:
```python
background_tasks.add_task(whatsapp.notificar_venda, session, venda_obj)
```

## Opportunity 10: Profile assignment can surface FK failures as 500s

Location: `components/xtreme_system/usuario/core.py:58-114`, `bases/xtreme_system/api/routes/json.py:64-99`, `bases/xtreme_system/api/routes/ui_routes/usuarios.py:70-201`
Impact: Low
Category: Error handling
Estimated effort: Low

Description:
`perfil_id` is written directly in `usuario.create()` and `usuario.set_perfil()` with no existence check. A tampered form or API call can hit a foreign-key error and bubble out as an internal server error.

Why it matters:
This turns a recoverable client mistake into a 500 and makes the UI/API feel brittle.

Concrete fix suggestion:
Check the profile id before writing it and return `400`/`409` with a clear message.

Example:
```python
if perfil_id is not None and session.get(Perfil, perfil_id) is None:
    raise HTTPException(400, "perfil_id inexistente")
```
