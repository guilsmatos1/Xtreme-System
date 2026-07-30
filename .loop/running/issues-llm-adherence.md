# Improvement opportunities

- **Generated:** 2026-07-30T17:12:55-03:00
- **Total:** 12

## imp-20260730-001 — Extract a venda creation workflow: the HTMX route owns DB writes, PDF filesystem I/O and WhatsApp notification

- **Impact:** High
- **Category:** Boundary clarity
- **Estimated effort:** High
- **Priority:** high
- **Risk level:** medium
- **Tags:** workflow-extraction, side-effects, filesystem, route-boundary, testability, venda
- **Files affected:**
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `components/xtreme_system/documento_contrato_venda/core.py`
  - `components/xtreme_system/whatsapp/core.py`
  - `components/xtreme_system/venda/core.py`
  - `bases/xtreme_system/api/routes/ui_routes/common.py`
- **Related opportunities:** imp-20260730-003, imp-20260730-004, imp-20260730-008, imp-20260730-011

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:445-455` — `_criar_venda_com_hooks`

```python
    return _ok_venda(request, session, user, limit=limit, offset=offset)


def _criar_venda_com_hooks(
    session: Session, data: venda.VendaCreate, actor_id: int | None
) -> venda.Venda:
    obj = venda.create(session, data, actor_id)
    _persistir_contrato_venda(session, obj, actor_id)
    whatsapp.notificar_venda(session, obj)
    return obj
