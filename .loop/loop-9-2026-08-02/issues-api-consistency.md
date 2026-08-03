# Improvement opportunities

- **Generated:** 2026-08-01T13:15:49-03:00
- **Total:** 15

## imp-20260801-001 — Delete-conflict message is silently dropped by every list partial

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, error-shape, htmx, templates
- **Files affected:** `bases/xtreme_system/api/crud_ui/routes.py`, `bases/xtreme_system/api/crud_ui/responses.py`, `bases/xtreme_system/api/templates/_linhas_veiculos.html`, `bases/xtreme_system/api/templates/_linhas_perfis.html`, `bases/xtreme_system/api/templates/_linhas_investidores.html`, `bases/xtreme_system/api/templates/_linhas_lancamentos.html`, `bases/xtreme_system/api/templates/_linhas_simples.html`, `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `bases/xtreme_system/api/routes/ui_routes/investidores.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`
- **Related opportunities:** imp-20260801-006, imp-20260801-007

### Location

Outlier — the canonical factory delete-conflict path passes the message as `erro`:

`bases/xtreme_system/api/crud_ui/routes.py:923` — `register_delete_route._excluir`

```python
                    module,
                    config.list_partial_template,
                    user=user,
                    list_key=config.list_key,
                    ctx_list=config.ctx_list,
                    listing=config.listing,
                    erro=delete_conflict_detail(config.label),
                    status_code=409,
                )

            return rollback_integrity_error_response(
                session,
```

Pattern it must match — the list partial that actually renders, which only knows `msg`:

`bases/xtreme_system/api/templates/_linhas_veiculos.html:1` — template body

```html
{% import "_macros.html" as ui %}
<tbody id="linhas"{% if oob %} hx-swap-oob="true"{% endif %}>
{% for v in veiculos %}{% include "_row_veiculo.html" %}{% else %}
<tr class="empty-row"><td colspan="15">
  {% call ui.empty("inbox", "Nenhum veículo encontrado", "Ajuste a busca ou cadastre um novo veículo para começar.") %}{% endcall %}
</td></tr>
{% endfor %}
</tbody>
{% if oob %}{% include "_stats_veiculos.html" %}{% endif %}
{% if msg %}<div id="msg" role="status" hx-swap-oob="true">{{ ui.icon("check") }}<span>{{ msg }}</span></div>{% endif %}
```

### Description

`delete_list_response` (`crud_ui/routes.py:857-889`) forwards `erro` into `list_response`, which
puts it in the template context under the key `erro` (`crud_ui/responses.py:197-198`). No
`_linhas_*.html` partial reads `erro` — a grep over all five (`_linhas_veiculos.html:10`,
`_linhas_investidores.html:40`, `_linhas_lancamentos.html:31`, `_linhas_perfis.html:27`,
`_linhas_simples.html:21`) shows they only render `msg`. So every delete that fails on a foreign-key
conflict for a factory-driven resource (veículos, clientes, compras, vendas, and the `simple`
resources) returns HTTP 409 with a list partial that looks exactly like a successful delete and
carries no explanation at all.

The two hand-written resources went the other way: `perfis.py:189` and `investidores.py:298` pass
the failure under `msg`, which the template renders inside `<div role="status">` with a **check
icon** — the success styling. So the same logical failure (delete refused) produces three different
client outcomes across the app: invisible (factory resources), styled as success (perfis,
investidores), or styled as success with a different wording.

### Why it matters

A user who tries to delete a vehicle with linked records gets a table that re-renders unchanged with
no message and no visual signal — indistinguishable from "nothing happened", so they retry. On perfis
and investidores they get a green success banner telling them the operation failed. Both defeat the
409 the server correctly returned, and no client-side code can compensate because the failure never
reaches the DOM in a distinguishable form.

### Concrete fix

Add an `{% if erro %}` block to the shared list partials, rendered as an alert (`role="alert"` with
an alert icon) rather than the `role="status"` check block used for `msg`, and change `perfis.py:189`
and `investidores.py:298` to pass `erro=` instead of `msg=` so all delete-conflict paths use the
single key `list_response` already populates.

### Potential savings

Removes the need for a per-resource error convention: one `erro` key covers all delete-conflict,
list-error, and validation-error swaps that `list_response` already supports.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Verified by grep that no `_linhas_*.html` partial references `erro`, and that all five reference
    `msg` in a `role="status"` success block.
  - Both sides of the divergence read directly: `delete_list_response` passes `erro`, `perfis.py`
    and `investidores.py` pass `msg`.
- **Weaknesses:**
  - Did not confirm whether a global `#msg` container elsewhere in `base.html` renders `erro` by
    some other mechanism.
- **Suggested checks:**
  - Trigger a delete conflict on `/ui/veiculos/{id}/excluir` and inspect the swapped HTML for any
    error text.

## imp-20260801-002 — UI routes return JSON `{"detail": ...}` into HTMX swaps on 404

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, error-shape, htmx, status-codes
- **Files affected:** `bases/xtreme_system/api/setup.py`, `bases/xtreme_system/api/deps.py`
- **Related opportunities:** imp-20260801-004, imp-20260801-005

### Location

Outlier — `found()` raises a bare `HTTPException`, used by essentially every `/ui/` handler:

`bases/xtreme_system/api/deps.py:62` — `found`

```python
def found[T](obj: T | None, nome: str) -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nome} não encontrado")
    return obj


# ---- Autenticação API (Bearer token) ----


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
) -> usuario.Usuario:
```

Pattern it should match — the UI-aware handlers that already branch on `/ui/`:

`bases/xtreme_system/api/setup.py:362` — exception handlers

```python
@app.exception_handler(NaoAdminError)
def _handle_nao_admin(_request: Request, _exc: NaoAdminError) -> HTMLResponse:
    return HTMLResponse("<p>Requer papel admin</p>", status_code=403)


@app.exception_handler(NaoAutorizadoError)
def _handle_nao_autorizado(_request: Request, _exc: NaoAutorizadoError) -> HTMLResponse:
    return HTMLResponse(
        "<p>Seu perfil não tem acesso a esta página.</p>", status_code=403
    )


@app.exception_handler(Exception)
def _handle_erro_interno(request: Request, _exc: Exception) -> Response:
    if request.url.path.startswith("/ui/"):
        return HTMLResponse("<p>Erro interno. Contate suporte.</p>", status_code=500)
```

### Description

`setup.py` registers handlers for `NaoAutenticadoError`, `NaoAdminError`, `NaoAutorizadoError`, and
the catch-all `Exception` — and the last two explicitly branch on `request.url.path.startswith("/ui/")`
to return HTML rather than JSON. There is no handler for `HTTPException`, so FastAPI's built-in one
runs and emits `{"detail": "..."}` as `application/json`.

Every `/ui/` route funnels missing entities through `found()`: `veiculos.py:252`, `vendas.py:466`,
`clientes.py:113`, `usuarios.py:140`, `lancamentos.py:200`, `perfis.py:178`, `crud_ui/routes.py:602`,
`crud_ui/routes.py:765`, `crud_ui/routes.py:911`, plus every upload sub-resource. The middleware in
`setup.py:227-234` and `setup.py:263-265` shows the intended rule (HTML under `/ui/`, JSON
elsewhere); the HTTPException path is the one place that rule is not applied.

### Why it matters

An HTMX request that hits a stale id (deleted in another tab, a bookmarked modal link) swaps a raw
JSON string into a table row or modal body. The user sees `{"detail":"Veículo não encontrado"}` as
literal text inside the page chrome, and the 409/404 handling the rest of the UI does carefully is
bypassed. It also means UI and JSON API disagree with each other about what a `/ui/` error body is.

### Concrete fix

Register one `HTTPException` handler in `setup.py` that mirrors the existing `/ui/` branch: return
`HTMLResponse(f"<p>{exc.detail}</p>", status_code=exc.status_code)` for paths starting with `/ui/`,
and delegate to FastAPI's built-in `http_exception_handler` for everything else so the JSON API
contract is unchanged.

### Potential savings

One handler replaces the need for every `/ui/` route to defensively translate `found()` failures
into HTML itself.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Verified by grep that `setup.py` registers no `HTTPException` handler, only the four listed.
  - Confirmed the codebase already encodes the "HTML under /ui/" rule in two other places.
- **Weaknesses:**
  - Starlette's built-in `HTTPException` handler runs inside `ExceptionMiddleware`; a custom handler
    must be registered on the app (which the fix does), but ordering was not exercised at runtime.
- **Suggested checks:**
  - `GET /ui/veiculos/999999/editar` with `HX-Request: true` and assert the body is HTML.

## imp-20260801-003 — `/ui/usuarios`, `/ui/perfis`, `/ui/investidores` list without any pagination

- **Impact:** High
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, pagination, list-endpoints
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/usuarios.py`, `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `bases/xtreme_system/api/routes/ui_routes/investidores.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-013, imp-20260801-014

### Location

Outlier — no `limit`/`offset`/`q`, unbounded `list_all`, sorted in Python:

`bases/xtreme_system/api/routes/ui_routes/usuarios.py:47` — `ui_usuarios`

```python
def ui_usuarios(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    usuarios = usuario.list_all(session)
    field = _USUARIO_SORT_FIELDS.get(sort)
    if field:
        usuarios = sorted(
            usuarios,
```

Pattern it should match — every factory-generated list route:

`bases/xtreme_system/api/crud_ui/routes.py:458` — `register_list_route._list`

```python
    @app.get(prefix)
    def _list(
        request: Request,
        session: SessionDep,
        user: UIUser,
        q: str = "",
        sort: str = "",
        order: str = "asc",
        search_column: str = "",
        limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> HTMLResponse:
```

### Description

Three list screens diverge from the shared contract. `ui_usuarios` (`usuarios.py:46-71`),
`ui_perfis` (`perfis.py:58-75`) and `ui_investidores` (`investidores.py:131-142`) accept only
`sort`/`order`, call `list_all(session)` with no bound, and sort the full result set in Python.
Every other list surface in the app is bounded: the CRUD-UI factory uses
`Query(ge=1, le=LIST_LIMIT_MAX)` with DB-side ordering, `/ui/auditoria` declares
`limit: int = Field(50, ge=1, le=LIMIT_MAX)` (`auditoria.py:48-49`), and the JSON API caps at
`JSON_LIST_LIMIT_MAX = 200` (`route_factories.py:31, 131-132`).

The templates for these screens also cannot render pagination controls, because `list_response`'s
`tem_proximo`/`page_start`/`offset_proximo` context is never produced for them.

### Why it matters

Response size and query time grow linearly and without ceiling as usuarios, perfis, and investidores
accumulate; the Python-side sort makes it worse by materializing and re-sorting the whole table on
every sort click. Any generic pagination component or client written against the factory list
contract (`limit`/`offset`/`q`) silently returns everything on these three routes instead of one
page.

### Concrete fix

Add `limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = 50` and
`offset: Annotated[int, Query(ge=0)] = 0` to the three handlers, push them into the corresponding
`list_all(...)`/`query` call, and route the render through `list_response` so the shared pagination
context is produced.

### Potential savings

Bounds three currently unbounded queries and makes the same pagination markup reusable across all
list screens instead of three bespoke tables.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Verified all three handlers' signatures and their `list_all(session)` calls with no arguments.
  - Verified the majority pattern in three independent places (factory, auditoria, JSON factory).
- **Weaknesses:**
  - Did not measure current row counts, so the practical urgency depends on deployment size.
- **Suggested checks:**
  - Count rows in `usuario`, `perfil`, and `investidor` in production to rank urgency.

## imp-20260801-004 — Perfil update accepts invalid input with no validation guard, unlike its own create

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, error-shape, validation
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-002

### Location

Outlier — `PerfilUpdate` is constructed outside any `try`:

`bases/xtreme_system/api/routes/ui_routes/perfis.py:142` — `ui_perfil_atualizar`

```python
@app.post("/ui/perfis/{item_id}")
async def ui_perfil_atualizar(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = found(perfil.get(session, item_id), "Perfil")
    form = await request.form()
    data = perfil.PerfilUpdate(
        nome=str(form.get("nome", "")),
        paginas=form.getlist("paginas"),
        restricoes=_parse_restricoes(form),
    )
    try:
```

Pattern it should match — its sibling create in the same file:

`bases/xtreme_system/api/routes/ui_routes/perfis.py:103` — `ui_perfil_criar`

```python
    form = await request.form()
    try:
        data = perfil.PerfilCreate(
            nome=str(form.get("nome", "")),
            paginas=form.getlist("paginas"),
            restricoes=_parse_restricoes(form),
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "_form_perfil.html",
            {
```

### Description

`ui_perfil_criar` catches `ValidationError` and re-renders `_form_perfil.html` with a 400 and the
field-level message from `validation_error_detail`. `ui_perfil_atualizar`, which parses the same
form into the same shape, has no such guard. The factory's update route does have it
(`crud_ui/routes.py:769-782`), matching its create route.

Because no `/ui/` handler exists for `ValidationError` either, an invalid perfil edit propagates to
the catch-all in `setup.py:374-377` and returns the generic `<p>Erro interno. Contate suporte.</p>`
with status 500 — the app reports its own bug for what is a user input error.

### Why it matters

The same user mistake produces a recoverable 400 form with the offending field named when creating a
perfil, and an unrecoverable 500 "internal error" when editing one — losing the submitted form data
and pointing the user at support instead of at their input. It also pollutes error logs
(`_request_context` calls `logger.exception("unhandled_error", ...)`) with routine validation noise.

### Concrete fix

Wrap the `PerfilUpdate(...)` construction in the same `try/except ValidationError` block used by
`ui_perfil_criar`, re-rendering `_form_perfil.html` with `perfil=obj`, `erro=validation_error_detail(exc)`,
and `status_code=400`.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both handlers read side by side in the same file; the asymmetry is unambiguous.
  - Confirmed no `ValidationError` exception handler is registered in `setup.py`.
- **Weaknesses:**
  - Whether `PerfilUpdate` can actually fail validation depends on its field constraints, which were
    not read.
- **Suggested checks:**
  - `POST /ui/perfis/{id}` with an empty `nome` and confirm the response status.

## imp-20260801-005 — Automatic-lançamento refusal returns 403 "no page access" in the UI and 400 in the JSON API

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, status-codes, error-shape
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`, `bases/xtreme_system/api/routes/json.py`, `bases/xtreme_system/api/setup.py`
- **Related opportunities:** imp-20260801-002

### Location

Outlier — the UI raises an authorization error for a business-rule refusal:

`bases/xtreme_system/api/routes/ui_routes/lancamentos.py:193` — `ui_lancamento_atualizar`

```python
async def ui_lancamento_atualizar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = found(caixa.get(session, lancamento_id), "Lançamento")
    if is_lancamento_automatico(obj):
        raise NaoAutorizadoError
    form = await request.form()
    try:
```

Pattern it should match — the JSON API's guard for the identical rule:

`bases/xtreme_system/api/routes/json.py:168` — `_guard_lancamento_veiculo`

```python
def _validate_investidor_lancamento(session: Session, data: Any) -> None:
    if investidor.get(session, data.investidor_id) is None:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")


def _guard_lancamento_veiculo(_session: Session, obj: Any, _data: Any = None) -> None:
    if is_lancamento_automatico(obj):
        raise HTTPException(
            status_code=400,
            detail="Lançamento automático não pode ser alterado manualmente",
        )
```

### Description

The same domain rule — an automatically generated cash entry cannot be edited or deleted by hand —
is enforced twice with different contracts. The JSON factory wires `_guard_lancamento_veiculo`
(`json.py:173-178`) as `before_update`/`before_delete` and returns **400** with an explanatory
message. The UI raises `NaoAutorizadoError` at `lancamentos.py:163-164`, `201-202`, and `221-222`,
which `setup.py:367-371` renders as **403** with the fixed text
`<p>Seu perfil não tem acesso a esta página.</p>`.

`NaoAutorizadoError` is otherwise used exclusively for perfil-based access control (`deps.py:153`,
`deps.py:155`, `deps.py:177`), so this is the one place the type is repurposed for a business rule.

### Why it matters

An admin who edits an automatic entry is told their **profile lacks page access** — a false and
unactionable message that will drive support tickets about permissions that are not the problem.
Status codes also diverge for the same failure (403 vs 400), so any client or monitor that buckets
403s as authorization failures will miscount these.

### Concrete fix

Replace the three `raise NaoAutorizadoError` sites in `lancamentos.py` with the same
`HTTPException(status_code=400, detail="Lançamento automático não pode ser alterado manualmente")`
the JSON path uses — ideally by calling `_guard_lancamento_veiculo` directly — and let the `/ui/`
HTTPException handler from imp-20260801-002 render it.

### Potential savings

Removes a duplicated rule implementation: one guard function serves both the JSON and UI paths.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both implementations of the same rule read directly, along with the handler that turns
    `NaoAutorizadoError` into its fixed 403 message.
- **Weaknesses:**
  - The fix's rendering depends on imp-20260801-002 landing first, otherwise the 400 surfaces as
    JSON in an HTMX swap.
- **Suggested checks:**
  - `POST /ui/investidores/{i}/lancamentos/{l}` on an automatic entry and read the response text.

## imp-20260801-006 — User-delete error swaps a full HTML page into an HTMX row target

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** api-consistency, htmx, error-shape
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/usuarios.py`, `bases/xtreme_system/api/crud_ui/routes.py`, `bases/xtreme_system/api/templates/usuarios.html`
- **Related opportunities:** imp-20260801-001

### Location

Outlier — error returns the full page template, success returns the row partial:

`bases/xtreme_system/api/routes/ui_routes/usuarios.py:130` — `ui_usuario_excluir`

```python
def ui_usuario_excluir(
    user_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    if user_id == user.id:
        return templates.TemplateResponse(
            request,
            "usuarios.html",
            _usuarios_ctx(session, user, erro="não pode excluir a si mesmo"),
            status_code=400,
        )
    obj = found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj, user.id)
```

Pattern it should match — the factory renders the same partial on both branches:

`bases/xtreme_system/api/crud_ui/routes.py:857` — `delete_list_response`

```python
def delete_list_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    list_partial_template: str,
    *,
    user: usuario.Usuario,
    list_key: str,
    ctx_list: CtxList[EntityT],
    listing: ListingSpec[EntityT],
    erro: str | None = None,
```

### Description

The delete button posts via HTMX and expects the `_linhas_usuarios.html` `<tbody>` fragment — which
is what the success branch returns (`usuarios.py:142-144`). The self-delete guard instead returns
`usuarios.html`, the full page (it carries the page-level `erro` alert block at
`templates/usuarios.html:22` and extends `base.html`), with status 400. HTMX swaps that entire
document into whatever the `hx-target` is, nesting a complete page inside the current one.

The factory never does this: `delete_list_response` takes a single `list_partial_template` and uses
it for both the 200 and the 409 branch (`crud_ui/routes.py:918-948`), differing only in `status_code`
and `erro`. `veiculos.py:305-331` follows the same rule.

### Why it matters

The user sees a duplicated page — header, nav, and table rendered inside the existing table region —
instead of an inline error. It is also the only place in the app where the response template depends
on success vs failure, so a client cannot assume "this endpoint returns the rows partial".

### Concrete fix

Return `_linhas_usuarios.html` on the guard branch, keeping `status_code=400` and passing the message
through the same key the partial renders (see imp-20260801-001).

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Both branches are in one function; the template names differ literally.
  - Confirmed `usuarios.html` is a full page (it carries the page-level `erro` alert block).
- **Weaknesses:**
  - Did not read the `hx-target` on the delete button in `usuarios.html`, so the exact visual result
    is inferred from the success branch's use of the partial.
- **Suggested checks:**
  - Attempt self-delete from the UI and inspect the swapped DOM.

## imp-20260801-007 — Success toast/close-modal `HX-Trigger` emitted inconsistently across equivalent write flows

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, htmx, response-headers
- **Files affected:** `bases/xtreme_system/api/crud_ui/responses.py`, `bases/xtreme_system/api/crud_ui/routes.py`, `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-015

### Location

Outlier — sale-closing success returns a raw `TemplateResponse`, bypassing `success_response`:

`bases/xtreme_system/api/routes/ui_routes/vendas.py:600` — `_confirmar_fechamento_venda`

```python
            status_code=400,
        )
        response.headers["HX-Retarget"] = "#modal"
        response.headers["HX-Reswap"] = "innerHTML"
        return response
    vendas = venda.list_all(session, limit=limit, offset=offset)
    return templates.TemplateResponse(
        request,
        "_vendas_ok.html",
        {"user": user, "vendas": vendas, **_ctx_lista_vendas(session, vendas)},
    )
```

Pattern it should match — the shared helper that stamps the success events:

`bases/xtreme_system/api/crud_ui/responses.py:29` — `success_response`

```python
def success_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    context: dict[str, Any],
) -> HTMLResponse:
    """Render a successful HTMX response with shared toast and modal behavior."""
    response = templates.TemplateResponse(request, template, context)
    if request.headers.get("HX-Request"):
        response.headers["HX-Trigger"] = json.dumps(_HTMX_SUCCESS_EVENTS)
    return response
```

### Description

`success_response` is the codebase's declared convention for "a write succeeded": it fires the
`htmx:toast` and `htmx:close-modal` events defined in `_HTMX_SUCCESS_EVENTS`
(`crud_ui/responses.py:16-19`) via `HX-Trigger`. It is used by the factory's create and update routes
(through `ok_response`/`write_ok_response`, `crud_ui/routes.py:654-662`) and by the hand-written
deletes in `usuarios.py:142`, `perfis.py:196`, and `investidores.py:303`.

Three equivalent success paths skip it and return a bare `TemplateResponse`, so no toast fires and
any open modal stays open:

- `vendas.py:605-609` — closing a sale (`_confirmar_fechamento_venda`), a modal flow.
- `lancamentos.py:224-231` — deleting a lançamento, while create/update in the same file go through
  `_ok_lancamentos`.
- Every factory-generated **delete** — `delete_list_response` calls `list_response`
  (`crud_ui/routes.py:873`), which never sets `HX-Trigger`, whereas the hand-written deletes for
  usuarios/perfis/investidores do.

### Why it matters

Users get a confirmation toast when deleting an investidor but not when deleting a vehicle; the
sale-closing modal stays on screen after a successful close, looking like the action did not take.
Client-side listeners bound to `htmx:toast`/`htmx:close-modal` fire for some resources and not
others, so no single front-end rule covers "write succeeded".

### Concrete fix

Route the three paths through `success_response`: replace the raw `TemplateResponse` in
`vendas.py:605` and `lancamentos.py:224`, and give `delete_list_response` a `success: bool = True`
flag that stamps `HX-Trigger` on the non-error branch.

### Potential savings

Lets the front end bind toast and modal-close behavior once to `HX-Trigger` instead of adding
per-flow handlers.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Verified `success_response` is the shared convention and identified each call site that bypasses
    it.
- **Weaknesses:**
  - For the upload modals (`veiculos_imagens.py`, `veiculos_documentos.py`, etc.) the omission is
    likely deliberate — those modals must stay open after an upload — so they are excluded here
    rather than flagged.
  - Whether the factory delete's missing toast is intentional was not documented anywhere.
- **Suggested checks:**
  - Confirm with the product owner whether delete should toast for all resources or none.

## imp-20260801-008 — Users are the only resource whose update posts to `/{id}/editar` instead of `/{id}`

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** medium
- **Tags:** api-consistency, naming, routing
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/usuarios.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-009

### Location

Outlier — `POST /ui/usuarios/{user_id}/editar` collides with the GET form route of the same path:

`bases/xtreme_system/api/routes/ui_routes/usuarios.py:228` — `ui_usuario_editar`

```python
@app.post("/ui/usuarios/{user_id}/editar")
def ui_usuario_editar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str | None, Form()] = None,
    nome: Annotated[str | None, Form()] = None,
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.funcionario,
    ativo: Annotated[bool, Form()] = True,
    perfil_id: Annotated[int | None, Form()] = None,
```

Pattern it should match — every other resource updates at `POST {prefix}/{item_id}`:

`bases/xtreme_system/api/crud_ui/routes.py:758` — `register_update_route._atualizar`

```python
    @app.post(f"{prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = found(module.get(session, item_id), config.label)
        form_data = await request.form()
        dados_form = config.parse_form(form_data)
        perfil.filtrar_campos_form_ocultos(user, config.pagina, dados_form)
        try:
```

### Description

The app has a uniform UI route convention: `GET {prefix}/{id}/editar` returns the form,
`POST {prefix}/{id}` applies the update. It holds for the factory (`crud_ui/routes.py:595` GET,
`758` POST), perfis (`perfis.py:87` GET, `142` POST), investidores (`investidores.py:181` GET,
`253` POST), lançamentos (`lancamentos.py:154` GET, `192` POST), and veículos (`veiculos.py:248` GET,
`365` POST).

Usuarios is the sole exception: `GET /ui/usuarios/{user_id}/editar` (`usuarios.py:216`) **and**
`POST /ui/usuarios/{user_id}/editar` (`usuarios.py:228`) share a path, and there is no
`POST /ui/usuarios/{user_id}`. Its create/update handlers also take individual `Form()` parameters
rather than parsing `await request.form()` like every other write handler.

### Why it matters

Any generic form component or template macro that builds `hx-post="{{ prefix }}/{{ item.id }}"` from
the resource prefix — which is exactly how the shared `_form_*.html` templates are parameterized —
produces a URL that 405s for usuarios. It is also the one route where the same path serves two
semantically different operations, so route-based logging and permission mapping have to special-case
it.

### Concrete fix

Add `POST /ui/usuarios/{user_id}` as the update route (keeping `GET .../editar` for the form), and
have the old `POST .../editar` delegate to it for one release before removal. Because the form
template's action must change in the same commit, treat this as a coordinated change rather than a
silent swap.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Verified the convention across five independent resources plus the factory, and confirmed no
    `POST /ui/usuarios/{user_id}` exists in the route sweep.
- **Weaknesses:**
  - Did not read `_form_usuario_editar.html` to confirm its `hx-post` target, so the "generic macro"
    consequence is inferred from how sibling forms are parameterized.
- **Suggested checks:**
  - Grep the templates for `hx-post` on the usuario edit form before changing the route.

## imp-20260801-009 — Clientes lives under two path prefixes and redirects from its canonical list URL

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** api-consistency, naming, routing
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/clientes.py`
- **Related opportunities:** imp-20260801-008

### Location

Outlier — the resource root is a redirect, and the vehicles sub-resource hangs off the long prefix:

`bases/xtreme_system/api/routes/ui_routes/clientes.py:241` — `ui_clientes_redirect` / `ui_cliente_veiculos`

```python
@app.get("/ui/clientes")
def ui_clientes_redirect(_: UIUser) -> RedirectResponse:
    return RedirectResponse("/ui/clientes/todos", status_code=303)


@app.get("/ui/clientes/todos/{cliente_id}/veiculos")
def ui_cliente_veiculos(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
) -> HTMLResponse:
```

Pattern it should match — the sibling sub-resource on the short prefix:

`bases/xtreme_system/api/routes/ui_routes/clientes.py:185` — `ui_cliente_documentos`

```python
@app.get("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos(
    request: Request,
    session: SessionDep,
    user: _EditarClienteDep,
    cliente_id: int,
) -> HTMLResponse:
    return _documentos_modal(request, session, user, cliente_id)


@app.post("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos_upload(
    request: Request,
```

### Description

The CRUD-UI factory for clientes is registered at `prefix="/ui/clientes/todos"`
(`clientes.py:376-377`), so list/create/update/delete/export all live under `/ui/clientes/todos`,
while `/ui/clientes` is only a 303 redirect. Every other resource is registered at `/ui/{resource}`
directly — `/ui/veiculos`, `/ui/investidores`, `/ui/perfis`, `/ui/usuarios`, `/ui/auditoria`.

Worse, the two cliente sub-resources disagree with each other: documents hang off the short prefix
(`/ui/clientes/{cliente_id}/documentos`, line 185) while vehicles hang off the long one
(`/ui/clientes/todos/{cliente_id}/veiculos`, line 246). Both take the same `cliente_id` and open a
modal for the same entity.

### Why it matters

Nothing in the code says which prefix is canonical, so every new cliente sub-resource is a coin
flip, and the two existing ones already went opposite ways. A client building URLs from a single
`route_prefix` variable — which `_ctx_lista_cliente` does supply (`clientes.py:101`) — will construct
a valid documents URL or a valid vehicles URL, never both. The 303 on `/ui/clientes` also means every
entry to the clientes screen costs an extra round trip.

### Concrete fix

Pick `/ui/clientes` as the canonical prefix, register the factory there, and move
`/ui/clientes/todos/{cliente_id}/veiculos` to `/ui/clientes/{cliente_id}/veiculos`. Keep
`/ui/clientes/todos*` as redirects for one release since bookmarks and templates reference it.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - Verified the factory registration prefix and both sub-resource paths directly.
- **Weaknesses:**
  - `_register_clientes_page` is a parameterized helper, suggesting more than one clientes page may
    be registered (e.g. a filtered variant) — only the `/ui/clientes/todos` call was read, so
    "todos" may exist to disambiguate sibling pages, which would be a legitimate reason for the long
    prefix.
  - Templates referencing `/ui/clientes/todos` were not enumerated, so the migration surface is
    unmeasured.
- **Suggested checks:**
  - Read the remaining `_register_clientes_page(...)` invocations after `clientes.py:385` to see
    whether other cliente pages exist.

## imp-20260801-010 — Backup import/export map the same error class to 200, 409, and 500

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, status-codes, error-shape
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
- **Related opportunities:** imp-20260801-011

### Location

Outlier — import failure of `ExportacaoError` returns the default 200:

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:279` — `ui_configuracoes_importar`

```python
    except exportacao.RestoreEmAndamentoError as exc:
        return HTMLResponse(f"<p>{exc}</p>", status_code=409)
    except exportacao.ExportacaoError as exc:
        try:
            with database_traffic_lock():
                config = whatsapp.get_config(session)
                return _pagina_empresa(
                    request,
                    session,
                    user,
                    empresa.get_config(session),
                    config=config,
```

Pattern for the same exception class one function above:

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:239` — `ui_configuracoes_exportar`

```python
    except exportacao.ExportacaoError as exc:
        os.unlink(tmp_path)
        config = whatsapp.get_config(session)
        return _pagina_empresa(
            request,
            session,
            user,
            empresa.get_config(session),
            config=config,
            erro=str(exc),
            aba="banco",
            status_code=500,
```

### Description

`ExportacaoError` is handled twice in the same file with different status codes: `status_code=500` on
export (line 250) and the default `status_code=200` on import (`_pagina_empresa` defaults to 200 at
line 143). A third failure, `RestoreEmAndamentoError`, returns a bare `<p>{exc}</p>` fragment with 409
(line 280) instead of the `configuracoes.html` page every other branch in the file renders.

Elsewhere in the codebase a user-correctable write failure is a 400 with the page or form re-rendered
(`crud_ui/routes.py:696`, `veiculos.py:387`, `investidores.py:202`), and a conflict is a 409 that
still returns the normal template (`crud_ui/routes.py:930`, `perfis.py:193`).

### Why it matters

An import that fails returns HTTP 200, so monitoring, HTMX `hx-on::after-request` status checks, and
any automation treating 2xx as success will record a failed database restore as successful. The 500
on export makes a user-visible, user-actionable failure look like an application crash. And the bare
`<p>` fragment on 409 replaces the whole configuration screen with one line of text.

### Concrete fix

Give the import's `ExportacaoError` branch `status_code=400`, lower the export branch from 500 to
400 (it is a reportable operational failure, not a crash), and render `RestoreEmAndamentoError`
through `_pagina_empresa(..., erro=str(exc), status_code=409)` like every other branch in the file.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - All three branches, plus `_pagina_empresa`'s `status_code: int = 200` default, read directly.
- **Weaknesses:**
  - Whether 500 was deliberately chosen for `dump_database_to_file` (an infrastructure failure, not
    user input) is arguable; the inconsistency with the import path is the firmer part of the claim.
- **Suggested checks:**
  - Confirm which `ExportacaoError` cases are user-correctable (bad dump file) vs infrastructural
    (pg_dump missing) before settling on one code.

## imp-20260801-011 — Database export is the only export served over POST

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, http-methods, exports
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-010

### Location

Outlier — a read-only download exposed as `POST`:

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:228` — `ui_configuracoes_exportar`

```python
@app.post("/ui/configuracoes/exportar")
def ui_configuracoes_exportar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> Response:
    detach_request_session(request, keep=(user,))
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
    try:
        exportacao.dump_database_to_file(tmp_path)
```

Pattern it should match — the shared export route factory:

`bases/xtreme_system/api/crud_ui/routes.py:520` — `register_export_route._exportar`

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
```

### Description

Every other export in the app is `GET {prefix}/exportar`: the factory (`crud_ui/routes.py:520`,
`crud_ui/simple.py:73`), usuarios (`usuarios.py:74`), investidores (`investidores.py:145`),
lançamentos (`lancamentos.py:117`), auditoria (`auditoria.py:143`), and the DRE report
(`relatorios.py:124`). `/ui/configuracoes/exportar` is the sole `POST`, even though it takes no body
and only reads state to produce a `FileResponse` download.

### Why it matters

The endpoint cannot be a plain `<a href>` download link, cannot be bookmarked or retried from the
browser, and triggers a form-resubmission prompt on refresh. It also breaks the one rule a client can
otherwise rely on — "exports are GET `{prefix}/exportar`" — meaning a shared export button component
cannot cover this screen.

### Concrete fix

Register the handler as `@app.get("/ui/configuracoes/exportar")` and update the template's form/link
to a GET. Keep the POST route as an alias for one release if the current button is a form submit.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Verified six independent `GET .../exportar` routes and confirmed the handler takes no request
    body.
- **Weaknesses:**
  - POST may have been chosen deliberately because a full `pg_dump` is expensive and POST discourages
    prefetch/caching — a defensible reason that is not documented in the code.
- **Suggested checks:**
  - Confirm with the author whether POST was chosen to prevent accidental repeat dumps.

## imp-20260801-012 — Fechamento JSON endpoints declare no response model, unlike every factory route

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, openapi, discoverability, response-shape
- **Files affected:** `bases/xtreme_system/api/routes/json.py`, `bases/xtreme_system/api/route_factories.py`
- **Related opportunities:** imp-20260801-013, imp-20260801-014

### Location

Outlier — bare decorators returning untyped dicts:

`bases/xtreme_system/api/routes/json.py:266` — `listar_fechamentos_vendas`

```python
@app.get(
    "/fechamentos-vendas",
)
def listar_fechamentos_vendas(
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=JSON_LIST_LIMIT_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    try:
        fechamentos = fechamento_venda.list_all(session, limit=limit, offset=offset)
    except fechamento_venda.FechamentoVendaError as exc:
```

Pattern it should match — the factory declares `responses` even when masking forces
`response_model=None`:

`bases/xtreme_system/api/route_factories.py:115` — `register_crud_routes`

```python
    response_model = None if pagina else list[read_schema]  # type: ignore[valid-type]
    list_response_model: Any = list[read_schema]  # type: ignore[valid-type]
    list_responses: dict[int | str, dict[str, Any]] | None = (
        {200: {"model": list_response_model}} if pagina else None
    )
    read_responses: dict[int | str, dict[str, Any]] | None = (
        {200: {"model": read_schema}} if pagina else None
    )
    create_responses: dict[int | str, dict[str, Any]] | None = (
        {201: {"model": read_schema}} if pagina else None
    )

    @app.get(prefix, response_model=response_model, responses=list_responses)
```

### Description

The factory solved exactly this problem: when per-field permission masking forces
`response_model=None`, it still passes `responses={200: {"model": read_schema}}` so the OpenAPI schema
documents the real shape. All factory-backed resources (investidores, veículos, clientes, vendas,
compras, lançamentos) get typed schemas this way.

Three hand-written fechamento endpoints — `GET /vendas/{venda_id}/fechamento/preview`
(`json.py:238-245`), `GET /fechamentos-vendas` (`266-279`), and `GET /fechamentos-vendas/{id}`
(`282-290`) — apply the same masking via `_fechamento_json`/`_fechamento_preview_json` but declare
neither `response_model` nor `responses`. Their OpenAPI entries are an untyped object. The sibling
`POST /vendas/{venda_id}/fechamento` in the same block *does* declare
`response_model=fechamento_venda.FechamentoVendaRead` (`json.py:248-252`), so the file contradicts
itself.

### Why it matters

A client generating types from the OpenAPI schema gets `FechamentoVendaRead` for the create response
and `any`/`object` for the read and list responses of the same resource. The actual contract — a
`FechamentoVendaRead` minus the fields the caller may not see — is discoverable only by reading
`_fechamento_json`.

### Concrete fix

Add `responses={200: {"model": fechamento_venda.FechamentoVendaRead}}` to the two
`/fechamentos-vendas` routes and `{200: {"model": fechamento_venda.FechamentoVendaPreview}}` to the
preview route, mirroring `read_responses` in `route_factories.py:120-122`.

### Potential savings

Restores generated client types for three endpoints without changing runtime behavior.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - The factory's `responses=` workaround for masked routes is explicit, so the intended convention
    is not inferred.
  - The contradiction with `POST /vendas/{venda_id}/fechamento` sits in the same file.
- **Weaknesses:**
  - `FechamentoVendaPreview` exists as a type (`json.py:200`) but its use as a response model was
    not verified against its field definitions.
- **Suggested checks:**
  - Regenerate the OpenAPI schema and diff the three route entries before and after.

## imp-20260801-013 — Hand-written `/usuarios` JSON routes diverge from the CRUD contract on body format, conflict handling, and verbs

- **Impact:** Medium
- **Category:** Architecture and design
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** api-consistency, status-codes, error-shape, http-methods
- **Files affected:** `bases/xtreme_system/api/routes/json.py`, `bases/xtreme_system/api/route_factories.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-012

### Location

Outlier — a `Form()` body on a JSON API and a 400 for a refused delete:

`bases/xtreme_system/api/routes/json.py:108` — `deletar_usuario` / `trocar_senha_usuario`

```python
@app.delete("/usuarios/{user_id}", status_code=204)
def deletar_usuario(
    user_id: int, session: SessionDep, current: CurrentUser, _: AdminUser
) -> None:
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="não pode excluir a si mesmo")
    obj = found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj, current.id)


@app.post("/usuarios/{user_id}/senha", status_code=204)
def trocar_senha_usuario(
```

Pattern it should match — the factory maps constraint failures to 409:

`bases/xtreme_system/api/route_factories.py:221` — `_delete_atomic`

```python
    def _delete_atomic(item_id: int, session: Session, actor_id: int | None) -> None:
        obj = found(module.get(session, item_id), label)
        if before_delete:
            before_delete(session, obj, actor_id)
        if handle_delete_error:
            try:
                module.delete(session, obj, actor_id)
            except IntegrityError:
                raise HTTPException(
                    status_code=409, detail=delete_conflict_detail(label)
                ) from None
```

### Description

`/usuarios` is the only JSON resource not built by `register_crud_routes`, and it diverges on four
points against the six resources that are:

1. **Body format** — `POST /usuarios/{user_id}/senha` takes `nova_senha: Annotated[str, Form()]`
   (`json.py:123`), so it requires `application/x-www-form-urlencoded` while every other JSON write
   takes a Pydantic model as JSON (`route_factories.py:157`, `190`).
2. **Conflict status** — creating a user with a duplicate username reaches `usuario.create` with only
   `SenhaFracaError`/`UsuarioValidationError` caught (`json.py:92-95`); an `IntegrityError` is not
   translated, whereas `_create_atomic` wraps every factory create in `safe_write(...,
   conflict_msg=...)` yielding 409 (`route_factories.py:168-181`).
3. **Refusal status** — self-deletion returns 400 (`json.py:113`) where the factory returns 409 for
   a delete the server refuses (`route_factories.py:228-231`).
4. **Missing verb** — there is no `PATCH /usuarios/{user_id}`, though every other resource exposes
   one (`route_factories.py:183`).

### Why it matters

A client that has one JSON write helper (set `Content-Type: application/json`, treat 409 as
"conflict, show the field error", treat 400 as "bad input") breaks on all four points for usuarios:
the password change 422s on a JSON body, a duplicate username surfaces as an unhandled 500 rather
than a 409, and there is no way to update a user at all through the JSON API.

### Concrete fix

Smallest useful step is the conflict mapping and the verb: wrap `usuario.create` in `safe_write` so
duplicates return 409 like every other resource, and change self-delete from 400 to 409. Switching
`nova_senha` to a Pydantic body and adding `PATCH /usuarios/{user_id}` are breaking changes and need
a deprecation window — keep the `Form()` variant accepting both content types for one release.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - All four divergences read directly against the factory implementation they should match.
- **Weaknesses:**
  - Whether `usuario.create` raises `IntegrityError` (vs pre-checking the username and raising
    `UsuarioValidationError`) was not verified — `components/xtreme_system/usuario/core.py` was not
    read, so the 500-on-duplicate claim is unconfirmed.
  - `/usuarios` may be intentionally hand-written because password handling does not fit the CRUD
    schema shape; that would justify the `Form()` body but not the status-code divergences.
- **Suggested checks:**
  - Read `usuario.create` to see whether a duplicate username is pre-checked.
  - `POST /usuarios` twice with the same username and record the status code.

## imp-20260801-014 — Vendas and compras write handlers ignore or unbound the shared list-state contract

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, pagination, validation
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/crud_ui/routes.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-012

### Location

Outlier A — unvalidated, unbounded `limit`/`offset` as plain ints:

`bases/xtreme_system/api/routes/ui_routes/vendas.py:416` — `_criar_venda`

```python
@app.post("/ui/vendas")
async def _criar_venda(
    request: Request,
    session: SessionDep,
    user: _CadastrarVendaDep,
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    form = await request.form()
    dados_form = dict(form)
    resultado = preparar_venda(session, form, user)
```

Outlier B — list state discarded entirely after a compra write:

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

Pattern both should match — the factory re-derives list state from the request:

`bases/xtreme_system/api/crud_ui/routes.py:652` — `write_ok_response`

```python
    state = _current_list_state(request)
    lista = query_list(session, module, listing=listing, state=state)
    return ok_response(
        templates,
        request,
        ok_partial_template,
        user=user,
        list_key=list_key,
        lista=lista,
        ctx_list=ctx_list(session, lista),
    )
```

### Description

After a successful write, the factory rebuilds the list the user was actually looking at by parsing
the current list state off the request (`_current_list_state`, `crud_ui/routes.py:229`) and applying
the listing's bounds.

Two hand-written resources diverge. `_criar_venda` (`vendas.py:421-422`), `_atualizar_venda`
(`vendas.py:463-464`) and `_confirmar_fechamento_venda` (`vendas.py:566-567`) declare
`limit: int = 50, offset: int = 0` as bare ints with no `Query(ge=1, le=LIST_LIMIT_MAX)` bound, then
pass them straight to `venda.list_all(session, limit=limit, offset=offset)` (`vendas.py:604`) — so
`?limit=100000` on a create returns the entire vendas table. `_ok_compra` goes further and calls
`compra.list_all(session)` with no bound and `ctx_list={}`, discarding sort, filter, and page.

### Why it matters

A caller can turn any vendas write into a full-table dump by appending a query parameter, bypassing
the `LIST_LIMIT_MAX` ceiling that governs every list route. And after creating a compra, the user's
table resets to an unsorted, unfiltered, unpaginated first render — the write silently loses the view
state that the factory preserves for every other resource.

### Concrete fix

Annotate the vendas parameters as `Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)]` / `Query(ge=0)`,
and change `_ok_compra` to derive state via `_current_list_state(request)` and a `ListingSpec` for
compras, as `write_ok_response` does.

### Potential savings

Closes an unbounded-response path on three write endpoints and makes the post-write refresh behave
identically across all resources.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Verified the bare-int signatures, the `list_all` call that consumes them, and the factory helper
    they diverge from.
- **Weaknesses:**
  - Whether `venda.list_all` clamps its own `limit` internally was not checked; if it does, the
    unbounded-dump consequence is reduced to a validation inconsistency.
- **Suggested checks:**
  - Read `venda.list_all` in `components/xtreme_system/venda/core.py` for an internal cap.

## imp-20260801-015 — Configurações signals success via a `sucesso` context key instead of the shared toast trigger

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** api-consistency, htmx, response-headers
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/crud_ui/responses.py`
- **Related opportunities:** imp-20260801-007

### Location

Outlier — a bespoke success channel in the template context:

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:133` — `_pagina_empresa`

```python
def _pagina_empresa(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    config_empresa: empresa.EmpresaConfig,
    *,
    config: whatsapp.WhatsappConfig | None = None,
    erro: str | None = None,
    sucesso: str | None = None,
    aba: str = "empresa",
    status_code: int = 200,
) -> HTMLResponse:
```

Pattern it should match — the app-wide success signal:

`bases/xtreme_system/api/crud_ui/responses.py:207` — `ok_response`

```python
def ok_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    *,
    user: object,
    list_key: str,
    lista: list[EntityT],
    ctx_list: dict[str, Any],
) -> HTMLResponse:
    return success_response(
        templates,
```

### Description

Every write-success in the app announces itself through `HX-Trigger` with the
`htmx:toast`/`htmx:close-modal` events (`crud_ui/responses.py:16-39`). Configurações invents a third
mechanism: a `sucesso` string baked into the template context, set at `configuracoes.py:87`
("Configurações salvas."), `configuracoes.py:126` ("Dados da empresa salvos."), and
`configuracoes.py:311` ("Dados importados com sucesso."). No other module in `ui_routes/` passes a
`sucesso` key.

This is a distinct mechanism from the `msg` key the list partials render, so the app now has three
ways to say "this worked": `HX-Trigger`, `msg`, and `sucesso`.

### Why it matters

Success feedback on the configurações screens renders as inline page markup rather than the toast the
user sees everywhere else, so the same action gives different feedback depending on the screen. Any
change to the toast component — wording, duration, dismissal, accessibility role — has to be applied
in `configuracoes.html` separately or that screen silently drifts.

### Concrete fix

Have `_pagina_empresa` stamp `HX-Trigger` with `{"htmx:toast": {"message": sucesso}}` when `sucesso`
is set and the request carries `HX-Request` — the same shape `success_response` uses — and drop the
`sucesso` block from `configuracoes.html` once the toast covers it. This needs a small change to let
`success_response` carry a per-call message instead of the fixed `_HTMX_SUCCESS_EVENTS` string.

### Potential savings

Consolidates three success-notification mechanisms into one, so toast styling and behavior live in a
single place.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Verified `sucesso` appears only in `configuracoes.py`, and that `_HTMX_SUCCESS_EVENTS` is the
    convention used by both the factory and the hand-written resources.
- **Weaknesses:**
  - `success_response`'s toast message is currently a fixed string; carrying a per-call message
    requires a small signature change that was not designed out here.
  - `configuracoes.html` was not read, so how prominently `sucesso` renders today is unknown.
- **Suggested checks:**
  - Read the `sucesso` block in `configuracoes.html` to confirm a toast is an acceptable replacement.

## Discarded candidates

### Upload modals omit the success `HX-Trigger`

`veiculos_documentos.py:105`, `veiculos_imagens.py:122`, `veiculos_procuracao.py`, and
`compras.py:226` all return `_*_modal(..., action_oob=True)` without `success_response`, so no toast
fires and the modal is not closed. Unlike the retained toast finding, this is almost certainly
deliberate — an upload modal must stay open so the user can add more files, and `htmx:close-modal`
would fight that. All four sub-resources agree with each other, so there is no inconsistency to
resolve.

### `AUDITORIA_LIMIT_MAX` duplicates `JSON_LIST_LIMIT_MAX`

`json.py:42` defines `AUDITORIA_LIMIT_MAX = 200`, the same value as `JSON_LIST_LIMIT_MAX`
(`route_factories.py:31`). Since both caps are identical and the auditoria route is correctly bounded,
no client-visible inconsistency exists — this is a duplication nit, not an API-contract issue.

### 404 entity labels differ for the same entity

`found(investidor.get(...), "Investidores")` at `investidores.py:185` and `investidores.py:290`
versus `found(investidor.get(...), "Investidor")` at `lancamentos.py:121` and `lancamentos.py:142`
produce different 404 detail strings for the same entity. Real but cosmetic: the status code and body
shape are identical and no client branches on the message text. Low impact, so excluded per the
High/Medium-only bar.

### `POST /ui/vendas/{id}/contrato/regerar` returns a redirect chain

`vendas.py:521-533` returns a 303 to `GET /ui/vendas/{id}/contrato`, which itself returns a
`RedirectResponse` to the stored document URL. This differs from the fragment-returning convention of
other POST handlers, but it is a download flow rather than a form submission, and without reading the
template's `hx-*` attributes there is no evidence the redirect actually breaks a swap. Too uncertain
to retain at Medium.

### `/health` returns a raw `JSONResponse` with no response model

`json.py:47-66` declares no `response_model`, so its `{"status", "database", "database_target"}` shape
is undocumented in OpenAPI. Unlike the fechamento finding this endpoint has no sibling that documents
a contract, no schema type exists for it, and health checks are consumed by probes that match on
status code rather than generated types. Low impact.
