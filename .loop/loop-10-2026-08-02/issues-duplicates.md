# Improvement opportunities

- **Generated:** 2026-08-01T16:34:03-03:00
- **Total:** 12

## imp-20260801-001 — Unify the five copy-pasted attachment (anexos) route modules behind one route factory

- **Impact:** High
- **Category:** Literal duplication
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** routes, uploads, htmx, route-factory, copy-paste
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos_procuracao.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos_imagens.py`, `bases/xtreme_system/api/routes/ui_routes/clientes.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/uploads.py`
- **Related opportunities:** imp-20260801-002

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py:83` — `ui_veiculo_documentos_upload`

```python
@app.post("/ui/veiculos/{veiculo_id}/documentos")
def ui_veiculo_documentos_upload(
    request: Request,
    session: SessionDep,
    user: _DocumentoDep,
    veiculo_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    found(veiculo.get(session, veiculo_id), "Veículo")
    erro = salvar_anexos_entidade(
        session,
        upload_dir=uploads_dir(veiculo_id) / "documentos",
```

### Description

`veiculos_documentos.py` and `veiculos_procuracao.py` are the same module with names substituted.
Both define a `_<coisa>_modal` helper, a `_<coisa>_erro_modal` helper that repeats the same body
plus `erro` and `status_code=400`, a GET modal route, a POST upload route that calls
`salvar_anexos_entidade` and branches to the error modal, and a POST delete route that calls
`excluir_anexo_entidade` and re-renders the modal OOB. `veiculos_imagens.py`,
the cliente-documentos block in `clientes.py:140-238`, and the compra-comprovantes block in
`compras.py:169-272` are the same five-part shape again.

The leaf-level work is already factored out — `salvar_anexos_entidade` and `excluir_anexo_entidade`
in `uploads.py`, and the `ui.anexos_modal` macro in `_macros.html`. What is duplicated is the
scaffolding *between* them: the modal pair and the three route handlers, roughly 100 lines each
across five entities.

### Why it matters

Every change to attachment handling — a new validation, a different OOB refresh, an audit hook, a
correction to the 400 status — must be made five times, and the copies have already drifted
(imp-20260801-002 documents divergent permission wiring across the same five sites). New attachment
types are added by copying a whole module, which reproduces whatever drift exists at copy time.

### Concrete fix

Add a `register_anexos_routes(...)` factory next to the existing helpers in `uploads.py`,
parameterized by the pieces that actually differ: URL segment, parent module and label, attachment
module and schema, template name, upload directory builder, URL prefix, permission dependencies,
and the not-found detail string. Register the five entities through it and delete the per-entity
modules. `crud_ui/routes.py` already establishes the route-factory pattern in this codebase, so this
introduces no new architectural idea.

### Potential savings

Roughly 400 of the ~520 lines across the five attachment blocks collapse into one ~120-line factory
plus five short registration calls.

### Domain details

#### Consolidation details