```

### Description

A single route function (`_criar_venda`, `vendas.py:345-407`) chains eight unrelated stages: form
parsing, nested-client resolution and creation, profile-based field stripping, Pydantic validation,
cross-entity FK/availability validation, the sale write, atomic PDF contract generation, a
rollback-compensation hook, and an outbound WhatsApp notification — then renders an HTMX partial.

`_persistir_contrato_venda` (`vendas.py:302-342`) performs the filesystem work inline
(`tmp_path.write_bytes` → `os.fsync` → `os.replace` at `vendas.py:319-326`) and hard-codes the upload
URL convention `f"/static/uploads/vendas/{obj.id}/contrato/{filename}"` (`vendas.py:339`), duplicating
the directory logic that already lives in `common._uploads_contrato_venda_dir`
(`common.py:95-96`).

### Why it matters

There is no way to exercise "create a sale" without a `Request`, a template environment, a
filesystem, and the WhatsApp code path. An LLM asked to change one rule (e.g. "don't generate the
contract for cancelled sales") must read and hold all 110 lines and correctly guess which of the
three `try` blocks owns which failure. The compensating-rollback pairing between
`register_post_rollback` (`vendas.py:334`) and `safe_write` (`vendas.py:394`) is invisible from any
single stage — it is itself evidence that the mixing already caused a correctness problem someone
had to patch.

### Concrete fix

Add `components/xtreme_system/venda/workflow.py` exposing
`criar_venda(session, data, *, actor_id, contrato: ContratoWriter, notificador: Notificador) -> Venda`,
with `ContratoWriter` and `Notificador` as Protocols. Move `_persistir_contrato_venda`'s PDF and
filesystem code into `documento_contrato_venda`, which already owns `gerar_pdf`. The route keeps only:
parse form → call workflow → map exception to HTMX response.

### Potential savings

`_criar_venda` drops from ~62 lines to ~15. The contract and notification rules become unit-testable
with a fake writer instead of the current filesystem-touching integration tests.

### Domain details

#### Modularity details

- **LLM risk:** An agent editing sale-creation rules must currently reason about filesystem atomicity
  and HTTP side effects it did not intend to touch; a partial edit silently breaks contract cleanup on
  rollback.
- **Suggested interface:**
  `criar_venda(session, data: VendaCreate, *, actor_id: int | None, contrato: ContratoWriter, notificador: Notificador) -> Venda`
- **New structure:** `components/xtreme_system/venda/workflow.py` for orchestration; contract PDF
  persistence moved into `documento_contrato_venda/core.py`; the route becomes a thin adapter.
- **Tests:** `tests/test_venda_workflow.py` with a fake `ContratoWriter` and fake `Notificador`
  covering success, contract-write failure rolling back the sale, and notification failure not rolling
  back.
- **Success metric:** `_criar_venda` under 20 lines; zero `os.` or `Path` calls remaining in
  `vendas.py`.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - The three concerns (DB, filesystem, HTTP notification) are objectively present in one call chain.
  - The rollback compensation is concrete evidence that the mixing already caused a correctness
    problem someone had to patch.
- **Weaknesses:**
  - The suggested Protocol seams are one of several valid designs.
  - The existing `register_post_rollback` mechanism may already be considered "good enough" by the
    maintainer.
- **Suggested checks:**
  - Confirm whether any non-HTTP caller (CLI, job, import script) needs sale creation today, which
    would raise the priority of the extraction.

## imp-20260730-002 — query_list picks among five listing strategies from optional ListingSpec callables with no declared contract

- **Impact:** High
- **Category:** Contract strength
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** implicit-contract, strategy-dispatch, pagination, sorting, performance, listing
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/query.py`
  - `bases/xtreme_system/api/crud_types.py`
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/routes/ui_routes/*.py` (every module building a `ListingSpec`)
- **Related opportunities:** imp-20260730-007, imp-20260730-009

### Location

`bases/xtreme_system/api/crud_ui/query.py:181-191` — `query_list`

```python
    else:
        callable_list = listing.list_func or module.list_all
        if not sort or sort not in listing.sort_fields:
            return _paginated_list(callable_list, session, limit, offset)
        result = _page_list(
            sorted_list(
                _paginated_list(callable_list, session, None, 0),
                sort,
                order,
                listing.sort_fields,
            ),
```

### Description

`ListingSpec` (`crud_types.py:139-149`) exposes five independent optional fields — `list_func`,
`search_func`, `query_func`, `search_query_func`, `searchable` — plus `paginated`, and `query_list`
(`query.py:126-195`) resolves them through a cascade of `if` branches whose precedence is written
nowhere.

The branches are not equivalent. The first two push sorting and pagination into SQL
(`query.py:137-157`); the last three sort in Python and slice. The final branch, quoted above, calls
`_paginated_list(callable_list, session, None, 0)` — it loads **the entire table** into memory before
slicing whenever a sort field is active.

### Why it matters

A caller configuring a new listing cannot tell from `ListingSpec`'s type which combination it is
opting into, nor that supplying `query_func` silently disables the Python `sort_fields` lambdas in
favour of the `sql` expressions. An LLM adding pagination to a resource will pick a field almost at
random and get either a full table scan or a sort that silently changes ordering semantics —
`sort_key` lowercases strings (`query.py:21-27`) while SQL `ORDER BY` does not
(`query.py:87-92`).

### Concrete fix

Replace the optional-field bag with an explicit tagged union in `crud_types.py`:
`ListingStrategy = SqlListing(query_func, search_query_func) | PythonListing(list_func, search_func)`,
and have `query_list` dispatch on the variant. Keep `sort_fields` and `default_sort` shared. The
invalid combinations then stop being representable.

### Potential savings

Removes five implicit precedence rules and eliminates the accidental full-table load in the last
branch by making "Python sort requires loading everything" an explicit, named choice.

### Domain details

#### Modularity details

- **LLM risk:** Choosing the wrong `ListingSpec` field produces working-but-wrong behaviour (different
  sort order, or a full table load) that no type checker or test failure surfaces.
- **Suggested interface:** `query_list(session, module, *, listing: ListingSpec[EntityT], state: ListState)`
  unchanged, with `ListingSpec.strategy: SqlListing | PythonListing`.
- **New structure:** `bases/xtreme_system/api/crud_ui/listing_strategy.py` holding the two variants and
  their resolution; `query.py` keeps only the sort and page primitives.
- **Tests:** Extend `tests/test_route_factories_ui.py` — one test per variant asserting SQL vs Python
  ordering of a mixed-case field, and one asserting the paginated path issues a `LIMIT`.
- **Success metric:** `query_list` has at most two top-level branches; `ListingSpec` has no
  mutually-exclusive optional fields.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The branch cascade and the divergent SQL-vs-Python sort semantics are directly readable in the
    quoted code.
  - `tests/test_route_factories_ui.py` already exists as a safety net for the refactor.
- **Weaknesses:**
  - A tagged union is a moderately invasive change across roughly ten call sites.
  - A cheaper fix — documenting precedence in the `ListingSpec` docstring plus a `__post_init__`
    validation of illegal combinations — would capture much of the value at lower risk.
- **Suggested checks:**
  - Measure the row count of the largest listed table to quantify the full-table-load branch's real
    cost before choosing between the cheap and the structural fix.

## imp-20260730-003 — Profile field-stripping is applied on update but not on create in the CRUD UI factory

- **Impact:** High
- **Category:** Boundary clarity
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** permissions, form-pipeline, consistency, security-adjacent, crud-factory
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/compras.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
  - `components/xtreme_system/perfil/core.py`
- **Related opportunities:** imp-20260730-001, imp-20260730-007, imp-20260730-009, imp-20260730-012

### Location

`bases/xtreme_system/api/crud_ui/routes.py:637-648` — `register_update_route._atualizar`

```python
    @app.post(f"{prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        form_data = await request.form()
        dados_form = parse_form(form_data)
        perfil.filtrar_campos_form_ocultos(user, pagina, dados_form)
        try:
```

### Description

`register_update_route` accepts a `pagina` parameter and strips profile-hidden fields before
validation (line 647). `register_create_route` takes no `pagina` and validates the raw form —
`create_schema.model_validate(dados_form)` at `routes.py:554` receives unfiltered data.

The manual routes compensate inconsistently: `vendas.py:377` and `vendas.py:424` filter on both create
and update, `compras.py:393` filters on create, `veiculos.py:366` filters once. The same rule is
implemented at five call sites in three different shapes, each repeating the page name as a bare
string literal.

### Why it matters

The rule "a profile that cannot see a field cannot write it" has no single owner. A route added by an
LLM through the factory inherits the protection on edit and silently loses it on create. Because
`filtrar_campos_form_ocultos` mutates in place *and* returns the dict, both call styles compile, so
nothing flags the omission.

### Concrete fix

Introduce one form pipeline used by every write path —
`prepare_form_payload(user, pagina, form, parse_form) -> dict[str, Any]` in `crud_ui/` — and have
`register_create_route` take `pagina` exactly as `register_update_route` does. Replace the five ad-hoc
call sites with it.

### Potential savings

One rule in one place instead of five, and removal of a create-path permission gap.

### Domain details

#### Modularity details

- **LLM risk:** An agent adding a resource through the factory reasonably assumes the factory enforces
  field permissions uniformly; the create path silently does not.
- **Suggested interface:**
  `prepare_form_payload(user: Usuario, pagina: str | None, form: FormData, parse_form: ParseForm) -> dict[str, Any]`
- **New structure:** `bases/xtreme_system/api/crud_ui/form_pipeline.py`; both create and update in
  `routes.py` call it.
- **Tests:** One parametrised test over (create, update) × (factory route, manual route) asserting a
  hidden field submitted in the form never reaches the persisted entity.
- **Success metric:** `filtrar_campos_form_ocultos` has exactly one caller.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** Yes
- **Strengths:**
  - The asymmetry between the two registrars is unambiguous in the code.
  - The manual routes' compensating calls are direct evidence that the factory's create path is known
    to be insufficient.
- **Weaknesses:**
  - I did not confirm whether every factory-registered create route is additionally guarded by a
    `cadastrar_dep` that makes the field-level gap unreachable in practice; if so, the impact is
    maintainability rather than exposure.
- **Suggested checks:**
  - Submit a profile-hidden field to a factory-registered create endpoint as a non-admin user and
    confirm whether it is persisted.

## imp-20260730-004 — ui_routes/common.py is a six-responsibility grab-bag imported by nearly every route module

- **Impact:** High
- **Category:** Coupling and import shape
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** god-module, low-cohesion, utils-dump, duplication, import-shape
- **Files affected:**
  - `bases/xtreme_system/api/routes/ui_routes/common.py`
  - `bases/xtreme_system/api/routes/ui_routes/compras.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py`
  - `bases/xtreme_system/api/routes/ui_routes/auditoria.py`
  - `bases/xtreme_system/api/deps.py`
- **Related opportunities:** imp-20260730-001, imp-20260730-006, imp-20260730-010

### Location

`bases/xtreme_system/api/routes/ui_routes/common.py:216-227` — `criar_aninhado_ou_resposta_conflito`

```python
def criar_aninhado_ou_resposta_conflito[EntityT, CreateDataT](
    session: Session,
    data: CreateDataT | None,
    create_fn: Callable[[Session, CreateDataT, int | None], EntityT],
    actor_id: int | None,
    build_conflict_response: Callable[[], HTMLResponse],
) -> tuple[EntityT | None, HTMLResponse | None]:
    if data is None:
        return None, None
    try:
        return create_fn(session, data, actor_id), None
    except IntegrityError:
```

### Description

One 236-line module holds six unrelated concerns: report date-range filter schemas
(`PeriodoFiltro`, `common.py:42-72`), the upload directory convention (`common.py:75-96`), magic-byte
file validation (`_MAGIC_BYTES` and `validar_uploads`, `common.py:99-147`), a Jinja template helper
(`arquivo_disponivel`, `common.py:154-160`), HTML-form entity resolution (`resolver_cliente`,
`common.py:168-213`), and session transaction control (the quoted helper plus
`rollback_se_criou_aninhados`, `common.py:216-235`). They share nothing but the name "common".

Compounding it, `resolver_cliente` has a near-twin — `_resolver_veiculo` at `compras.py:243-284` —
with an identical shape (`tuple[Entity | None, CreateSchema | None, str | None]`). One lives in the
shared module, one is private to a route file, and the two have drifted: the client version takes
keyword-configurable error messages, the vehicle version hard-codes them.

### Why it matters

Every route module imports this file, so any edit has repo-wide blast radius and every LLM working on
any route pulls all six concerns into context. There is no signal about where a new helper belongs,
which is exactly how `_resolver_veiculo` ended up in the wrong place.

### Concrete fix

Split by concern into `ui_routes/filters.py` (`PeriodoFiltro`, `DataFiltro`, `IdFiltro`,
`TextoFiltro`), `ui_routes/uploads.py` (directory helpers, `validar_uploads`, `arquivo_disponivel`),
`ui_routes/nested_create.py` (`criar_aninhado_ou_resposta_conflito`, `rollback_se_criou_aninhados`),
and a generic `resolve_or_create(session, form, spec)` covering both client and vehicle resolution.
Delete `common.py`.

### Potential savings

Route modules import one or two focused modules instead of one 236-line catch-all; removes roughly 40
lines of duplicated resolution logic.

### Domain details

#### Modularity details

- **LLM risk:** Broad-blast-radius module. An agent editing upload validation risks touching report
  filters in the same file, and cannot tell where new helpers belong.
- **Suggested interface:**
  `resolve_or_create[E, C](session, form, spec: ResolveSpec[E, C]) -> tuple[E | None, C | None, str | None]`
- **New structure:** `ui_routes/filters.py`, `ui_routes/uploads.py`, `ui_routes/nested_create.py`,
  `ui_routes/resolve.py`.
- **Tests:** Move the existing `common`-facing assertions in `tests/test_uploads.py` to target
  `ui_routes/uploads.py`; add a `resolve_or_create` test covering select-existing, create-new, and
  duplicate-document paths for both client and vehicle.
- **Success metric:** No module named `common.py` remains; each new module has one reason to change.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The six concerns are visible in the file's own section comments.
  - The `resolver_cliente` / `_resolver_veiculo` twin is concrete duplication with observable drift.
- **Weaknesses:**
  - A pure file split with no behaviour change is low-value on its own; the value comes from doing it
    together with the `resolve_or_create` unification.
  - Generalising the two resolvers may be over-abstraction if no third case ever appears.
- **Suggested checks:**
  - Check whether a third entity (investidor, usuario) is likely to need select-or-create in the near
    term, which decides whether the generic `resolve_or_create` is justified.

## imp-20260730-005 — crud and upload_file form a component import cycle that the import-linter contract does not cover

- **Impact:** High
- **Category:** Coupling and import shape
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** circular-import, layering, import-linter, polylith, dependency-inversion
- **Files affected:**
  - `components/xtreme_system/crud/attachment.py`
  - `components/xtreme_system/upload_file/core.py`
  - `components/xtreme_system/upload_file/authorization.py`
  - `components/xtreme_system/imagem_veiculo/core.py`
  - `pyproject.toml`
  - `ARCHITECTURE.md`
- **Related opportunities:** imp-20260730-010

### Location

`components/xtreme_system/upload_file/authorization.py:8-17` — module imports

```python
from xtreme_system.database.core import Base
from xtreme_system.documento_contrato_venda.core import DocumentoContratoVenda
from xtreme_system.documento_procuracao.core import DocumentoProcuracao
from xtreme_system.documento_veiculo.core import DocumentoVeiculo
from xtreme_system.empresa.core import EmpresaConfig
from xtreme_system.imagem_comprovante_compra.core import ImagemComprovanteCompra
from xtreme_system.imagem_documento_cliente.core import ImagemDocumentoCliente
from xtreme_system.imagem_veiculo.core import ImagemVeiculo
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
```

The edge that closes the cycle is `crud/attachment.py:9-10`:
`from xtreme_system.crud import core as crud` followed by
`from xtreme_system.upload_file.core import schedule_uploaded_file_delete`.

### Description

`crud` is the lowest-level shared component — imported by 14 others — yet `crud/attachment.py` imports
upward into `upload_file`, and `upload_file/authorization.py:9-17` imports eight sibling components
back down, including `imagem_veiculo`. `imagem_veiculo/core.py:7` imports `crud.attachment`, closing a
`crud → upload_file → imagem_veiculo → crud` cycle at package level.

The only import-linter contract (`pyproject.toml:167-172`) forbids components importing
`xtreme_system.api`; nothing forbids component-to-component cycles, so this is invisible to CI.
`ARCHITECTURE.md` asserts "Não há acoplamento direto entre componentes", which the actual graph
contradicts: `venda` imports `cliente`, `veiculo`, `usuario`, `documento_contrato_venda` and
`imagem_comprovante_venda`; `fechamento_venda` imports eight components.

### Why it matters

An LLM asked to change `crud` cannot bound the change: the cycle means `crud`'s behaviour is entangled
with the entire attachment and authorization surface. Import order becomes load-bearing, and the
documented architecture is actively misleading as context — an agent reading `ARCHITECTURE.md` will
make wrong assumptions about safe edit boundaries.

### Concrete fix

Invert the `crud → upload_file` edge: `crud/attachment.py` should accept a delete-scheduling callback
(or a `FileLifecycle` Protocol) supplied at registration time rather than importing
`upload_file.core`. Separately, move `upload_file/authorization.py`'s per-entity table knowledge into
a registry the owning components populate, so `upload_file` stops importing eight siblings. Then add a
layered import-linter contract (`database < crud < entity components < aggregate components`) so CI
enforces it.

### Potential savings

Removes the cycle, makes `crud` editable in isolation, and lets CI catch the next regression instead
of a reviewer.

### Domain details

#### Modularity details

- **LLM risk:** The stated architecture ("no direct coupling between components") contradicts the real
  graph, so an agent using `ARCHITECTURE.md` as context will misjudge safe edit boundaries.
- **Suggested interface:**
  `class FileLifecycle(Protocol): def schedule_delete(self, url: str) -> None: ...`, injected into
  `attachment.register(...)`.
- **New structure:** `crud/attachment.py` becomes dependency-free of `upload_file`;
  `upload_file/authorization.py` reads a registry instead of importing entity modules.
- **Tests:** A CI step running `lint-imports` with the new layered contract, plus a unit test for
  `attachment` using a stub `FileLifecycle`.
- **Success metric:** `lint-imports` passes with a layered contract; no component imports a component
  above it.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** Yes
- **Strengths:**
  - The three import statements closing the cycle are quoted verbatim from the current files.
  - The absence of a layering contract in `pyproject.toml` is verifiable in a single grep.
- **Weaknesses:**
  - Because `upload_file/__init__.py` is empty and `crud/attachment.py` imports only
    `upload_file.core` (which imports nothing but `database`), Python never actually raises a
    circular-import error at runtime — this is a design-level cycle in the package graph, not a live
    import failure.
  - I did not run `lint-imports` to confirm how a layering contract would report it.
- **Suggested checks:**
  - Add a draft layered contract to `pyproject.toml` and run `lint-imports` to get the exact set of
    violations before committing to the inversion.

## imp-20260730-006 — Underscore-prefixed helpers are the de facto public API of deps.py and common.py

- **Impact:** Medium
- **Category:** Encapsulation
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** encapsulation, naming, public-api, llm-signal, refactor-safety
- **Files affected:**
  - `bases/xtreme_system/api/deps.py`
  - `bases/xtreme_system/api/routes/ui_routes/common.py`
  - `bases/xtreme_system/api/routes/json.py`
  - `bases/xtreme_system/api/route_factories.py`
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/compras.py`
  - `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
  - `bases/xtreme_system/api/routes/ui_routes/auditoria.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos_cliente_vendedor.py`
  - `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`
- **Related opportunities:** imp-20260730-004

### Location

`bases/xtreme_system/api/deps.py:37-48` — `_found`

```python
def _bind_usuario(session: Session, user: usuario.Usuario) -> usuario.Usuario:
    session.info["usuario_id"] = user.id
    return user


def _found[T](obj: T | None, nome: str) -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nome} não encontrado")
    return obj


# ---- Autenticação API (Bearer token) ----
```

### Description

At least seven underscore-prefixed names are imported across module boundaries by ten or more call
sites: `_found`, `_uploads_dir`, `_uploads_cliente_dir`, `_uploads_compra_dir`, `_uploads_empresa_dir`,
`_uploads_contrato_venda_dir`, `_uploaded_file_path`, `_remover_upload`, and `_vazio_para_none`.

Confirmed call sites include `routes/json.py:13`, `route_factories.py:27`, `crud_ui/routes.py:51`,
`ui_routes/auditoria.py:15,20`, `ui_routes/vendas.py:34,39,40`, `ui_routes/compras.py:30,35-37`,
`ui_routes/configuracoes.py:18-20`, `ui_routes/veiculos.py:33`,
`ui_routes/veiculos_documentos.py:9,11`, `ui_routes/veiculos_cliente_vendedor.py:11`, and
`ui_routes/lancamentos.py:12`. The leading underscore states "internal, safe to change", while the
actual contract is "public, ten callers".

### Why it matters

This is a direct trap for LLM-assisted edits. The single strongest local signal an agent has for "can
I rename, inline, or delete this?" is the underscore prefix, and here that signal is inverted. Static
tooling reinforces the error: linters flag *access* to protected members, not the misleading
declaration, so an agent that "cleans up" `_remover_upload` breaks three route modules.

### Concrete fix

Rename the cross-module names to public — `found` (or `get_or_404`), `uploads_dir`,
`uploaded_file_path`, `remover_upload`, `vazio_para_none` — and declare them in an `__all__` on the
owning module. Do this as part of the `common.py` split (imp-20260730-004) so the moves happen once.
Keep the underscore only on names with a single in-module caller.

### Potential savings

Restores the private/public signal across roughly 15 call sites and makes the safe-to-change surface
machine-checkable via `__all__`.

### Domain details

#### Modularity details

- **LLM risk:** The private-name convention is inverted, so an agent's safest heuristic for "local,
  safe to change" produces cross-module breakage.
- **Suggested interface:** `__all__` declared on `deps.py` and on each module produced by the
  `common.py` split.
- **New structure:** No structural change — renames plus explicit `__all__`.
- **Tests:** No new tests; the existing suite covers the renames. Add a lint rule (ruff `PLC2701` or an
  import-linter contract) forbidding cross-module underscore imports to prevent recurrence.
- **Success metric:** `rg "import .*[ ,]_[a-z]" bases/` returns zero cross-module hits.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Purely mechanical and verifiable — every call site is cited with file and line.
  - A rename is behaviour-preserving and fully covered by the existing test suite.
- **Weaknesses:**
  - Low intrinsic risk reduction on its own; it is a naming fix, and its real value is conditional on
    agents actually treating the underscore as a signal.
- **Suggested checks:**
  - Confirm ruff `PLC2701` (or equivalent) can be enabled without a large pre-existing violation
    backlog elsewhere in the repo.

## imp-20260730-007 — CSV export contract is three hand-aligned parallel lists while a ColumnSpec abstraction already exists unused

- **Impact:** High
- **Category:** Contract strength
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** parallel-arrays, implicit-contract, csv-export, dead-abstraction, permissions
- **Files affected:**
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/crud_ui/routes.py`
  - `bases/xtreme_system/api/crud_ui/responses.py`
  - `bases/xtreme_system/api/routes/ui_routes/*.py` (other modules using the legacy triple)
- **Related opportunities:** imp-20260730-002, imp-20260730-003

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:182-193` — `register_crud_ui_routes` export config

```python
    export=CrudUIExportConfig(
        csv_filename="vendas.csv",
        csv_headers=[
            "ID",
            "Cliente",
            "Veiculo",
            "Data/Hora",
            "Valor Venda",
            "Valor Entrada",
            "Debitos",
            "KM",
            "Veiculo Troca",
```

### Description

`CrudUIExportConfig` (`crud_ui/routes.py:106-113`) accepts two mutually exclusive shapes: a structured
`columns: Sequence[ColumnSpec]`, or the legacy triple of `csv_headers` / `csv_fields` / `csv_row` whose
correctness depends entirely on three lists staying index-aligned by hand.

`vendas.py:182-258` uses the legacy triple with 18 entries in each of the three literals, spread over
76 lines. `csv_fields` additionally carries the profile field-visibility mapping, so a misalignment
does not just shift a column heading — it exports a field the profile was meant to hide. The
structured alternative, `ColumnSpec` (`crud_ui/routes.py:96-104`), is already defined and used by other
resources.

### Why it matters

"Add a column to the vendas CSV" is a textbook small LLM edit, and here it requires three coordinated
insertions at the same index in three separate literals 40 lines apart, with no type, test, or runtime
check catching a miss. Because two competing shapes exist, an agent must also first work out which
convention this resource follows.

### Concrete fix

Migrate `vendas.py` — and any other legacy-triple caller — to
`columns=[ColumnSpec(key=..., label=..., field=..., export=lambda v: ...), ...]`, then delete
`csv_headers`, `csv_fields`, and `csv_row` from `CrudUIExportConfig` so only one shape remains.

### Potential savings

Turns a three-place coordinated edit into one, removes a silent hidden-field-leak path, and deletes
one of two competing export contracts.

### Domain details

#### Modularity details

- **LLM risk:** Adding or reordering an export column requires three synchronised edits; a miss
  silently shifts every subsequent column and can leak a profile-hidden field.
- **Suggested interface:**
  `CrudUIExportConfig(csv_filename: str, columns: Sequence[ColumnSpec[EntityT]], pagina: str | None = None)`
  with the legacy fields removed.
- **New structure:** A single `ColumnSpec`-based export path in `crud_ui/`.
- **Tests:** A test asserting `len(headers) == len(row)` for every registered resource, plus one
  asserting a profile-hidden column is absent from both header and row.
- **Success metric:** `csv_headers`, `csv_fields`, and `csv_row` no longer exist in the codebase.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Three 18-element parallel lists are objectively fragile.
  - The better abstraction already exists in the same codebase, so this is a migration rather than a
    new design.
- **Weaknesses:**
  - I verified the legacy triple in `vendas.py` but did not enumerate every other resource still on
    it, so the migration's total size is not established here.
- **Suggested checks:**
  - Grep for `csv_headers=` across `ui_routes/` to size the full migration before scheduling it.

## imp-20260730-008 — routes/workflows.py holds cross-domain business rules in the API layer with every payload typed Any

- **Impact:** High
- **Category:** Contract strength
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** any-typing, domain-logic-in-api, exception-boundary, cross-component-rules
- **Files affected:**
  - `bases/xtreme_system/api/routes/workflows.py`
  - `components/xtreme_system/venda/core.py`
  - `components/xtreme_system/compra/core.py`
  - `components/xtreme_system/caixa/core.py`
  - `bases/xtreme_system/api/routes/json.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/compras.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
- **Related opportunities:** imp-20260730-001, imp-20260730-011

### Location

`bases/xtreme_system/api/routes/workflows.py:39-49` — `validate_cliente_veiculo_fks`

```python
def validate_cliente_veiculo_fks(session: Session, data: Any) -> None:
    cli_id = getattr(data, "cliente_id", None)
    vei_id = getattr(data, "veiculo_id", None)
    troca_id = getattr(data, "veiculo_troca_id", None)
    if cli_id is not None and cliente.get(session, cli_id) is None:
        raise HTTPException(status_code=400, detail="cliente_id inexistente")
    if vei_id is not None and veiculo.get(session, vei_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if troca_id is not None and veiculo.get(session, troca_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_troca_id inexistente")
    ven_id = getattr(data, "vendedor_id", None)
```

### Description

This module is where genuinely cross-domain rules live — "a sale's vehicle must be available", "cancelling
a purchase cancels the vehicle", "deleting a sale recomputes vehicle status" — and it sits in the API
base rather than in any component. Every payload parameter is `Any` (`workflows.py:26, 39, 54, 69, 74,
82`), with field access via a mix of direct attribute reads (`data.investidor_id`, `workflows.py:27`)
and defensive `getattr(data, ..., None)`.

It also raises `HTTPException` at `:30, :36, :44-51, :64, :66`, embedding HTTP status codes into
business rules. `validate_valores_venda_update` (`:54-58`) is a pure `ValueError → HTTPException`
translation of a rule that already lives in `venda.core`, showing the intended split exists but is only
half applied.

### Why it matters

`Any` means neither a type checker nor an LLM can tell which schemas are valid inputs to
`validate_cliente_veiculo_fks` — the `getattr` defaults exist precisely because the answer is "several,
with different field sets". An agent adding a field cannot verify any call site. And because the rules
raise `HTTPException`, they are not reusable from a CLI, a job, or a test without a FastAPI context.

### Concrete fix

Move each rule to the component that owns the invariant — `venda.core` for sale rules,
`compra`/`caixa` for the purchase-cash sync — have them raise domain errors (`VendaError`, mirroring
the existing `FechamentoVendaError` at `fechamento_venda/core.py:36`), and replace `Any` with the real
union (`VendaCreate | VendaUpdate`). Keep only the domain-error-to-`HTTPException` mapping in the API
layer, ideally as a FastAPI exception handler rather than per-function translation.

### Potential savings

Removes eight `Any` parameters, makes cross-entity rules testable without HTTP, and gives each rule one
owning module.

### Domain details

#### Modularity details

- **LLM risk:** `Any` plus `getattr` defaults means an agent cannot determine the valid input schemas,
  and cannot be warned by mypy when a field is renamed.
- **Suggested interface:** `venda.validar_para_criar(session, data: VendaCreate) -> None` raising
  `VendaError`; the API maps `VendaError → HTTPException` in one handler.
- **New structure:** Rules distributed to owning components; `workflows.py` reduced to typed
  cross-component orchestration.
- **Tests:** Component-level tests calling the validators directly and asserting domain exceptions — no
  `TestClient` required.
- **Success metric:** Zero `Any`-typed parameters in `workflows.py`; zero `HTTPException` raises in
  component code.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Every parameter is literally annotated `Any` in the current file.
  - `validate_valores_venda_update` is a visible, already-half-done example of the exact split being
    proposed.
- **Weaknesses:**
  - These rules are cross-component by nature, so "move it to the owning component" is genuinely
    awkward for `sincronizar_caixa_compra`, which spans `compra`, `veiculo`, and `caixa` — that one may
    legitimately belong in a base-layer orchestration module, just a typed one.
- **Suggested checks:**
  - Enumerate the concrete schema types passed at each call site to confirm the proposed unions are
    complete before changing the annotations.

## imp-20260730-009 — CRUD UI route registrars flatten their config dataclasses into 10-14 keyword parameters each

- **Impact:** Medium
- **Category:** Locality of change
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** parameter-explosion, config-objects, change-locality, crud-factory
- **Files affected:**
  - `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260730-002, imp-20260730-003

### Location

`bases/xtreme_system/api/crud_ui/routes.py:265-276` — `register_crud_ui_routes`

```python
    if routes.register_update:
        register_update_route(
            app,
            form,
            module,
            prefix,
            resource.label,
            update_schema=resource.update_schema,
            list_key=resource.list_key,
            ok_partial_template=templates_config.ok_partial_template,
            ctx_list=ctx_list,
            parse_form=behavior.parse_form,
```

### Description

The five config dataclasses — `CrudUIResourceConfig`, `CrudUITemplateConfig`, `CrudUIBehaviorConfig`,
`CrudUIExportConfig`, `CrudUIRouteConfig` (`routes.py:63-127`) — exist and are the right idea, but
`register_crud_ui_routes` (`routes.py:175-297`) immediately destructures them and forwards 10 to 14
loose keyword arguments to each sub-registrar. `register_update_route` (`routes.py:617-634`) alone
takes 14 parameters.

The pylint suppressions in the file record the pressure: `too-many-branches` at `routes.py:174` and
`too-many-instance-attributes` at `routes.py:80` and `routes.py:116`.

### Why it matters

Adding one option — say `pagina` to the create path, which imp-20260730-003 requires — means editing
the dataclass, the registrar's parameter list, the call site inside `register_crud_ui_routes`, and the
closure body: four coordinated edits in one file for one flag. That is the opposite of a localised
change, and it is the single most likely place an LLM drops a parameter and produces a `TypeError` at
import time, or worse, silently falls back to a default.

### Concrete fix

Pass the frozen config objects straight through —
`register_update_route(app, form, module, prefix, resource=resource, templates_config=templates_config, behavior=behavior, listing=listing, routes=routes, export=export)`
— instead of destructuring. Each registrar then reads what it needs from typed objects, and adding a
field touches exactly one dataclass.

### Potential savings

A new config option becomes a one-line change instead of four, and roughly 50 lines of argument
forwarding disappear.

### Domain details

#### Modularity details

- **LLM risk:** Adding one CRUD-factory option requires four coordinated edits; a dropped argument
  fails at import time or silently falls back to a default.
- **Suggested interface:**
  `register_update_route(app, form, module, prefix, *, resource: CrudUIResourceConfig, templates_config: CrudUITemplateConfig, behavior: CrudUIBehaviorConfig, listing: ListingSpec, export: CrudUIExportConfig, routes: CrudUIRouteConfig) -> None`
- **New structure:** No new files; registrars accept the existing frozen dataclasses directly.
- **Tests:** `tests/test_route_factories_ui.py` already exercises these registrars — run unchanged as
  the regression gate.
- **Success metric:** No registrar takes more than six keyword parameters.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Fully contained in one file, behaviour-preserving, and directly covered by
    `tests/test_route_factories_ui.py`.
  - The pylint suppressions are the maintainer's own record of the pressure.
- **Weaknesses:**
  - Passing whole config objects widens each registrar's nominal input surface, which slightly weakens
    the "this function needs exactly these five things" signal — a real trade-off, not a free win.
- **Suggested checks:**
  - Confirm no sub-registrar is called from outside `register_crud_ui_routes`, which would make the
    signature change wider than one file.

## imp-20260730-010 — deps.py builds a module-level Jinja environment with 11 globals and imports downward into ui_routes

- **Impact:** Medium
- **Category:** Dependency control
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** mutable-singleton, import-time-side-effects, bidirectional-dependency, templating, testability
- **Files affected:**
  - `bases/xtreme_system/api/deps.py`
  - `bases/xtreme_system/api/routes/ui_routes/common.py`
  - `bases/xtreme_system/api/routes/ui_routes/*.py` (every module importing `templates`)
- **Related opportunities:** imp-20260730-004, imp-20260730-005

### Location

`bases/xtreme_system/api/deps.py:15-26` — module-level template environment

```python
from xtreme_system.api.routes.ui_routes.common import arquivo_disponivel
from xtreme_system.auth import core as auth
from xtreme_system.cliente import core as cliente
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["pode_acessar"] = perfil.pode_acessar
templates.env.globals["pode_operacao"] = perfil.pode_operacao
templates.env.globals["pode_ver_campo"] = perfil.pode_ver_campo
templates.env.globals["paginas_labels"] = dict(perfil.PAGINAS)
```

### Description

A module intended for FastAPI dependencies also constructs, at import time, the single mutable Jinja
environment for the whole UI and wires 11 template globals and filters into it (`deps.py:22-31`). The
`dict(perfil.PAGINAS)` copy at line 26 snapshots policy data at import.

To reach `arquivo_disponivel`, `deps.py:15` imports from `routes/ui_routes/common.py` — while every
module in `routes/ui_routes/` imports `deps` — creating a bidirectional dependency between the
dependency layer and the route layer.

### Why it matters

There is no way to construct a second template environment (for a test with a different global, or a
future admin surface) without mutating global state that every route shares. The downward import means
editing `common.py` can break the `deps.py` import, which breaks every route — a blast radius invisible
from `common.py` itself. An LLM adding a template helper has no single obvious place to put it and will
plausibly widen the cycle.

### Concrete fix

Move the environment construction and global registration into
`bases/xtreme_system/api/templating.py`, exposing `build_templates() -> Jinja2Templates` plus a
module-level `templates = build_templates()` for the app to use. `deps.py` then only re-exports
dependencies and no longer imports from `routes/`, breaking the bidirectional edge.

### Potential savings

Removes the `deps ↔ ui_routes` cycle and makes the template environment constructible per test.

### Domain details

#### Modularity details

- **LLM risk:** An agent adding a Jinja global or filter has no designated home and may deepen the
  `deps ↔ ui_routes` cycle; the shared mutable environment makes any such addition globally visible.
- **Suggested interface:** `build_templates(directory: Path | None = None) -> Jinja2Templates`
- **New structure:** `bases/xtreme_system/api/templating.py`; `deps.py` keeps only FastAPI
  dependencies.
- **Tests:** A test constructing an isolated `build_templates()` and asserting the expected globals and
  filters are registered.
- **Success metric:** `deps.py` contains no import from `xtreme_system.api.routes`.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The downward import at `deps.py:15`, set against the pervasive `from ...deps import templates` in
    route modules, is a clear and verifiable bidirectional edge.
  - The extraction is mechanical.
- **Weaknesses:**
  - A single module-level `templates` object is idiomatic FastAPI and causes no observed problem
    today; the concrete payoff is the cycle removal, with per-test environments being speculative
    benefit.
- **Suggested checks:**
  - Confirm no template global depends on request-scoped state, which would complicate moving
    construction behind a factory.

## imp-20260730-011 — fechamento_venda.confirmar mixes calculation, validation, ORM writes, auditing and ledger posting behind a process-wide schema cache

- **Impact:** Medium
- **Category:** Boundary clarity
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** mixed-responsibilities, pure-function-extraction, tuple-contract, global-cache, financial-logic
- **Files affected:**
  - `components/xtreme_system/fechamento_venda/core.py`
  - `components/xtreme_system/caixa/core.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/relatorios.py`
- **Related opportunities:** imp-20260730-001, imp-20260730-008

### Location

`components/xtreme_system/fechamento_venda/core.py:227-238` — `confirmar`

```python
    if not _schema_disponivel(session):
        raise FechamentoVendaError(ERRO_SCHEMA_DESATUALIZADO)
    receita, custo_veiculo, custos_operacionais, debitos, lucro = _calcular(
        session, venda_obj
    )
    _validar_elegibilidade(session, venda_obj)
    _validar_participacoes(session, data.participacoes, lucro)

    fechamento = FechamentoVenda(
        venda_id=venda_obj.id,
        usuario_id=usuario_id,
        receita=receita,
```

### Description

One 76-line function (`core.py:220-295`) runs five distinct stages — schema guard, calculation,
validation, ORM construction plus flush, auditing, and cash-ledger posting — and the financial core
(profit calculation and distribution) is only reachable through it. `_calcular` returns a bare 5-tuple
(`core.py:229-231`), so every consumer must remember positional meaning.

Separately, `_schema_disponivel` caches table existence per engine in a module-level
`WeakKeyDictionary` (`core.py:33`, populated at `core.py:147-162`) and is consulted by `get`,
`get_by_venda`, `listar_para_dre`, and `confirmar` — a process-wide mutable cache inside domain code
that makes a migration applied mid-process invisible and that persists across tests sharing an engine.

### Why it matters

The profit-distribution rule is the highest-consequence logic in the system and can only be tested by
writing a sale, a vehicle, an investor, and a full session. An LLM changing the distribution rounding
must reason about audit rows and cash-ledger entries in the same breath. The 5-tuple means adding a
cost category silently shifts every unpacking site.

### Concrete fix

Extract a pure `calcular_fechamento(...) -> ResultadoFechamento` — a frozen dataclass replacing the
5-tuple — and a pure `distribuir_lucro(lucro, participacoes) -> list[Decimal]`, both free of `Session`.
`confirmar` keeps persistence, auditing, and ledger posting. Move `_schema_disponivel` behind an
explicit `FechamentoSchemaGuard` passed in, or drop the guard once the migration is guaranteed applied.

### Potential savings

Financial rules become pure-function unit tests with no database, and the 5-tuple becomes a named
record.

### Domain details

#### Modularity details

- **LLM risk:** The most financially consequential rule is unreachable without full DB setup, so an
  agent changing rounding or distribution cannot get fast, isolated feedback.
- **Suggested interface:**
  `calcular_fechamento(receita: Decimal, custo_veiculo: Decimal, custos_operacionais: Decimal, debitos: Decimal) -> ResultadoFechamento`
  and `distribuir_lucro(lucro: Decimal, participacoes: Sequence[ParticipacaoCreate]) -> list[Decimal]`
- **New structure:** `components/xtreme_system/fechamento_venda/calculo.py` (pure) alongside `core.py`
  (persistence, audit, ledger).
- **Tests:** `tests/test_fechamento_calculo.py` — pure tests for rounding, zero and negative profit,
  and percentages summing to 100 with remainder distribution.
- **Success metric:** `calculo.py` imports neither `Session` nor any model; `confirmar` under 40 lines.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** Yes
- **Strengths:**
  - The five stages and the bare 5-tuple are directly visible in the quoted code.
  - `tests/test_fechamento_venda.py` (476 lines) is substantial existing coverage for the refactor.
- **Weaknesses:**
  - `_calcular` needs a `Session` to gather operational costs, so making it fully pure requires the
    caller to load costs first — a real interface change, not a free extraction.
  - The `_schema_disponivel` guard has a documented rationale (the comment at `core.py:154-156`
    explains why it inspects the connection rather than the engine), so removing it needs care.
- **Suggested checks:**
  - Trace what `_calcular` reads from the session to confirm the pure signature captures every input.

## imp-20260730-012 — Permission page and operation pairs are bare string literals with no link to the perfil policy definitions

- **Impact:** Medium
- **Category:** Contract strength
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** magic-strings, permissions, type-safety, fail-closed, policy
- **Files affected:**
  - `components/xtreme_system/perfil/policy.py`
  - `components/xtreme_system/perfil/core.py`
  - `bases/xtreme_system/api/deps.py`
  - `bases/xtreme_system/api/route_factories.py`
  - `bases/xtreme_system/api/routes/ui_routes/compras.py`
  - `bases/xtreme_system/api/routes/ui_routes/clientes.py`
  - `bases/xtreme_system/api/routes/ui_routes/investidores.py`
  - `bases/xtreme_system/api/routes/ui_routes/vendas.py`
  - `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
  - `bases/xtreme_system/api/routes/ui_routes/custos_veiculos.py`
- **Related opportunities:** imp-20260730-003

### Location

`bases/xtreme_system/api/routes/ui_routes/compras.py:64-74` — permission dependency aliases

```python
_EditarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "editar"))
]
_CadastrarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "cadastrar"))
]
_ExcluirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "excluir_comprovante"))
]
_AbrirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "abrir_comprovante"))
```

### Description

`require_operacao(pagina: str, operacao: str)` (`deps.py:154`) and
`perfil.pode_operacao(user, pagina, operacao)` take plain strings. The valid pairs are enumerated in
`perfil/policy.py`, re-exported as `OPERACOES` and `PAGINAS_VALIDAS` at `perfil/core.py:14-18`, but
nothing connects the two: a typo produces a perfectly valid call.

The literals appear at 25 or more sites across six route modules — `compras.py:65-77, 350, 395`,
`clientes.py:72-75, 316, 372-374`, `investidores.py:173-176`, `vendas.py:377, 424`, `veiculos.py:366` —
and the same `(pagina, operacao)` pair is often repeated in both a `Depends` guard and an inline
`pode_operacao` check within one file (compare `compras.py:77` with `compras.py:350`).

### Why it matters

Because `pode_operacao` is an allowlist — denied by default for non-admins per `ARCHITECTURE.md` — a
misspelled operation fails closed and silently: the route simply denies everyone except admins, and
admins, who bypass both checks, will never notice in manual testing. An LLM adding a guarded operation
must guess the exact string, and gets no autocomplete, no type error, and no test failure — only a
permission that quietly never grants.

### Concrete fix

Promote the policy to enums or `Literal` types in `perfil/policy.py` (`class Pagina(StrEnum)`,
`class Operacao(StrEnum)`, or `PaginaLit = Literal["vendas", ...]`) and change the `require_operacao`
and `pode_operacao` signatures to accept them. Add a startup assertion that every `(pagina, operacao)`
pair used by a registered route exists in `OPERACOES`.

### Potential savings

Turns 25 or more unchecked string literals into type-checked references; typos become mypy errors
instead of silent permanent denials.

### Domain details

#### Modularity details

- **LLM risk:** An added guard with a typo'd operation name silently denies all non-admin users, and
  the admin bypass means manual verification will not catch it.
- **Suggested interface:** `require_operacao(pagina: Pagina, operacao: Operacao) -> DepFilter` and
  `pode_operacao(user: Usuario, pagina: Pagina, operacao: Operacao) -> bool`
- **New structure:** `perfil/policy.py` gains `Pagina` and `Operacao` StrEnums; call sites reference
  members.
- **Tests:** A test iterating the FastAPI route table and asserting every `require_operacao` pair is
  present in `OPERACOES`.
- **Success metric:** `rg 'require_operacao\("'` returns zero string-literal call sites.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** Yes
- **Strengths:**
  - The literals and the authoritative enumeration in `perfil/policy.py` are both concrete and cited.
  - The fail-closed-and-silent failure mode follows directly from the documented allowlist semantics.
- **Weaknesses:**
  - I did not check whether `tests/test_perfil.py` already cross-validates route literals against
    `OPERACOES`; if it does, the practical risk is materially lower than stated and this drops toward
    Low impact.
- **Suggested checks:**
  - Read `tests/test_perfil.py` for an existing route-table-versus-policy consistency test before
    scheduling this work.

## Discarded candidates

### Component core.py modules combine SQLAlchemy model, Pydantic schemas and CRUD functions

Observed in `venda/core.py` (612 lines), `cliente/core.py` (400), `veiculo/core.py` (327) and others.
Not retained: this is the codebase's deliberate and uniformly applied Polylith convention, and the
consistency itself aids LLM navigation — an agent that learns the pattern once applies it everywhere.
Splitting into `models.py` / `schemas.py` would be cosmetic and would break the documented
`from xtreme_system.venda import core as venda` idiom used at every call site.

Worth noting separately: `ARCHITECTURE.md` describes a `models.py` / `schemas.py` split that does not
exist in any component. That is a documentation fix, not a refactor.

### Global app singleton with importlib side-effect route registration

`bases/xtreme_system/api/setup.py:149` defines `app`, imported by 20 route modules; `routes/ui.py:5-26`
imports each module purely for its registration side effect. Not retained: the problem is real and does
prevent building an isolated second app instance in tests, but converting 20 modules to `APIRouter` is a
high-effort, high-risk change touching every route file at once, for a benefit — per-test app
construction — that the current suite does not appear to need. Revisit if per-test app isolation ever
becomes a requirement.

### resolver_cliente / _resolver_veiculo duplication as a standalone finding

`common.py:168-213` and `compras.py:243-284`. Not retained as its own entry: it is genuine duplication,
but it is the clearest symptom of imp-20260730-004 rather than an independent problem, and fixing it
separately from the `common.py` split would mean moving the same code twice. Folded into
imp-20260730-004.