- **Duplicate type:** Literal duplication
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py:28-126`,
  `bases/xtreme_system/api/routes/ui_routes/veiculos_procuracao.py:34-132`,
  `bases/xtreme_system/api/routes/ui_routes/veiculos_imagens.py:35-143`,
  `bases/xtreme_system/api/routes/ui_routes/clientes.py:140-238`,
  `bases/xtreme_system/api/routes/ui_routes/compras.py:169-272`. Consolidation target:
  `bases/xtreme_system/api/routes/ui_routes/uploads.py`.
- **Differences between copies:** parent entity and its `found()` label; the veiculo copies call
  `session.refresh(item)` before rendering while the compra copy does not; the compra copy fetches
  its attachment list explicitly via `imagem_comprovante_compra.list_by_compra` while the veiculo
  copies read the ORM relationship off the refreshed parent; upload directory builder
  (`uploads_dir(id) / "documentos"` vs `_uploads_procuracao_dir` vs `uploads_compra_dir`); template
  name; form field name; permission dependencies; the imagens copy passes extra macro arguments.
- **Behavior preservation:** the union must be preserved — the factory needs an opt-in
  `refresh_parent` flag and a pluggable "load attachments" callable so that the compra path keeps its
  explicit query and the veiculo paths keep their `session.refresh`. Collapsing those two to one
  behavior would change what a stale identity-map parent renders.
- **Verification plan:** the attachment routes have existing coverage in `tests/test_uploads.py`;
  run it unchanged against the factory. Add a parametrized case asserting each of the five entities
  returns 200 on GET, 400 with the error modal on an invalid upload, and 200 with `action_oob`
  markup after a successful upload and after a delete.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both `veiculos_documentos.py` and `veiculos_procuracao.py` were read in full and are
    structurally identical function for function.
  - The consolidation target already exists; `salvar_anexos_entidade` / `excluir_anexo_entidade` are
    called identically from all five sites.
- **Weaknesses:**
  - The clientes and compras copies were read only across their modal + route ranges, so a small
    entity-specific behavior inside those handlers could still need its own factory hook.
- **Suggested checks:**
  - Confirm the permission dependency names for all five entities are expressible as
    `require_operacao(<pagina>, <operacao>)` with no bespoke dependency logic.

## imp-20260801-002 — Three divergent permission conventions across five call sites of the same `anexos_modal` macro

- **Impact:** High
- **Category:** Template consolidation
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** templates, permissions, jinja, ui-affordance, drift
- **Files affected:** `bases/xtreme_system/api/templates/_modal_documentos_veiculo.html`, `bases/xtreme_system/api/templates/_modal_documentos_cliente.html`, `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html`, `bases/xtreme_system/api/templates/_modal_procuracao_veiculo.html`, `bases/xtreme_system/api/templates/_modal_comprovantes_compra.html`
- **Related opportunities:** imp-20260801-001

### Location

`bases/xtreme_system/api/templates/_modal_documentos_veiculo.html:1` — `anexos_modal` call

```jinja
{% import "_macros.html" as ui %}
{{ ui.anexos_modal(
  "modal-documentos-title",
  "Documento do Veículo — " ~ veiculo.modelo ~ " (" ~ veiculo.placa ~ ")",
  veiculo.documentos,
  erro,
  pending_upload_paths,
  "file",
  "Nenhum documento",
  "Envie documentos deste veículo usando a área abaixo.",
  true,
  "/ui/veiculos/" ~ veiculo.id ~ "/documentos",
```

### Description

`ui.anexos_modal` takes `upload_allowed` as its 9th argument and `delete_allowed` as its 17th. The
five templates that call it supply those two arguments three different ways:

| Template | `upload_allowed` | `delete_allowed` |
| --- | --- | --- |
| `_modal_documentos_veiculo.html` | `true` | `true` |
| `_modal_documentos_cliente.html` | `true` | `pode_operacao(user, 'clientes', 'excluir_documento')` |
| `_modal_imagens_veiculo.html` | `pode_enviar_imagens` (context var) | `pode_excluir_imagens` |
| `_modal_procuracao_veiculo.html` | `pode_operacao(user, 'veiculos', 'enviar_procuracao')` | `pode_operacao(user, 'veiculos', 'excluir_procuracao')` |
| `_modal_comprovantes_compra.html` | `pode_operacao(user, 'compras', 'enviar_comprovante')` | `pode_operacao(user, 'compras', 'excluir_comprovante')` |

The hardcoded `true` values are not a server-side authorization hole: the corresponding routes are
guarded by `require_operacao("veiculos", "upload_documento")` at
`veiculos_documentos.py:23-25` and by `_ExcluirDocumentoDep` at `clientes.py:75`. The defect is that
the same macro, expressing one rule ("show the control only to users who may perform the operation"),
is wired three ways.

### Why it matters

A user without `upload_documento` is shown a working-looking upload dropzone on the veiculo
documents modal and a delete button on all its documents; the request then fails at the dependency
with a 403 rendered into an HTMX target. The cliente modal is inconsistent with itself — it hides
delete but shows upload. Because the permission decision is expressed as a positional literal, no
grep for `pode_operacao` reveals the sites that skipped it, so the drift is invisible to review.

### Concrete fix

Replace both `true` literals in `_modal_documentos_veiculo.html` (lines 11 and 19) and the `true` at
`_modal_documentos_cliente.html:11` with the `pode_operacao(user, <pagina>, <operacao>)` calls
matching the dependency already enforced on each route, and switch the imagens copy from
route-supplied context variables to the same inline form. Then make `upload_allowed` and
`delete_allowed` keyword-only in the `anexos_modal` signature so a future call site cannot silently
pass the wrong positional argument.

### Domain details

#### Consolidation details

- **Duplicate type:** Template consolidation
- **All sites:** `bases/xtreme_system/api/templates/_modal_documentos_veiculo.html:11` and `:19`,
  `bases/xtreme_system/api/templates/_modal_documentos_cliente.html:11` and `:19`,
  `bases/xtreme_system/api/templates/_modal_imagens_veiculo.html:11` and `:19`,
  `bases/xtreme_system/api/templates/_modal_procuracao_veiculo.html:11` and `:19`,
  `bases/xtreme_system/api/templates/_modal_comprovantes_compra.html:11` and `:19`. Macro definition:
  `bases/xtreme_system/api/templates/_macros.html:167`.
- **Differences between copies:** three conventions — literal `true`, a route-supplied context
  variable, and an inline `pode_operacao(...)` call. `_modal_documentos_cliente.html` mixes two of
  them within one call.
- **Behavior preservation:** the `pode_operacao` behavior wins. This deliberately *changes* rendered
  output for users lacking the operation — the controls disappear instead of 403-ing on use — which
  is the intended correction, not a regression. No server-side behavior changes.
- **Verification plan:** render each modal for a user with the operation and a user without it, and
  assert the upload form and delete buttons are present in the first case and absent in the second.
  The permission helpers are already exercised by the perfil tests, so the new assertions only need
  to cover template output.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - All five call sites were read verbatim and the macro's positional signature was confirmed at
    `_macros.html:167-185`.
  - The server-side dependencies were checked before framing this as an affordance problem rather
    than an authorization bypass, so the impact claim is not overstated.
- **Weaknesses:**
  - Whether every entity has a defined `enviar_documento`-style operation name in the perfil page
    definitions was not verified; if one is missing it must be added before the fix.
- **Suggested checks:**
  - Confirm the operation slugs used by `require_operacao` on each route exist in `perfil.PAGINAS`
    so `pode_operacao` does not silently return `False` for everyone.

## imp-20260801-003 — The venda value-coherence rule is implemented three times and executed twice per update

- **Impact:** High
- **Category:** Parallel implementations
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** business-rules, validation, venda, pydantic, drift
- **Files affected:** `components/xtreme_system/venda/core.py`, `components/xtreme_system/workflow/core.py`
- **Related opportunities:** imp-20260801-004

### Location

`components/xtreme_system/venda/core.py:214` — `validate_valores_venda_update`

```python
def validate_valores_venda_update(venda_obj: Venda, data: VendaUpdate) -> None:
    valor_venda = (
        data.valor_venda if data.valor_venda is not None else venda_obj.valor_venda
    )
    valor_entrada = (
        data.valor_entrada
        if data.valor_entrada is not None
        else venda_obj.valor_entrada
    )
    if valor_entrada is not None and valor_entrada > valor_venda:
        raise ValueError(ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA)
```

### Description

One rule — "entrada must not exceed valor_venda, and pagamento_pendente/valor_pendente/datas_pagamento
must be coherent" — has three implementations in the same file:

1. `VendaCreate.validar_valores` (`venda/core.py:171-179`), a model validator over the full payload.
2. `VendaUpdate.validar_valores` (`venda/core.py:200-211`), a model validator over the partial
   payload only, which can only compare the fields present in the request.
3. `validate_valores_venda_update` (`venda/core.py:214-240`), which merges the partial payload with
   the persisted row before applying the same two checks.

Copies 2 and 3 differ in what they can see, and that difference is load-bearing: a `VendaUpdate` that
sets only `valor_entrada` passes the model validator (no `valor_venda` to compare against) and is
caught only by copy 3. Copy 1 duplicates copy 3's checks against a payload where every field is
present.

### Why it matters

The rule is only fully enforced when copy 3 runs. Any write path that constructs a `VendaUpdate` and
persists it without calling `validate_valores_venda_update` silently accepts an entrada larger than
the sale price. Adding a fourth coherence condition means editing three places with three different
field-availability assumptions, and forgetting one of them fails open rather than closed.

### Concrete fix

Extract the merged-value comparison into one private helper that takes plain resolved values
(`valor_venda`, `valor_entrada`, `pagamento_pendente`, `valor_pendente`, `datas_pagamento`) and
raises. Have all three current entry points resolve their inputs and delegate to it:
`VendaCreate.validar_valores` passes its own fields, `validate_valores_venda_update` passes the
payload-merged-with-row values, and `VendaUpdate.validar_valores` is reduced to the checks it can
actually make on a partial payload — or removed, once every update path is confirmed to go through
`validate_valores_venda_update`.

### Domain details

#### Consolidation details

- **Duplicate type:** Parallel implementation
- **All sites:** `components/xtreme_system/venda/core.py:171-179` (`VendaCreate.validar_valores`),
  `components/xtreme_system/venda/core.py:200-211` (`VendaUpdate.validar_valores`),
  `components/xtreme_system/venda/core.py:214-240` (`validate_valores_venda_update`). Callers:
  `components/xtreme_system/venda/core.py:385` (`update`) and
  `components/xtreme_system/workflow/core.py:71-77`.
- **Differences between copies:** the create validator sees every field; the update validator sees
  only `model_fields_set` and cannot compare against persisted values; the standalone function
  resolves each field from the payload when set and from the row otherwise. The create and update
  validators raise `ValueError` inside Pydantic (surfacing as `ValidationError`); the standalone
  function raises a bare `ValueError`.
- **Behavior preservation:** the union of checks must be preserved, with the merged-value semantics
  of `validate_valores_venda_update` winning wherever the two disagree — it is the only copy that
  sees the full post-update state. The exception *types* must not change: callers distinguish
  `ValidationError` from `ValueError`.
- **Verification plan:** before refactoring, add table-driven tests over the shared helper covering
  entrada-only updates, valor-only updates, both-fields updates, and each
  `pagamento_pendente`/`valor_pendente`/`datas_pagamento` combination. Those tests must pass
  identically before and after. `tests/test_fechamento_venda.py` and the venda API tests then cover
  the wiring.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - `validate_valores_venda_update` was read verbatim, and both model validators sit in the same
    file with the same error constant, confirming they express one rule.
  - The field-availability asymmetry between copies 2 and 3 is visible directly in the
    `model_fields_set` guards.
- **Weaknesses:**
  - `VendaCreate.validar_valores` at lines 171-179 was identified from the signature sweep and the
    surrounding context rather than read line by line, so its exact check list is inferred from the
    shared error constant.
- **Suggested checks:**
  - Read `venda/core.py:151-212` in full and confirm the create validator's checks are a strict
    subset of the standalone function's before collapsing them.

## imp-20260801-004 — `workflow.validate_valores_venda_update` is a forwarding wrapper that causes the same validation to run twice

- **Impact:** Medium
- **Category:** Redundant layers
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** workflow, validation, wrapper, error-handling, venda
- **Files affected:** `components/xtreme_system/workflow/core.py`, `components/xtreme_system/venda/core.py`
- **Related opportunities:** imp-20260801-003

### Location

`components/xtreme_system/workflow/core.py:71` — `validate_valores_venda_update`

```python
def validate_valores_venda_update(
    venda_obj: venda.Venda, data: venda.VendaUpdate
) -> None:
    try:
        venda.validate_valores_venda_update(venda_obj, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def validate_veiculo_disponivel_para_venda(session: Session, veiculo_id: int) -> None:
    veiculo_obj = session.get(veiculo.Veiculo, veiculo_id, with_for_update=True)
    if veiculo_obj is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if veiculo_obj.status != veiculo.StatusVeiculo.disponivel:
```

### Description

`workflow.validate_valores_venda_update` shares its name with the function it wraps and adds exactly
one thing: translating `ValueError` into `HTTPException(400)`. Its only caller is
`workflow.validate_venda_update` (line 97), which is itself called from
`venda_write._validar_venda` (`venda_write.py:215`) before the route calls `venda.update`. But
`venda.update` re-runs `validate_valores_venda_update` itself at `venda/core.py:385`.

So on every UI venda update the rule is evaluated twice against the same inputs, and the second
evaluation is *outside* the wrapper — meaning any path that reaches `venda.update` without going
through the workflow layer raises a raw `ValueError`, not a 400.

### Why it matters

Two consequences. First, the redundant call is wasted work on a hot write path and, more
importantly, misleading: a reader cannot tell which of the two calls is the authoritative guard.
Second, the error contract is inconsistent — the same violation surfaces as a clean HTTP 400 through
the workflow layer and as an unhandled `ValueError` (a 500) through the direct one. Since the JSON
API and the HTMX UI both write vendas, the same bad payload can produce two different responses
depending on which entry point is used.

### Concrete fix

Pick one owner. The lower-risk option: keep the validation inside `venda.update` (so it cannot be
bypassed), delete the redundant `validate_valores_venda_update` call from
`workflow.validate_venda_update`, and move the `ValueError → HTTPException(400)` translation to
where the boundary actually is — either a FastAPI exception handler for the venda `ValueError`
types, or a `try/except` around the `venda.update` call in the route. That removes the wrapper, the
double execution, and the divergent error contract in one change.

### Domain details

#### Consolidation details

- **Duplicate type:** Redundant layer
- **All sites:** `components/xtreme_system/workflow/core.py:71-77` (the wrapper),
  `components/xtreme_system/workflow/core.py:97` (its only caller),
  `components/xtreme_system/venda/core.py:385` (the second, independent execution inside
  `venda.update`).
- **Differences between copies:** the workflow call happens before persistence and converts
  `ValueError` to `HTTPException(400)`; the `venda.update` call happens at write time and lets
  `ValueError` propagate. Both evaluate identical inputs, since `venda.update` receives the same
  `obj` and `data` the workflow validated.
- **Behavior preservation:** the 400 status and detail text must be preserved for every existing
  caller; the in-`update` guard must be preserved so non-workflow callers stay protected. Only the
  duplicate evaluation and the name-shadowing wrapper are removed.
- **Verification plan:** assert that a venda update with `valor_entrada > valor_venda` still returns
  400 with the same detail through both the JSON API and the HTMX route, and add a direct
  `venda.update` unit test asserting the rule still rejects the write when the workflow layer is
  bypassed.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The wrapper, its single caller, and the second call inside `venda.update` were all read
    verbatim; the double execution is not inferred.
- **Weaknesses:**
  - The claim that a raw `ValueError` reaches the client as a 500 depends on there being no global
    `ValueError` exception handler registered in `api/setup.py`, which was not checked.
- **Suggested checks:**
  - Grep `bases/xtreme_system/api/setup.py` for `add_exception_handler` / `exception_handler` to
    confirm whether `ValueError` is already translated at the app boundary.

## imp-20260801-005 — Three byte-identical "outra venda com status X" queries differing only in column and status

- **Impact:** Medium
- **Category:** Near duplication
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** query-construction, venda, veiculo-status, sqlalchemy
- **Files affected:** `components/xtreme_system/venda/core.py`
- **Related opportunities:** None

### Location

`components/xtreme_system/venda/core.py:290` — `veiculo_tem_outra_venda_concluida`

```python
def veiculo_tem_outra_venda_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(Venda).filter(
        Venda.veiculo_id == veiculo_id,
        Venda.status == StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def veiculo_tem_outra_venda_pendente(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
```

### Description

`veiculo_tem_outra_venda_concluida` (line 290), `veiculo_tem_outra_venda_pendente` (line 302), and
`veiculo_tem_outra_troca_concluida` (line 314) have identical signatures and identical ten-line
bodies. The only variation is which two values go into the filter: the join column
(`Venda.veiculo_id` vs `Venda.veiculo_troca_id`) and the status (`concluido` vs `pendente`). All
three exist solely to feed the priority ladder in `recomputar_status_veiculo_por_vendas`
(lines 326-345).

### Why it matters

The three copies encode the vehicle-status recomputation rule, which is what decides whether a
vehicle shows as `vendido`, `reservado`, or `disponivel`. A change that must apply to all three —
excluding soft-deleted vendas, adding a tenant filter, switching `.first()` to an `EXISTS` — has to
be replicated three times, and applying it to two of the three produces a status ladder that
disagrees with itself in a way no single test would catch.

### Concrete fix

Replace the three functions with one private helper and keep the three names as thin, explicit
delegations so no call site changes:

```python
def _existe_venda(
    session: Session,
    coluna: InstrumentedAttribute[int | None],
    veiculo_id: int,
    status: StatusVenda,
    excluir_venda_id: int | None,
) -> bool:
    sql_query = session.query(Venda).filter(coluna == veiculo_id, Venda.status == status)
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(Venda.id != excluir_venda_id)
    return sql_query.first() is not None
```

### Potential savings

Thirty-four lines become roughly fifteen, and the recomputation rule gains a single edit point.

### Domain details

#### Consolidation details

- **Duplicate type:** Near duplication
- **All sites:** `components/xtreme_system/venda/core.py:290-299`,
  `components/xtreme_system/venda/core.py:302-311`,
  `components/xtreme_system/venda/core.py:314-323`. Sole consumer:
  `components/xtreme_system/venda/core.py:326-345`.
- **Differences between copies:** exactly two tokens. Copy 1 filters `Venda.veiculo_id` /
  `StatusVenda.concluido`; copy 2 `Venda.veiculo_id` / `StatusVenda.pendente`; copy 3
  `Venda.veiculo_troca_id` / `StatusVenda.concluido`. Signatures, the `excluir_venda_id` guard, and
  the `.first() is not None` return are character-for-character identical.
- **Behavior preservation:** trivially preserved — the generated SQL is unchanged for each of the
  three parameter pairs, and the public function names and signatures are kept.
- **Verification plan:** the existing venda status-sync tests exercise all three branches of
  `recomputar_status_veiculo_por_vendas`; run them unchanged. Optionally capture the emitted SQL for
  each of the three helpers before and after and assert equality.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - All three functions and their only consumer were read verbatim in one contiguous range; the
    duplication is exact and not inferred.
- **Weaknesses:**
  - Callers outside `venda/core.py` were not enumerated, so the delegation shims should be kept
    rather than the three names deleted.
- **Suggested checks:**
  - `rg "veiculo_tem_outra"` across `bases/` and `components/` to confirm the external call sites
    before choosing whether to keep the shims permanently.

## imp-20260801-006 — Two parallel implementations of "create nested entity, roll back on conflict" with different rollback semantics

- **Impact:** Medium
- **Category:** Parallel implementations
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** transactions, rollback, nested-writes, integrity-error, venda, compra
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py`, `bases/xtreme_system/api/routes/ui_routes/nested_writes.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`
- **Related opportunities:** imp-20260801-008

### Location

`bases/xtreme_system/api/routes/ui_routes/venda_write.py:130` — `_create_nested`

```python
) -> tuple[EntityT | None, bool]:
    if data is None:
        return None, False
    nested_writes.add(data)
    try:
        return create_fn(session, data, actor_id), False
    except IntegrityError:
        nested_writes.rollback(session)
        return None, True
```

### Description

The venda create path and the compra create path each solve the same problem — a form may create a
cliente and/or a veiculo inline before the main record, and an `IntegrityError` on either must undo
the partial work and render a conflict form — with two independent helpers:

- `venda_write._create_nested` (lines 124-138) tracks pending writes in a `NestedWrites` accumulator,
  calls `nested_writes.rollback(session)` on `IntegrityError`, and returns a `(obj, conflito: bool)`
  tuple that the caller turns into a `VendaErro`.
- `nested_writes.criar_aninhado_ou_resposta_conflito` (lines 12-24) has no accumulator, delegates to
  `rollback_integrity_error_response(session, build_conflict_response)`, and returns
  `(obj, HTMLResponse | None)` — the response is built inside the helper.

`compras.py:399` and `compras.py:421` use the second; `venda_write.py:165` and `venda_write.py:190`
use the first.

### Why it matters

The two differ on the thing that matters most in this codebase: rollback discipline. The compra path
routes through `rollback_integrity_error_response`, the shared rollback entry point; the venda path
rolls back through its own `NestedWrites` accumulator instead. Any fix to how a dirty session is
recovered after a nested-write conflict lands in one path and not the other, and the two are not
greppable as one concern. The second helper also mixes a persistence concern with HTTP response
construction, which is why the venda path could not reuse it in the first place.

### Concrete fix

Narrow `criar_aninhado_ou_resposta_conflito` to the persistence concern — have it return
`(obj, conflito: bool)` and perform only the rollback, matching `_create_nested`'s shape — and let
each caller build its own response. Then add the optional `NestedWrites` accumulator as a parameter
so `venda_write` can delete `_create_nested` and call the shared helper. Both rollback paths then run
through the same code, and `compras.py` keeps its current behavior by wrapping the boolean in the
`conflict_form_response` it already builds.

### Domain details

#### Consolidation details

- **Duplicate type:** Parallel implementation
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py:124-138` (helper),
  called at `venda_write.py:165-171` and `venda_write.py:190-196`;
  `bases/xtreme_system/api/routes/ui_routes/nested_writes.py:12-24` (helper), called at
  `bases/xtreme_system/api/routes/ui_routes/compras.py:399-415` and `compras.py:421-437`.
- **Differences between copies:** the venda helper accumulates pending writes via `NestedWrites.add`
  and rolls back through `NestedWrites.rollback`; the compra helper does neither and calls
  `rollback_integrity_error_response`. The venda helper returns a boolean conflict flag; the compra
  helper returns a fully built `HTMLResponse`. The venda helper types `actor_id` as `int`, the compra
  helper as `int | None`.
- **Behavior preservation:** the union must be preserved. The accumulator is not redundant — the
  venda path needs it because `_preparar_veiculo_troca` may roll back writes made earlier by
  `_preparar_cliente`, a multi-step case the compra path does not have. It must become an optional
  parameter, not be dropped.
- **Verification plan:** existing tests cover the duplicate-plate and duplicate-documento conflict
  paths for both compra and venda creation; run them unchanged. Add a venda test that creates both a
  nested cliente and a conflicting nested veiculo de troca in one submit and asserts the cliente was
  not persisted, which is the case only the accumulator handles.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Both helpers and all four call sites were read verbatim; the divergent rollback mechanisms are
    directly visible.
- **Weaknesses:**
  - `NestedWrites.add` / `NestedWrites.rollback` (declared at `venda_write.py:27`) were not read, so
    the accumulator's exact rollback semantics — and therefore how cleanly it becomes an optional
    parameter — are inferred from its call sites.
- **Suggested checks:**
  - Read `venda_write.py:27-52` and confirm `NestedWrites.rollback` is compatible with the
    `session.rollback()` that `rollback_integrity_error_response` performs, so combining them cannot
    double-roll-back.

## imp-20260801-007 — The `ValidationError | HTTPException → message` ternary is reimplemented at four sites despite an existing helper

- **Impact:** Medium
- **Category:** Reimplemented helpers
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** error-handling, helpers, routes, copy-paste
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`, `bases/xtreme_system/api/routes/ui_routes/vendas.py`
- **Related opportunities:** imp-20260801-009, imp-20260801-012

### Location

`bases/xtreme_system/api/routes/ui_routes/venda_write.py:141` — `_validation_message`

```python
def _validation_message(exc: ValidationError | HTTPException) -> str:
    return (
        str(exc.detail)
        if isinstance(exc, HTTPException)
        else validation_error_detail(exc)
    )


def _preparar_cliente(
    session: Session,
    form: Any,
    user: usuario.Usuario,
```

### Description

`venda_write._validation_message` names the rule "turn a validation failure into a user-facing
string". Three other route modules inline the identical four-line ternary instead of importing it:

- `compras.py:463-467`, inside the `except (ValidationError, HTTPException)` of `_criar_compra`
- `veiculos.py:378-382`, inside the same except clause of `_atualizar_veiculo`
- `lancamentos.py:78-82`, inside `_erro_lancamento`

A fifth site, `vendas.py:584-588`, is a *divergent* variant: it handles
`ValidationError | FechamentoVendaError` and falls back to `str(exc)` rather than `exc.detail`,
inverting the isinstance test.

### Why it matters

Error-message formatting is user-facing surface. The four identical copies mean a change to how
Pydantic errors are rendered — adding a field name, truncating, translating — reaches one screen and
not the others, so the same class of failure reads differently depending on which form produced it.
The divergent fifth copy shows this has already started.

### Concrete fix

Move `_validation_message` from `venda_write.py` to `crud_ui/responses.py`, next to the
`validation_error_detail` it already delegates to, export it as `validation_message`, and replace the
three identical inline ternaries with calls to it. Leave `vendas.py:584-588` alone or widen the
shared helper's union to include `FechamentoVendaError` with an explicit `str(exc)` branch — that
copy handles a genuinely different exception type and should not be silently folded in.

### Domain details

#### Consolidation details

- **Duplicate type:** Reimplemented helper
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py:141-146` (the helper),
  `bases/xtreme_system/api/routes/ui_routes/compras.py:463-467`,
  `bases/xtreme_system/api/routes/ui_routes/veiculos.py:378-382`,
  `bases/xtreme_system/api/routes/ui_routes/lancamentos.py:78-82`, and the divergent
  `bases/xtreme_system/api/routes/ui_routes/vendas.py:584-588`. Consolidation target:
  `bases/xtreme_system/api/crud_ui/responses.py:22` (`validation_error_detail`).
- **Differences between copies:** the four `HTTPException`-based copies are character-identical apart
  from indentation and whether the result is bound to `msg` or returned directly. The `vendas.py`
  copy differs materially: different exception union, inverted isinstance test, `str(exc)` fallback
  instead of `str(exc.detail)`.
- **Behavior preservation:** the four identical copies collapse with no observable change. The
  `vendas.py` variant's behavior wins on its own path and must not be replaced by the shared helper
  unless the union is explicitly widened — `FechamentoVendaError` has no `.detail` attribute.
- **Verification plan:** assert the rendered error string is unchanged for one `ValidationError` case
  and one `HTTPException` case per converted route (compra create, veiculo update, lancamento
  create/update). Existing form-validation tests already assert on error text.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - All five sites were located by a single grep and their surrounding context read, so both the
    identical copies and the divergent one are confirmed rather than assumed.
- **Weaknesses:**
  - Whether `crud_ui/responses.py` importing `HTTPException` introduces an import-linter contract
    violation was not checked; the repo has an `.import_linter_cache`, so layer contracts are
    enforced.
- **Suggested checks:**
  - Run the import-linter contracts after moving the helper to confirm `crud_ui.responses` is allowed
    to depend on FastAPI exception types.

## imp-20260801-008 — The `IntegrityError → conflict_form_response` block is repeated six times, and the venda update copy silently drops form data

- **Impact:** Medium
- **Category:** Near duplication
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** error-handling, conflict, forms, htmx, drift, data-loss
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
- **Related opportunities:** imp-20260801-006, imp-20260801-009, imp-20260801-010, imp-20260801-012

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:484` — `_atualizar_venda`

```python
        return rollback_integrity_error_response(
            session,
            lambda: conflict_form_response(
                templates,
                request,
                "_form_venda.html",
                ctx_form=_ctx_form_venda(session),
                item_key="venda",
                item=obj,
                erro=write_conflict_detail("Venda"),
                user=user,
            ),
```

### Description

The same eight-argument `conflict_form_response` call, wrapped in the same
`rollback_integrity_error_response`, appears six times: `vendas.py:442-452` and `vendas.py:486-495`,
`compras.py:404-414`, `compras.py:426-436` and `compras.py:491-501`, and `veiculos.py:415-425`. Each
differs only in template name, `item_key`, `item`, the `write_conflict_detail` label, and whether
`dados=` is passed.

That last one is drift, not variation. `_criar_venda` (line 451) passes `dados=dados_form` so the
user's input is re-rendered into the conflict form; `_atualizar_venda` (above) omits it and never
computes `dados_form` at all. Both handlers render the same `_form_venda.html`.

### Why it matters

A user who hits a uniqueness conflict while *editing* a venda gets the form repopulated from the
persisted row, losing every unsaved change they had just typed — while the same conflict on *create*
preserves their input. This is user-visible data loss on an error path, which is exactly where users
are least willing to retype a long form. The six-way duplication is what let the two copies of one
behavior diverge unnoticed.

### Concrete fix

Give each entity module a `_conflito_<entidade>(request, session, user, *, item=None, dados=None)`
helper built from the existing `_erro_<entidade>` helper — same arguments, `write_conflict_detail`
for the message and 409 instead of 400 — and replace the six inline blocks with calls to it. Fix the
drift as part of the move by computing `dados_form = dict(form)` in `_atualizar_venda` and passing it
through, matching `_criar_venda`.

### Domain details

#### Consolidation details

- **Duplicate type:** Near duplication
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/vendas.py:440-453`,
  `bases/xtreme_system/api/routes/ui_routes/vendas.py:484-496`,
  `bases/xtreme_system/api/routes/ui_routes/vendas.py:393-404` (the `VendaErro` conflict branch),
  `bases/xtreme_system/api/routes/ui_routes/compras.py:404-414`,
  `bases/xtreme_system/api/routes/ui_routes/compras.py:426-436`,
  `bases/xtreme_system/api/routes/ui_routes/compras.py:485-503`,
  `bases/xtreme_system/api/routes/ui_routes/veiculos.py:413-425`. Consolidation targets: the existing
  `_erro_venda` (`vendas.py:340`), `_erro_compra` (`compras.py:333`), `_erro_veiculo`
  (`veiculos.py:349`).
- **Differences between copies:** template name and `item_key` per entity; `item=None` on create vs
  `item=obj` on update; the `write_conflict_detail` label (`"Venda"`, `"Compra"`, `"Cliente"`,
  `"Veículo"`); and the `dados=` argument, which is present at every site except
  `vendas.py:486-495`. The `compras.py:485-503` copy additionally wraps the call in an
  idempotency-key check that returns `_ok_compra` instead.
- **Behavior preservation:** the union wins — `dados=` should be passed everywhere, which
  intentionally changes `_atualizar_venda`'s conflict rendering to preserve user input. That is the
  defect being fixed, and it must be called out rather than treated as an incidental side effect.
  The `compras.py:485-503` idempotency branch must stay outside the shared helper.
- **Verification plan:** add a regression test that submits a venda edit whose new values collide on
  a unique constraint and asserts the returned form contains the submitted values, not the persisted
  ones. Existing conflict tests cover the remaining five sites and must pass unchanged.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Both venda handlers were read in one contiguous range, so the missing `dados=` is a direct
    observation, not a diff artifact.
  - The compra and veiculo copies were read verbatim and confirm the same eight-argument shape.
- **Weaknesses:**
  - Whether `conflict_form_response` falls back to reading `item` when `dados` is absent was not
    verified by reading `crud_ui/responses.py`; if it does, the data loss is real but the repopulated
    values come from the ORM object rather than being blank.
- **Suggested checks:**
  - Read `bases/xtreme_system/api/crud_ui/responses.py` around `conflict_form_response` to confirm
    exactly what the form renders when `dados` is `None`.

## imp-20260801-009 — `_atualizar_veiculo` rebuilds the error form inline instead of calling the `_erro_veiculo` helper defined 30 lines above

- **Impact:** Medium
- **Category:** Reimplemented helpers
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** routes, error-handling, helpers, veiculo, bypass
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
- **Related opportunities:** imp-20260801-007, imp-20260801-008, imp-20260801-012

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos.py:377` — `_atualizar_veiculo`

```python
    except (ValidationError, HTTPException) as exc:
        msg = (
            str(exc.detail)
            if isinstance(exc, HTTPException)
            else validation_error_detail(exc)
        )
        return templates.TemplateResponse(
            request,
            "_form_veiculo.html",
            {**_ctx_form_veiculo(session), "veiculo": obj, "user": user, "erro": msg},
            status_code=400,
        )
```

### Description

`_erro_veiculo` (`veiculos.py:349-362`) exists precisely to render `_form_veiculo.html` with an error
at status 400, going through the shared `error_response` helper. Twelve lines later,
`_atualizar_veiculo` builds that same response by hand with a raw `templates.TemplateResponse`, and
the same handler *does* call `_erro_veiculo` for its other error branch at line 397 ("Débitos
inválidos"). One handler therefore produces two structurally different renderings of the same error
screen.

The bypass is not gratuitous: the inline version passes `"veiculo": obj` so the form keeps the record
being edited, while `_erro_veiculo` hardcodes `item=None`. The helper is simply too narrow for the
update path.

### Why it matters

`error_response` is the shared wrapper that all other entity modules use, so it is where cross-cutting
concerns land — OOB swap markers, HTMX retarget headers, consistent context keys. The inline copy
receives none of them, which means a validation failure on veiculo update renders through a different
code path than every other validation failure in the application, and any future addition to
`error_response` will silently skip it.

### Concrete fix

Add an `item: veiculo.Veiculo | None = None` parameter to `_erro_veiculo`, pass it through to
`error_response` as `item=item` in place of the hardcoded `None`, and replace the inline
`TemplateResponse` at lines 383-388 with `return _erro_veiculo(request, session, user, msg, item=obj)`.
Existing callers keep the default and are unaffected.

### Domain details

#### Consolidation details

- **Duplicate type:** Reimplemented helper
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/veiculos.py:383-388` (the inline
  reimplementation). Consolidation target: `bases/xtreme_system/api/routes/ui_routes/veiculos.py:349-362`
  (`_erro_veiculo`), already used correctly at `veiculos.py:397`.
- **Differences between copies:** the inline version passes `"veiculo": obj` and builds the context
  dict directly; `_erro_veiculo` passes `item=None` through `error_response` with `item_key="veiculo"`.
  Both use `status_code=400` and the same template. Whatever context keys `error_response` adds beyond
  the four in the inline dict are absent from the inline path.
- **Behavior preservation:** the union wins — the helper gains the `item` parameter so the update path
  keeps rendering the edited record, and the update path gains whatever `error_response` contributes.
  If `error_response` emits additional markup, the rendered output changes; that convergence is the
  point of the fix and must be confirmed against a snapshot rather than assumed invisible.
- **Verification plan:** capture the rendered HTML for a failing veiculo update before the change,
  apply it, and diff. Any difference must be attributable to `error_response`'s shared additions.
  Then assert the form still shows the edited veiculo's values, which is the behavior the inline
  version was protecting.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The inline block, the `_erro_veiculo` helper, and the correct call at line 397 were all read in
    one contiguous range, so the bypass and its reason are directly observed.
- **Weaknesses:**
  - `error_response` itself was not read, so the claim that it adds context beyond the inline dict is
    reasoned from its role as the shared wrapper rather than verified. The consolidation is still
    correct, but the "silently skips future additions" argument rests on that.
- **Suggested checks:**
  - Read `bases/xtreme_system/api/crud_ui/responses.py` `error_response` and diff its emitted context
    against the four keys the inline version supplies.

## imp-20260801-010 — `ui_investidor_criar` and `ui_investidor_atualizar` duplicate the whole validate-write-conflict body

- **Impact:** Medium
- **Category:** Near duplication
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** routes, investidor, crud, conflict, copy-paste
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/investidores.py`
- **Related opportunities:** imp-20260801-008

### Location

`bases/xtreme_system/api/routes/ui_routes/investidores.py:260` — `ui_investidor_atualizar`

```python
    if not nome:
        return templates.TemplateResponse(
            request,
            "_form_simples.html",
            _form_ctx_investidor(obj, "Nome obrigatório"),
            status_code=400,
        )
    try:
        investidor.update(session, obj, investidor.InvestidorUpdate(nome=nome), user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
```

### Description

`ui_investidor_criar` (line 192) and `ui_investidor_atualizar` (line 254) share the same body: strip
`nome` from the form, return a 400 `_form_simples.html` when empty, call the create/update, catch
`IntegrityError` and return a 409 `_form_simples.html` through
`rollback_integrity_error_response`, then return `success_response` with
`_ctx_investidores(session)`. The only differences are `investidor.create` vs `investidor.update`,
the `None` vs `obj` passed to `_form_ctx_investidor`, and an extra initial-aporte block that only
the create path runs.

### Why it matters

Investidor is the only entity whose create and update handlers are written out by hand rather than
generated through `crud_ui`, so it is the one place where a change to the shared conflict or
validation behavior has to be applied twice and where an inconsistency between create and update
will not be caught by the factory's tests. The 400/409 status split and the rollback path are both
duplicated, and both are exactly the kind of detail that drifts (see imp-20260801-008 for the same
pattern drifting in the venda routes).

### Concrete fix

Extract a `_validar_nome_investidor(request, obj, form) -> str | HTMLResponse` helper for the
empty-name branch and a `_conflito_investidor(request, obj) -> HTMLResponse` helper for the 409
branch, and have both handlers call them. That removes the duplicated validation and conflict bodies
while leaving the genuinely create-only aporte block where it is.

### Domain details

#### Consolidation details

- **Duplicate type:** Near duplication
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/investidores.py:192-249`
  (`ui_investidor_criar`) and `bases/xtreme_system/api/routes/ui_routes/investidores.py:254-285`
  (`ui_investidor_atualizar`). Both render
  `bases/xtreme_system/api/templates/_form_simples.html` via `_form_ctx_investidor`
  (`investidores.py:120`).
- **Differences between copies:** `investidor.create` + `InvestidorCreate` vs `investidor.update` +
  `InvestidorUpdate`; `_form_ctx_investidor(None, ...)` vs `_form_ctx_investidor(obj, ...)`; the
  create path additionally parses `valor_investido`, builds an optional initial
  `LancamentoInvestimentoCreate` aporte, and has its own `Decimal`/`InvalidOperation` error branch
  with a `session.rollback()` and a `logger.warning`. The update path has no aporte handling.
- **Behavior preservation:** both behaviors are preserved as-is; only the shared empty-name and
  conflict branches move into helpers. The create-only aporte block, including its distinct
  `session.rollback()` path, stays in `ui_investidor_criar` and must not be pulled into the shared
  helper.
- **Verification plan:** assert both handlers still return 400 with "Nome obrigatório" for an empty
  name and 409 with the conflict detail for a duplicate name, and that creating an investidor with a
  positive `valor_investido` still produces exactly one aporte lancamento.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Both handlers were read in one contiguous range, so the shared and divergent parts are directly
    observed.
- **Weaknesses:**
  - The first few lines of `ui_investidor_criar` (its signature and the start of the empty-name
    check, lines 192-199) fell just above the range read, so the create path's form-reading is
    matched to the update path's by structure rather than verbatim comparison.
- **Suggested checks:**
  - Read `investidores.py:192-200` to confirm the create handler reads `nome` identically
    (`str(form.get("nome") or "").strip()`) before extracting the shared validation helper.

## imp-20260801-011 — Nine `_linhas_*.html` fragments repeat the same tbody / OOB / for-else / pagination scaffolding

- **Impact:** Medium
- **Category:** Template consolidation
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** templates, jinja, htmx, macros, list-rendering
- **Files affected:** `bases/xtreme_system/api/templates/_linhas_vendas.html`, `bases/xtreme_system/api/templates/_linhas_compras.html`, `bases/xtreme_system/api/templates/_linhas_clientes.html`, `bases/xtreme_system/api/templates/_linhas_veiculos.html`, `bases/xtreme_system/api/templates/_linhas_custos_veiculos.html`, `bases/xtreme_system/api/templates/_linhas_lancamentos.html`, `bases/xtreme_system/api/templates/_linhas_perfis.html`, `bases/xtreme_system/api/templates/_linhas_usuarios.html`, `bases/xtreme_system/api/templates/_linhas_investidores.html`, `bases/xtreme_system/api/templates/_macros.html`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/templates/_linhas_compras.html:1` — list fragment

```jinja
{% import "_macros.html" as ui %}
<tbody id="linhas"{% if oob %} hx-swap-oob="true"{% endif %}>
  {% for c in compras %}
    {% include "_row_compra.html" %}
  {% else %}
  <tr class="empty-row"><td colspan="9">
    {% call ui.empty("inbox", "Nenhuma compra encontrada", "Cadastre uma compra para começar.") %}{% endcall %}
  </td></tr>
  {% endfor %}
</tbody>
{% if oob %}{{ ui.paginacao(request.url.path, qs_base, "#linhas", page_start, page_end, page_count, limit, offset_anterior, offset_proximo, tem_anterior, tem_proximo, oob=True) }}{% endif %}
```

### Description

Nine list fragments share one structure: `{% import %}`, a `<tbody id="linhas">` with a conditional
`hx-swap-oob`, a `for … include row … else … ui.empty(...)` block, and a conditional OOB
`ui.paginacao(...)` call with eleven positional arguments. The per-list variation is small and
regular: the loop variable and collection, the row partial, the empty-state icon/title/text, the
`colspan`, and which optional trailing blocks (`_stats_*.html`, an `msg` OOB div) are appended.

`_linhas_simples.html` already demonstrates the generic form for the `crud_ui.simple` entities; the
nine hand-written fragments are the same idea, unfactored.

### Why it matters

The eleven-argument positional `ui.paginacao` call is copied verbatim into every paginated fragment.
Adding or reordering a pagination argument means editing every copy correctly, and a positional
mismatch produces silently wrong pagination rather than a template error. The same applies to the
`hx-swap-oob` contract: the OOB refresh behavior of every list is re-declared nine times instead of
being defined once.

### Concrete fix

Add a `ui.linhas(...)` macro to `_macros.html` taking the collection, the row template name, the
empty-state triple, the colspan, and a pagination context object, using `{% call %}` for the row
body. Convert the fragments to call it, keeping the entity-specific trailing blocks
(`_stats_veiculos.html`, `_stats_clientes.html`, the `msg` div) outside the macro. As a smaller
first step with most of the benefit, change `ui.paginacao` to accept a single context dict instead of
eleven positional arguments — the route layer already assembles those values together.

### Domain details

#### Consolidation details

- **Duplicate type:** Template consolidation
- **All sites:** `bases/xtreme_system/api/templates/_linhas_vendas.html`,
  `_linhas_compras.html`, `_linhas_clientes.html`, `_linhas_veiculos.html`,
  `_linhas_custos_veiculos.html`, `_linhas_lancamentos.html`, `_linhas_perfis.html`,
  `_linhas_usuarios.html`, `_linhas_investidores.html` — all in
  `bases/xtreme_system/api/templates/`. Existing generic form: `_linhas_simples.html`. Consolidation
  target: `bases/xtreme_system/api/templates/_macros.html` (`paginacao` at line 259, `empty` at
  line 158).
- **Differences between copies:** loop variable and collection name; row partial; empty-state icon,
  title and text; `colspan`, which is a literal in most copies, a `{% if %}` expression over
  `pode_operacao` in `_linhas_vendas.html`, and `columns | length + 1` in `_linhas_clientes.html`.
  `_linhas_veiculos.html` has no pagination block and appends `_stats_veiculos.html` plus an `msg`
  OOB div; `_linhas_clientes.html` appends `_stats_clientes.html` in addition to pagination.
- **Behavior preservation:** every difference above is intentional configuration and must survive as
  a macro parameter. In particular, the absent pagination block in `_linhas_veiculos.html` is
  correct, not drift — `veiculos.html` has no `ui.paginacao` call at all, unlike `vendas.html:85`,
  `compras.html:83` and `clientes.html:69` — so pagination must stay opt-in rather than being
  normalized on.
- **Verification plan:** render each of the nine lists before and after with a populated collection
  and with an empty one, and diff the HTML. The output must be byte-identical; this refactor has no
  intended behavior change, so any diff is a defect.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Four fragments were read verbatim and the pagination call is character-identical across the three
    paginated ones.
  - The apparent pagination "drift" in `_linhas_veiculos.html` was checked against the page templates
    and confirmed intentional rather than reported as a bug.
- **Weaknesses:**
  - Five of the nine fragments (`_linhas_lancamentos`, `_linhas_perfis`, `_linhas_usuarios`,
    `_linhas_investidores`, `_linhas_custos_veiculos`) were identified by name and size only, not
    read, so their conformance to the shape is inferred from the four that were.
  - `_linhas_usuarios.html` (46 lines) and `_linhas_investidores.html` (40 lines) are notably larger
    than the others and may inline their rows rather than including a `_row_*.html` partial, which
    would make them poor fits for the macro.
- **Suggested checks:**
  - Read the five unread fragments and confirm they follow the `include _row_*.html` shape before
    committing to a single macro; those that inline rows may be better left alone.

## imp-20260801-012 — The `_ok_*` / `_erro_*` list-and-form response helpers are the same pair rewritten per entity

- **Impact:** Medium
- **Category:** Near duplication
- **Estimated effort:** Medium
- **Priority:** low
- **Risk level:** medium
- **Tags:** routes, responses, htmx, helpers, boilerplate
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`
- **Related opportunities:** imp-20260801-008

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:340` — `_erro_venda`

```python
def _erro_venda(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    msg: str,
    venda_obj: venda.Venda | None = None,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        "_form_venda.html",
```

### Description

Four entity modules define the same helper pair over `ok_response` / `error_response`:
`_ok_venda`/`_erro_venda` (`vendas.py:320`, `:340`), `_ok_compra`/`_erro_compra`
(`compras.py:354`, `:333`), `_ok_veiculo`/`_erro_veiculo` (`veiculos.py:334`, `:349`), and
`_ok_lancamentos`/`_erro_lancamento` (`lancamentos.py:55`, `:72`). Each `_erro_*` passes the same
eight keyword arguments with only the template name, `item_key`, and context builder changing; each
`_ok_*` fetches the list and passes template name, `list_key`, `lista`, and `ctx_list`.

The `_erro_lancamento` copy has additionally absorbed the exception-to-message conversion that
imp-20260801-007 covers, so it takes an `exc` where the others take a `msg`.

### Why it matters

This is the seam where per-entity response behavior drifts — the missing `dados=` in
imp-20260801-008 and the bypassed helper in imp-20260801-009 are both symptoms of these
four families being maintained independently. Adding a new UI entity means writing the pair again by
hand, and each new copy starts from whichever existing copy was pasted.

### Concrete fix

Add a small `EntityResponders` dataclass (or a `make_responders(...)` factory) in
`crud_ui/responses.py` that takes the template names, `item_key`, `list_key`, and the two context
builders, and returns bound `ok` and `erro` callables. Each entity module then declares one
`_RESPONDERS = make_responders(...)` and calls `_RESPONDERS.erro(...)` / `_RESPONDERS.ok(...)`. This
is worth doing after imp-20260801-008 and imp-20260801-009, so the copies are already converged when
they are folded together.

### Domain details

#### Consolidation details

- **Duplicate type:** Near duplication
- **All sites:** `bases/xtreme_system/api/routes/ui_routes/vendas.py:320-337` and `:340-359`,
  `bases/xtreme_system/api/routes/ui_routes/compras.py:333-351` and `:354-364`,
  `bases/xtreme_system/api/routes/ui_routes/veiculos.py:334-346` and `:349-362`,
  `bases/xtreme_system/api/routes/ui_routes/lancamentos.py:55-70` and `:72-95`. Consolidation
  target: `bases/xtreme_system/api/crud_ui/responses.py` (`ok_response`, `error_response`).
- **Differences between copies:** `_ok_venda` takes `limit`/`offset` and calls
  `venda.list_all(session, limit=limit, offset=offset)`; `_ok_compra` takes neither and passes
  `ctx_list={}`; `_ok_veiculo` delegates to `_listar_veiculos(session)`; `_ok_lancamentos` takes an
  `investidor_id` and derives `ctx_list` by filtering its own context dict. `_erro_venda` and
  `_erro_compra` accept `dados`; `_erro_veiculo` does not; `_erro_lancamento` takes an `exc` instead
  of a `msg`, omits `user`, and builds `ctx_form` inline rather than calling a `_ctx_form_*`
  function.
- **Behavior preservation:** every listed difference must remain expressible — pagination arguments,
  the `dados` parameter, and the per-entity `ctx_list` builder all become factory parameters or
  call-site keyword arguments. `_erro_lancamento`'s exception handling should move to the shared
  helper from imp-20260801-007 first, so the four `erro` signatures converge before being unified;
  otherwise the factory has to carry the divergence.
- **Verification plan:** the four entity modules' route tests all assert on rendered form and list
  output; run them unchanged. Because this is pure plumbing, any change in rendered HTML is a defect.
- **Sequencing:** apply imp-20260801-007, imp-20260801-008, and imp-20260801-009 first. Unifying the
  families while they still disagree would bake the current divergences into the shared factory.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** No
- **Strengths:**
  - All eight helpers were located by signature sweep and six of them read verbatim, so the shared
    shape and the specific divergences are observed, not assumed.
- **Weaknesses:**
  - This is the weakest finding in the set. The four pairs are already thin wrappers over genuinely
    shared helpers, so the remaining duplication is the per-entity configuration itself — which a
    factory relocates rather than eliminates. The value is in giving drift one place to be caught,
    not in line count, and that value is real but modest.
  - The risk level is medium despite the low complexity because four independently-evolved
    signatures must be reconciled, and the reconciliation is where behavior can silently change.
- **Suggested checks:**
  - Re-evaluate whether this is worth doing at all after imp-20260801-008 and imp-20260801-009 land.
    If those two converge the copies, the remaining duplication may not justify a new abstraction.

## Discarded candidates

### `search_query` / `columns_map` repeated across five component cores

`venda/core.py:405`, `compra/core.py:206`, `veiculo/core.py:281`, `custo_veiculo/core.py:111`, and
`cliente/core.py:380` each build a `columns_map` dict and call `apply_text_search`. This looked like
duplication but is not: the shared algorithm is already factored into `apply_text_search`, and what
remains at each site is a per-entity column mapping — configuration data, not repeated logic. There
is no behavior to unify and no drift risk, since each map is independently correct for its own model.

### `_ctx_form_*` and `_ctx_lista_*` context builders across entity modules

Nine modules define `_ctx_form_<entidade>` / `_ctx_lista_<entidade>` functions with similar names and
return types. Their bodies are entity-specific — different queries, different template variables —
so the only shared element is the naming convention. Consolidating would mean inventing an
abstraction over genuinely different data.

### `_row_*.html` table row partials

`_row_venda.html`, `_row_veiculo.html`, `_row_compra.html`, `_row_cliente.html` and
`_row_custo_veiculo.html` share the `{% if pode_ver_campo(user, <pagina>, <campo>) %}<td …>` idiom
per cell, but each row's columns, formatting, and badge logic are entirely different. A diff of
`_row_compra.html` against `_row_veiculo.html` shares no cell. This is a consistent idiom, not
duplication; the `pode_ver_campo` wrapper is already the shared mechanism.

### `crud_ui/routes.py` register_* route functions

`register_list_route`, `register_create_route`, `register_update_route`, `register_delete_route`,
`register_edit_route`, `register_export_route` and `register_new_route` follow the same shape by
design — this file *is* the consolidation target for CRUD UI duplication, and each function handles a
distinct HTTP verb and response contract. Merging them would reduce clarity without removing a
duplicated rule.

### `fechamento_venda.preview` and `fechamento_venda.confirmar` both calling `_calcular`

Both call `_calcular(session, venda_obj)` and use the result, which initially looked like a
duplicated calculation path. On reading, `preview` is read-only and reports eligibility while
`confirmar` persists, audits, and distributes profit; the shared calculation is already extracted
into `_calcular`. This is correct reuse, not duplication.
