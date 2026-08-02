# Improvement opportunities

- **Generated:** 2026-08-01T12:47:34-03:00
- **Total:** 13

## imp-20260801-001 — Cover the lançamentos UI write surface and its three "automatic entry" guards

- **Impact:** High
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** testing, coverage, authorization, data-integrity, caixa
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`, `components/xtreme_system/workflow/core.py`, `tests/test_ui.py`, `tests/test_fechamento_venda.py`
- **Related opportunities:** imp-20260801-011

### Location

`bases/xtreme_system/api/routes/ui_routes/lancamentos.py:213` — `ui_lancamento_excluir`

```python
def ui_lancamento_excluir(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = found(caixa.get(session, lancamento_id), "Lançamento")
    if is_lancamento_automatico(obj):
        raise NaoAutorizadoError
    caixa.delete(session, obj, user.id)
```

### Description

A full-suite coverage run (`437 passed, 1 skipped`, 89.09% overall) puts this module at **48% — the
lowest of any file in the codebase**. Missing lines are `58-59, 78-83, 113, 121-123, 142-143,
162-165, 180-189, 200-209, 220-224`: that is the entire create/update/delete write surface plus all
three `is_lancamento_automatico(obj)` → `raise NaoAutorizadoError` guards (`:163-164` on edit-form,
`:201-202` on update, `:221-222` on delete).

Those guards are the only thing stopping an admin from hand-editing or deleting cash-ledger entries
that the system generated itself (vehicle cost, sale closing). The equivalent rule is tested on the
JSON API — `tests/test_fechamento_venda.py:432` asserts `PATCH /lancamentos-caixa/{id}` returns 400
for an `origem == "fechamento_venda"` entry — but the UI routes have no such test. Deleting any of
the three `if is_lancamento_automatico(obj)` lines would leave the whole suite green.

### Why it matters

Automatic lançamentos are derived values that mirror a compra or fechamento. Letting one be edited
or deleted directly desynchronizes the investor cash balance from the transactions that produced it,
with no audit trail explaining the divergence and no way to recompute it. Because the JSON API is
tested and the UI is not, the codebase currently reads as if the rule is covered when only half of
it is.

### Concrete fix

Add three tests to `tests/test_ui.py` next to the existing investidor/lançamento helpers, seeding an
automatic entry through the normal compra flow rather than constructing one by hand.

### Example

```python
def test_ui_lancamento_automatico_nao_pode_ser_editado(client: TestClient) -> None:
    _login_admin(client)
    _seed_compra(client)  # gera lançamento origem != manual
    automatico = next(
        lanc for lanc in caixa.list_all(session)
        if lanc.origem != caixa.OrigemLancamento.manual
    )
    resp = client.post(
        f"/ui/investidores/{automatico.investidor_id}/lancamentos/{automatico.id}/excluir"
    )
    assert resp.status_code == 403
    assert caixa.get(session, automatico.id) is not None  # ainda existe
```

Mirror it for `GET .../editar` and `POST .../{lancamento_id}`, and add one happy-path test that a
`manual` entry *can* be created, updated, and deleted — that single pair covers most of the missing
48%.

### Potential savings

Closes the largest single coverage hole in the repo and prevents silent corruption of investor cash
balances via the UI.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Coverage figure is from a real run in this session, not the stale committed `.coverage`.
  - Missing-line list places the gap precisely on the three guards, verified against the source.
  - The contrast with the tested JSON-API equivalent is confirmed at `tests/test_fechamento_venda.py:432`.
- **Weaknesses:**
  - The exact status code raised by `NaoAutorizadoError` was not confirmed; the example assumes 403.
  - `_seed_compra` exists in `tests/test_ui.py` but was not read in full, so the seeding helper may need adjusting.
- **Suggested checks:**
  - Confirm the `NaoAutorizadoError` status code before writing the assertion.

## imp-20260801-002 — Test the shared simple-CRUD factory's IntegrityError/409 branches

- **Impact:** High
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** testing, coverage, rollback, integrity, factory
- **Files affected:** `bases/xtreme_system/api/crud_ui/simple.py`, `bases/xtreme_system/api/crud_ui/responses.py`, `tests/test_route_factories_ui.py`
- **Related opportunities:** imp-20260801-004, imp-20260801-011

### Location

`bases/xtreme_system/api/crud_ui/simple.py:136` — `_atualizar`

```python
        try:
            module.update(session, obj, update_schema(nome=nome), user.id)
        except IntegrityError:
            return rollback_integrity_error_response(
                session,
                lambda: templates.TemplateResponse(
                    request,
                    "_form_simples.html",
                    _form_ctx(obj, write_conflict_detail(titulo)),
                    status_code=409,
                ),
            )
```

### Description

`crud_ui/simple.py` sits at 61% with missing lines `41, 70, 75-76, 84, 92-93, 101, 119, 127-148,
156-169`. The two large blocks — `127-148` and `156-169` — are the `except IntegrityError` handlers
of `_atualizar` and `_excluir`, and `119` is the same handler in `_criar`. **All three
conflict/rollback paths of this factory are untested.**

This is a factory: it generates the create/update/delete routes for every "simple" name-only entity
in the app from one code path. A regression in any of these three branches — a dropped
`session.rollback()`, a wrong status code, a template that no longer renders — breaks every entity
built on it simultaneously, and the current suite reports green.

Note this is not the same as the `safe_write`/`get_session` rollback contract, which *is* genuinely
well covered (`tests/test_database_session.py`, `tests/test_request_context.py`,
`tests/test_route_factories_atomicity.py`). `rollback_integrity_error_response` itself is executed by
some other caller (`responses.py:137-138` is covered). What is missing is any test that the *simple
factory* wires into it correctly.

### Why it matters

`rollback_integrity_error_response` calls `session.rollback()` before building the response. If the
factory ever returns a response without going through it, `get_session` later attempts a commit on a
dirty session — exactly the failure mode called out in this project's `CLAUDE.md`. Because one
factory backs many entities, the blast radius of an untested regression here is the widest in the
codebase relative to its size.

### Concrete fix

Add one parametrized test to `tests/test_route_factories_ui.py`, which already imports
`IntegrityError` (`:15`) and has the fixture scaffolding for factory-generated routes.

### Example

```python
def test_simple_factory_conflito_no_update_faz_rollback_e_retorna_409(...):
    # cria duas entidades e tenta renomear a segunda para o nome da primeira
    resp = client.post(f"{ui_prefix}/{segundo.id}", data={"nome": primeiro.nome})
    assert resp.status_code == 409
    assert "já existe" in resp.text
    assert not session.dirty and not session.new   # sessão limpa após rollback
    session.refresh(segundo)
    assert segundo.nome != primeiro.nome           # nada foi persistido
```

The `assert not session.dirty and not session.new` line is the important one — it asserts the
rollback happened, not merely that a 409 was rendered.

### Potential savings

One test protects the conflict-handling path of every entity generated by this factory.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Missing-line ranges map exactly onto the three `except IntegrityError` blocks, read and verified.
  - Correctly distinguishes this gap from the `safe_write` contract, which was checked and found covered.
- **Weaknesses:**
  - Which concrete entities are registered through this factory was not enumerated, so "many entities" is inferred from the factory shape rather than counted.
- **Suggested checks:**
  - Grep the callers of the simple-CRUD registration function to size the blast radius precisely.

## imp-20260801-003 — Exercise the idempotency-key branch in the compra conflict handler

- **Impact:** High
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** testing, coverage, idempotency, concurrency, rollback
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/compras.py`, `tests/test_api_compras.py`, `tests/test_ui.py`
- **Related opportunities:** imp-20260801-010

### Location

`bases/xtreme_system/api/routes/ui_routes/compras.py:470` — `ui_compra_criar`

```python
    try:
        obj = compra.create(session, data, user.id)
        sincronizar_caixa_compra(session, obj, user.id)
        salvar_arquivos(
            session,
            upload_dir=uploads_compra_dir(obj.id),
            url_prefix=f"/static/uploads/compras/{obj.id}/comprovantes",
            create_fn=imagem_comprovante_compra.create,
            schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
            fk_field="compra_id",
            fk_id=obj.id,
            arquivos=comprovantes,
```

### Description

Coverage for `compras.py` is 81%, but the specific missing range `461-468` is the branch *inside*
the `except IntegrityError` handler that checks `idempotency_key and
compra.get_by_idempotency_key(session, idempotency_key)` and, when it matches, returns the normal
success response instead of an error.

That branch is the entire duplicate-submit protection for purchase creation: when the same
idempotency key arrives twice (double-clicked button, htmx retry, browser resubmit), the unique
constraint fires and this handler is supposed to recognize "this is my own earlier write" and return
success rather than a conflict. **No test ever drives a second request with the same idempotency
key.**

### Why it matters

If this branch regresses, a duplicate submit surfaces to the user as a spurious error on a purchase
that actually succeeded — or, worse, if the condition inverts, a genuinely conflicting write gets
reported as success. Purchases create both a `compra` row and a synchronized caixa entry
(`sincronizar_caixa_compra`), so a mishandled retry is a money-affecting event. Idempotency logic is
also precisely the kind of code that is never exercised in manual testing, which makes automated
coverage the only realistic defense.

### Concrete fix

Add one test that posts the same compra payload twice with an identical idempotency key and asserts
the second call is a success that creates no second row.

### Example

```python
def test_compra_duplicada_com_mesma_idempotency_key_nao_duplica(client, headers):
    payload = {..., "idempotency_key": "abc-123"}
    primeira = client.post("/ui/compras", data=payload)
    segunda = client.post("/ui/compras", data=payload)

    assert primeira.status_code == 200
    assert segunda.status_code == 200          # não 409
    assert len(compra.list_all(session)) == 1  # nenhuma linha extra
    assert len(caixa.list_all(session)) == 1   # nenhum lançamento duplicado
```

The `caixa` assertion matters as much as the `compra` one — a duplicate cash entry is the damaging
outcome.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The uncovered range was identified from a real coverage run and the surrounding handler was read.
- **Weaknesses:**
  - The tail of the conditional (`compras.py:461-468`) was read only partially; the exact response returned on an idempotency hit was inferred from the visible `_ok_compra(...) if idempotency_key and ...` fragment.
  - Whether the UI form actually submits an idempotency key, or only the JSON API does, was not confirmed — if only the JSON path sets it, the test belongs in `tests/test_api_compras.py`.
- **Suggested checks:**
  - Read `compras.py:455-490` in full and confirm where `idempotency_key` is populated from before choosing the test file.

## imp-20260801-004 — Cover the three IntegrityError handlers in the perfis routes

- **Impact:** High
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** testing, coverage, rollback, authorization, perfil
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `tests/test_perfil.py`, `tests/test_api_perfil.py`
- **Related opportunities:** imp-20260801-002, imp-20260801-011

### Location

`bases/xtreme_system/api/routes/ui_routes/perfis.py:175` — `ui_perfil_excluir`

```python
def ui_perfil_excluir(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = found(perfil.get(session, item_id), "Perfil")
    try:
        perfil.delete(session, obj, user.id)
    except IntegrityError:
        return rollback_integrity_error_response(
            session,
            lambda: templates.TemplateResponse(
                request,
                "_linhas_perfis.html",
```

### Description

`perfis.py` is at 69% with missing lines `66-71, 110-111, 123-124, 146-169, 178-196`. The blocks
`146-169` and `178-196` are the `except IntegrityError` handlers of `ui_perfil_atualizar` and
`ui_perfil_excluir`; `110-111`/`123-124` are the validation-error and conflict branches of
`ui_perfil_criar`.

The domain logic in `components/xtreme_system/perfil/core.py` is at 99% and `tests/test_perfil.py`
has a genuinely good 18-test authorization matrix (`test_operacoes_sao_opt_in`,
`test_campos_de_pagina_fora_do_perfil_sao_negados`, and so on). The gap is not the policy — it is
the **HTTP layer around it**: no test creates a duplicate profile name, and no test tries to delete
a profile that still has users attached.

Note `tests/test_perfil.py:52` does test `test_delete_desvincula_usuarios_do_perfil` at the module
level, which makes the route-level behavior here ambiguous: if delete unlinks users, the
`IntegrityError` path may be unreachable in practice. Either way that is worth resolving — the
handler is currently unverified dead-or-live code.

### Why it matters

Profiles carry page and field permissions. A duplicate-name collision that is mishandled leaves a
dirty session, and a delete that half-succeeds could detach users from their permission set,
silently widening or removing access. This is authorization configuration, so failures are security
consequences rather than cosmetic ones.

### Concrete fix

Add two route-level tests to `tests/test_perfil.py`, and use the delete test to determine whether the
`IntegrityError` handler at `:178-196` is reachable at all.

### Example

```python
def test_ui_perfil_nome_duplicado_retorna_409_e_sessao_limpa(client, session):
    payload = {"nome": "Vendas", "paginas": ["veiculos"]}
    primeira = client.post("/ui/perfis", data=payload)
    assert primeira.status_code == 200

    resp = client.post("/ui/perfis", data=payload)

    assert resp.status_code == 409
    # a sessão precisa estar limpa: rollback_integrity_error_response
    # chama session.rollback() antes de montar a resposta
    assert not session.dirty and not session.new
    assert len(perfil.list_all(session)) == 1
```

If the delete-with-linked-users case proves unreachable because `perfil.delete` unlinks first, delete
the handler at `:178-196` instead of testing it.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Missing-line ranges verified against the read source; the handlers are unambiguously uncovered.
  - Correctly separates the well-tested policy layer from the untested HTTP layer instead of claiming the whole area is untested.
- **Weaknesses:**
  - Reachability of the delete handler is genuinely open, given `test_delete_desvincula_usuarios_do_perfil`; the finding may resolve to a deletion rather than a new test.
- **Suggested checks:**
  - Read `perfil.delete` to determine whether an `IntegrityError` can escape it at all.

## imp-20260801-005 — Test the database-restore failure paths in configurações

- **Impact:** High
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** testing, coverage, disaster-recovery, error-handling, backup
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `components/xtreme_system/exportacao/core.py`, `tests/test_configuracoes_backup.py`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:277` — `ui_configuracoes_restaurar`

```python
    try:
        await run_in_threadpool(exportacao.restore_database_from_file, tmp_path)
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
```

### Description

`configuracoes.py` is at 83%, and the missing range `279-295` is precisely this nested failure
handler: `ExportacaoError` → re-render the page with an error, and the inner
`DatabaseRestoreInProgressError` → 503. `tests/test_configuracoes_backup.py` is a substantial
397-line file, but its coverage lands on the success paths; the two failure branches here are never
entered.

This is the restore-from-backup flow — the code that runs when someone is recovering from data loss,
under stress, having already detached the request session (`detach_request_session`). It is the
single worst place in the application for an untested error path.

### Why it matters

If `restore_database_from_file` fails and this handler raises instead of rendering, the operator sees
a 500 with no indication of whether the database was left partially restored. The inner
`DatabaseRestoreInProgressError` branch exists specifically to handle a session that cannot reach the
database because a restore is holding the traffic lock — meaning the error path itself operates on a
degraded database, the exact condition least likely to be discovered before it is needed.

### Concrete fix

Add two tests to `tests/test_configuracoes_backup.py` that monkeypatch `restore_database_from_file`
to raise, rather than performing a real restore.

### Example

```python
def test_restore_com_arquivo_invalido_renderiza_erro_sem_500(client, monkeypatch):
    def _falha(_path):
        raise exportacao.ExportacaoError("dump corrompido")
    monkeypatch.setattr(exportacao, "restore_database_from_file", _falha)

    resp = client.post("/ui/configuracoes/restaurar", files={"arquivo": ("b.sql", b"x")})

    assert resp.status_code == 200
    assert "dump corrompido" in resp.text   # erro chega ao operador

def test_restore_concorrente_retorna_409(client, monkeypatch):
    ...raise exportacao.RestoreEmAndamentoError(...)
    assert resp.status_code == 409
```

Monkeypatching the restore function is the right level here — a real failed restore would be slow and
would leave the test database in an undefined state. That is a deliberate tradeoff: these tests
verify the *handler*, not the restore itself.

### Potential savings

Prevents an unhandled 500 during disaster recovery, when diagnostic capacity is lowest.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Uncovered range verified from a real coverage run and matched to the read source.
  - The proposed mock is scoped to the failure trigger only, so it does not hide the handler under test.
- **Weaknesses:**
  - The exact route path and form field name in the example were not confirmed against the source.
  - `RestoreEmAndamentoError` at `:279-280` may be partially covered; the missing range starts at 279, so the 409 line itself is the boundary and could already be exercised.
- **Suggested checks:**
  - Confirm the route path and whether `:279` is genuinely uncovered before writing both tests.

## imp-20260801-006 — Replace `time.sleep(0.1)` with deterministic waits in the WhatsApp tests

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** testing, flaky, concurrency, async, whatsapp
- **Files affected:** `tests/test_venda_whatsapp.py`
- **Related opportunities:** None

### Location

`tests/test_venda_whatsapp.py:95` — `test_criar_venda_dispara_notificacao`

```python
    resp = client.post(
        "/vendas", json=_payload(cliente_id, veiculo_id), headers=headers
    )

    assert resp.status_code == 201
    time.sleep(0.1)
    assert len(mensagens) == 1
    assert "João Silva" in mensagens[0]
    assert "Gol" in mensagens[0]


def test_criar_venda_agenda_notificacao_em_executor_limitado(
```

### Description

Three tests — `:100`, `:229`, `:250` — post a venda, then `time.sleep(0.1)` and assert that a
background executor has delivered the WhatsApp notification. The sleep is the synchronization
mechanism: if the post-commit callback thread has not run within 100 ms, the assertion fails.

The suite already has a deterministic alternative. `test_criar_venda_agenda_notificacao_em_executor_limitado`
(`:106`) injects a fake executor whose `submit` runs `fn(*args)` inline, removing the race entirely.
Two of the three sleeping tests could use that same fixture and drop the sleep.

100 ms is generous on an idle laptop and thin on a loaded CI runner, especially under
`pytest -n 4` / `-n auto`, which the pre-commit hook (`.pre-commit-config.yaml:103`) and CI
(`.github/workflows/ci.yml:60`) both use. All three passed in this session's run, so this is a
latent flake rather than an observed one.

### Why it matters

A sleep-synchronized test fails intermittently and for reasons unrelated to the change under review.
The predictable outcome is that someone reruns CI until it goes green, which erodes trust in the
suite and eventually masks a real notification regression. The cost of fixing it is very low here
because the deterministic pattern already exists in the same file.

### Concrete fix

Extract the inline-executor fake from `test_criar_venda_agenda_notificacao_em_executor_limitado`
into a fixture and use it in the three sleeping tests, deleting the `time.sleep(0.1)` calls.

### Example

```python
@pytest.fixture
def executor_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Inline:
        def submit(self, fn: Callable[..., None], *args: Any) -> None:
            fn(*args)
    monkeypatch.setattr(whatsapp, "_executor", _Inline())

def test_criar_venda_dispara_notificacao(client, monkeypatch, executor_inline) -> None:
    ...
    assert resp.status_code == 201
    assert len(mensagens) == 1   # sem sleep — callback já rodou inline
```

### Potential savings

Removes three latent CI flakes and ~0.3 s from every suite run.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - All three sleep sites located by grep and the surrounding tests read.
  - The deterministic replacement is not invented — it already exists at `:106` in the same file.
  - Parallel execution in both pre-commit and CI confirmed, which is what makes 100 ms risky.
- **Weaknesses:**
  - The attribute the executor is bound to (`whatsapp._executor` in the example) was not confirmed; the real name must be read from `components/xtreme_system/whatsapp/core.py`.
  - No observed failure — this is reasoning about timing margin, not a reproduced flake.
- **Suggested checks:**
  - Read the executor wiring in `whatsapp/core.py` to get the correct monkeypatch target.

## imp-20260801-007 — Cover the money-field normalization in `parse_venda_form`

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, edge-case, money, forms
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py`, `tests/test_ui.py`
- **Related opportunities:** imp-20260801-012

### Location

`bases/xtreme_system/api/routes/ui_routes/venda_write.py:54` — `parse_venda_form`

```python
    data = dict(form)
    if data.get("valor_entrada") == "":
        data["valor_entrada"] = None
    if data.get("debitos") == "":
        data["debitos"] = None
    if data.get("km") == "":
        data["km"] = None
    if data.get("parcelas") == "":
        data["parcelas"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if data.get("veiculo_troca_id") == "":
```

### Description

The coverage run reports `venda_write.py` missing lines `56, 58, 60, 62, 64, 66, 68, 70, 72, 75` —
every single assignment body in this function. The `if` conditions execute; the branches never do.
That means **no test ever submits a venda form with any of these fields left blank**, which is the
normal case for an HTML form where the user simply does not fill in an optional money field.

Four of the ten are monetary: `valor_entrada`, `debitos`, `valor_diferenca`, `valor_pendente`. The
normalization converts `""` to `None` so Pydantic treats them as absent rather than attempting to
parse an empty string as a `Decimal`.

### Why it matters

Remove or reorder any one of these lines and the empty-string value reaches
`VendaCreate.model_validate`, which rejects `""` for a `Decimal` field — turning a routine "user left
the down-payment blank" submission into a validation error the user cannot act on. Every test today
fills every field, so the suite would not notice. This is a ten-line function guarding the primary
money-entry form in the application.

### Concrete fix

One test that posts a venda form with the optional fields omitted, asserting the venda is created
with `None` in those columns.

### Example

```python
def test_ui_criar_venda_aceita_campos_opcionais_em_branco(client: TestClient) -> None:
    _login_admin(client)
    resp = client.post("/ui/vendas", data={
        **_form_venda_minimo(cliente_id, veiculo_id),
        "valor_entrada": "", "debitos": "", "parcelas": "",
        "observacoes": "", "valor_diferenca": "", "valor_pendente": "",
    })

    assert resp.status_code == 200
    criada = venda.list_all(session)[-1]
    assert criada.valor_entrada is None
    assert criada.debitos is None
```

A single test covers all ten missing lines.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - The missing-line list maps one-to-one onto the assignment bodies, an unusually clean signal.
  - The function was read in full, so the branch semantics are certain.
- **Weaknesses:**
  - No `_form_venda_minimo` helper is known to exist in `tests/test_ui.py`; the test may need to build the form dict inline.
- **Suggested checks:**
  - Reuse an existing venda-form payload from `tests/test_ui.py` rather than writing a new helper.

## imp-20260801-008 — `tendencia_por_periodo` is 66 uncovered lines with no callers

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, dead-code, analytics
- **Files affected:** `components/xtreme_system/venda/core.py`, `tests/test_venda_analytics.py`
- **Related opportunities:** imp-20260801-011

### Location

`components/xtreme_system/venda/core.py:520` — `tendencia_por_periodo`

```python
def tendencia_por_periodo(
    session: Session, periodo: str
) -> list[tuple[str, int, Decimal]]:
    """Retorna vendas agregadas por semana (30d/90d) ou mês (12m)."""
    hoje = datetime.now(UTC).date()
    if periodo == "12m":
        inicio = _inicio_janela_meses(hoje, 12)
        granularidade = "mes"
    elif periodo == "90d":
        inicio = hoje - timedelta(days=89)
        granularidade = "semana"
    else:
```

### Description

`venda/core.py` reports missing lines `524-585` — the entire body of this function, 66 lines of
date-window logic, SQL aggregation, and ISO-week bucketing with three `periodo` branches.

A repo-wide search for `tendencia` returns **exactly one hit: the definition itself.** There are no
callers in `bases/`, no callers in `components/`, no template references, and no tests. By contrast
its sibling `desempenho_vendas_mensal` is called from `dashboard.py:145` and is covered.

So the correct reading is not "this needs tests" — it is **dead code that the coverage gap makes
look like a testing gap**. `tests/test_venda_analytics.py` is 20 lines and tests only the pure helper
`_inicio_janela_meses`, which the dead function is the primary consumer of.

### Why it matters

66 lines of untested, uncalled aggregation logic is a maintenance liability in both directions:
nobody will notice when a schema change breaks it, and any future developer who wires it into a
dashboard inherits code that has never executed once. It also depresses the coverage number in a way
that hides genuine gaps elsewhere. If the function is speculative groundwork for a trends chart, that
intent belongs in a ticket, not in `main`.

### Concrete fix

Delete `tendencia_por_periodo` (`venda/core.py:520-585`). Confirm `_inicio_janela_meses` still has a
live caller — if `desempenho_vendas_mensal` does not use it, it and its test at
`tests/test_venda_analytics.py:17` go with it.

If the function is intentionally retained for imminent use, add a test that covers all three
`periodo` values (`12m`, `90d`, default) with seeded vendas spanning a week boundary, so the ISO-week
grouping at `:578-584` is actually verified.

### Potential savings

Removes 66 lines of unexecuted code and raises the honest signal-to-noise of the coverage report.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - "No callers" verified by a repo-wide search excluding `graphify-out/` and bytecode, contrasted against `desempenho_vendas_mensal`, which the same search found wired to `dashboard.py:145`.
  - Full-body uncoverage independently confirmed by the coverage run.
- **Weaknesses:**
  - The search covered the repository only; a caller in an external consumer of this Polylith component would not appear. `venda/core.py` is a shared component, so that is a real if unlikely possibility.
  - This is framed as a deletion, which is a different action than the rest of this report — it warrants an owner decision rather than a mechanical fix.
- **Suggested checks:**
  - Confirm with the maintainer whether a trends chart is planned before deleting; check git history for when the function was added and whether its caller was reverted.

## imp-20260801-009 — Vehicle-documents upload and delete routes are 54% covered

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, uploads, attachments
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py`, `components/xtreme_system/crud/attachment.py`, `tests/test_uploads.py`
- **Related opportunities:** None

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos_documentos.py:116` — `ui_veiculo_documentos_excluir`

```python
    doc = found(documento_veiculo.get(session, doc_id), "Documento")
    excluir_anexo_entidade(
        session,
        anexo=doc,
        parent_field="veiculo_id",
        parent_id=veiculo_id,
        delete_fn=documento_veiculo.delete,
        actor_id=user.id,
        not_found_detail="Documento não encontrado",
    )
    return _documentos_modal(request, session, user, veiculo_id, action_oob=True)
```

### Description

This module sits at 54% with missing lines `36-38, 57-59, 80, 91-105, 116-126` — the upload handler
body (`91-105`), the delete handler body (`116-126`), and both modal-rendering helpers.

`tests/test_uploads.py` is a strong 680-line file and covers the *generic* attachment machinery well,
including rollback behavior (`test_salvar_arquivos_rollback_remove_arquivo:239`,
`test_delete_parent_keeps_upload_file_on_rollback:326`). `tests/test_ui.py` covers the equivalent
routes for **client** documents and **vehicle images**
(`test_salvar_documentos_cliente_remove_arquivo_se_create_falha:3571`,
`test_salvar_documento_veiculo_remove_arquivo_se_create_falha:3592`,
`test_upload_imagem_veiculo_remove_arquivo_se_create_falha:3548`).

The vehicle-*documents* route is the one member of that family with no route-level test. The
`parent_field`/`parent_id` wiring in `excluir_anexo_entidade` — which is what stops a caller from
deleting a document belonging to a *different* vehicle — is unverified for this entity.

### Why it matters

`excluir_anexo_entidade` receives `parent_field="veiculo_id"` and `parent_id=veiculo_id` specifically
so that a crafted request cannot delete another vehicle's document by guessing a `doc_id`. That is an
ownership check. Since the sibling routes are tested and this one is not, the gap is invisible to
anyone reading the test suite for reassurance.

### Concrete fix

Add a mismatched-parent test, mirroring the structure of the existing sibling tests in
`tests/test_ui.py`.

### Example

```python
def test_ui_excluir_documento_de_outro_veiculo_e_rejeitado(client: TestClient) -> None:
    _login_admin(client)
    doc_a = _upload_documento(client, veiculo_a.id)

    # doc_a pertence a veiculo_a, mas a rota é chamada com veiculo_b
    resp = client.post(f"/ui/veiculos/{veiculo_b.id}/documentos/{doc_a.id}/excluir")

    assert resp.status_code == 404
    assert documento_veiculo.get(session, doc_a.id) is not None  # não removido
    assert Path(doc_a.caminho).exists()  # arquivo em disco preservado
```

Add one happy-path upload/delete test alongside it to close most of the remaining 46%.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The coverage figure and missing ranges are from a real run; the delete handler was read in full.
  - The claim that sibling routes are tested was verified by locating the three named tests in `tests/test_ui.py`.
- **Weaknesses:**
  - `excluir_anexo_entidade` itself was not read, so whether the parent mismatch raises 404 (as `not_found_detail` suggests) or is silently ignored is inferred from the parameter names.
- **Suggested checks:**
  - Read `excluir_anexo_entidade` in `components/xtreme_system/crud/attachment.py` to confirm the mismatch behavior before asserting a status code.

## imp-20260801-010 — Cover the vehicle-resolution rejection branches in compra creation

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, validation, negative-case, compras
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/compras.py`, `tests/test_ui.py`
- **Related opportunities:** imp-20260801-003

### Location

`bases/xtreme_system/api/routes/ui_routes/compras.py:287` — `_resolver_veiculo`

```python
    placa = str(form.get("vei_placa") or "").strip().upper()
    if not placa:
        return None, None, "Informe a placa do veículo"
    if veiculo.get_by_placa(session, placa):
        return None, None, "Placa já cadastrada — selecione o veículo na lista"
    try:
        novo_veiculo_data = veiculo.VeiculoCreate.model_validate(
            {
                "tipo": form.get("vei_tipo"),
                "tipo_entrada": form.get("vei_tipo_entrada"),
```

### Description

Within `compras.py`'s 81%, the missing lines `282-283, 285, 290, 292` are all rejection returns of
`_resolver_veiculo`: invalid/nonexistent selected vehicle (`282-285`), missing plate (`290`), and
**plate already registered** (`292`). Only the success path is exercised.

The duplicate-plate rejection is the notable one. The venda side has an equivalent test —
`test_ui_criar_venda_troca_placa_ja_cadastrada_retorna_erro` at `tests/test_ui.py:1188` — so the
pattern and the fixtures already exist; the compra side simply never got the same treatment.

### Why it matters

`vei_placa` is the inline "register a new vehicle while recording a purchase" path. Without the
duplicate check, a purchase form creates a second vehicle row for a plate that already exists,
splitting that vehicle's cost history and caixa entries across two records — a data-integrity
failure that is tedious to unwind after the fact and easy to miss at entry time.

### Concrete fix

Add a duplicate-plate test for the compra form, copying the structure of the existing venda test at
`tests/test_ui.py:1188`.

### Example

```python
def test_ui_criar_compra_placa_ja_cadastrada_retorna_erro(client: TestClient) -> None:
    _login_admin(client)
    resp = client.post("/ui/compras", data={
        **_form_compra_base(cliente_id),
        "veiculo_id": "",
        "vei_placa": veiculo_existente.placa,
    })

    assert "Placa já cadastrada" in resp.text
    assert len(veiculo.list_all(session)) == 1   # nenhum veículo duplicado
```

The row-count assertion is what makes this a data-integrity test rather than a message test.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Missing lines map cleanly onto the three rejection returns, read and verified in the source.
  - The analogous venda-side test was located, confirming both the pattern and that the gap is compra-specific.
- **Weaknesses:**
  - `_form_compra_base` is illustrative; the real test must reuse whatever compra-form payload helper `tests/test_ui.py` already has.
- **Suggested checks:**
  - Reuse the payload construction from the existing compra tests around `tests/test_ui.py:2061`.

## imp-20260801-011 — Investidor update: blank-name and duplicate-name branches untested

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, validation, rollback, investidor
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/investidores.py`, `tests/test_ui.py`
- **Related opportunities:** imp-20260801-002, imp-20260801-001

### Location

`bases/xtreme_system/api/routes/ui_routes/investidores.py:258` — `ui_investidor_atualizar`

```python
    nome = str((await request.form()).get("nome") or "").strip()
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
```

### Description

`investidores.py` is at 78%, missing `139-142, 168, 185-186, 198, 208-209, 257-278, 302-303`. The
`257-278` block is this whole handler: the blank-name 400 branch, the `IntegrityError` 409 branch,
and the rollback call between them.

Investidores are the owners of vehicles and the counterparties of every caixa lançamento
(`caixa.list_by_investidor`), so this is not an incidental lookup table. It is also worth noting that
`components/xtreme_system/investidor/core.py` is small and fully covered — the gap is entirely at the
route layer, the same shape as imp-20260801-002 and imp-20260801-004.

### Why it matters

The 409 branch routes through `rollback_integrity_error_response`, which issues the
`session.rollback()` that keeps `get_session` from committing a dirty session afterwards. Untested,
a refactor that returns the template directly — skipping the rollback — would produce exactly the
failure this project's `CLAUDE.md` calls out as a bug worth flagging, and no test would catch it.

### Concrete fix

Two short tests in `tests/test_ui.py`, asserting the session is clean after the conflict.

### Example

```python
def test_ui_investidor_nome_duplicado_retorna_409_e_nao_persiste(client, session):
    a = _criar_investidor(client, "Alfa")
    b = _criar_investidor(client, "Beta")

    resp = client.post(f"/ui/investidores/{b.id}", data={"nome": "Alfa"})

    assert resp.status_code == 409
    assert not session.dirty and not session.new
    session.refresh(b)
    assert b.nome == "Beta"
```

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The uncovered range covers the handler exactly; the source was read and matches.
  - Consistent with the same route-layer-vs-domain-layer pattern confirmed in two other modules.
- **Weaknesses:**
  - Assumes a unique constraint exists on `investidor.nome`; if there is none, the 409 branch is unreachable and this becomes a dead-code finding like imp-20260801-008.
- **Suggested checks:**
  - Confirm the unique constraint on `investidor.nome` in the model or migrations before writing the test.

## imp-20260801-012 — Nested-write conflict rollback in venda creation is untested

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** testing, coverage, rollback, nested-writes, venda
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/venda_write.py`, `tests/test_ui.py`
- **Related opportunities:** imp-20260801-007

### Location

`bases/xtreme_system/api/routes/ui_routes/venda_write.py:131` — `_create_nested`

```python
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

`venda_write.py` is at 77%. Beyond the form-normalization gap in imp-20260801-007, the missing lines
`84-90, 119-120, 136-138, 158, 161, 173, 198, 235` include the trade-in vehicle rejection branch of
`resolver_veiculo_troca` (`84-90`), the `except (ValidationError, ValueError)` branch at `119-120`,
and the conflict-propagation paths at `136-138`/`158`/`161`.

The critical uncovered behavior is `_create_nested`'s `except IntegrityError` →
`nested_writes.rollback(session)`. Creating a venda can create a client and a trade-in vehicle in the
same request; when the second nested write conflicts, `nested_writes.rollback` must undo the first.
No test drives that sequence.

The suite does cover *adjacent* atomicity — `test_venda_inline_cliente_nao_persiste_quando_validacao_falha`
(`tests/test_ui.py:1605`) covers the `ValidationError` path, and
`test_ui_vendas_aborta_se_gravacao_do_contrato_falhar` (`:3019`) covers a later failure. The specific
`IntegrityError`-during-nested-create path is the one that is missed.

### Why it matters

A partial nested write leaves an orphaned client or vehicle row with no venda referencing it. Those
orphans are invisible in the UI, accumulate silently, and later surface as duplicate-client
confusion or as a vehicle in inventory that was never actually acquired. The rollback helper is the
only thing preventing it, and it is currently unverified.

### Concrete fix

One test that submits a venda with a new inline client and a trade-in vehicle whose plate already
exists, asserting neither the client nor the vehicle survives.

### Example

```python
def test_ui_venda_com_troca_conflitante_nao_deixa_cliente_orfao(client, session):
    antes = len(cliente.list_all(session))

    resp = client.post("/ui/vendas", data={
        **_form_venda_cliente_inline("Novo Cliente"),
        "veic_troca_placa": veiculo_existente.placa,   # colide
    })

    assert "Veículo da troca" in resp.text
    assert len(cliente.list_all(session)) == antes   # cliente não persistiu
```

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** No
- **Strengths:**
  - `_create_nested` was read in full and its rollback branch confirmed uncovered.
  - The adjacent-but-different existing tests were located, so the gap is narrowly scoped rather than overstated.
- **Weaknesses:**
  - `NestedWrites.rollback` was not read, so exactly what it undoes (flush-level vs full session rollback) is unconfirmed, and the assertion may need adjusting.
  - Whether a duplicate plate on the trade-in path raises `IntegrityError` or is caught earlier as a validation error is unverified — if the latter, this branch may be unreachable from the UI.
- **Suggested checks:**
  - Read `NestedWrites.rollback` and confirm the duplicate-plate path reaches `_create_nested` rather than being rejected upstream by `resolver_veiculo_troca`.

## imp-20260801-013 — Raise the coverage floor from 75% to near the actual 89%

- **Impact:** Medium
- **Category:** Testing
- **Estimated effort:** Low
- **Priority:** low
- **Risk level:** low
- **Tags:** testing, coverage, ci, suite-health
- **Files affected:** `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `.coverage`
- **Related opportunities:** None

### Location

`pyproject.toml:198` — `[tool.coverage.report]`

```toml
[tool.coverage.report]
fail_under = 75
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@overload",
]
```

### Description

Measured coverage is **89.09%** while the enforced floor is **75%**. The threshold is genuinely
enforced — this session's run printed `Required test coverage of 75.0% reached` — but the 14-point
gap means roughly 780 statements' worth of regression could land before CI objects.

Separately, the committed `.coverage` file is stale: reading it fails with
`No source for code: .../ui_routes/common.py` and `.../routes/workflows.py`, both of which no longer
exist. It also reports 54% total, which materially understates the suite. A stale artifact that
reports a much worse number than reality is actively misleading to anyone who inspects it instead of
re-running.

### Why it matters

A floor 14 points below actual is not a ratchet — it permits substantial silent erosion. The
practical failure mode is incremental: several PRs each add uncovered branches, none individually
trips the threshold, and the gaps in this report get quietly larger. Raising the floor to just under
current makes any net coverage loss a CI failure rather than a code-review judgment call.

### Concrete fix

Set `fail_under = 88` in `pyproject.toml:199` and `--cov-fail-under=88` in `Makefile:56`, then add
`.coverage` to `.gitignore` and remove the stale file from the index.

Pair this with the higher-value findings above rather than shipping it alone — raising the floor
first would only make the next unrelated PR fail.

### Potential savings

Converts silent coverage erosion into a CI failure; removes a committed artifact that understates the
suite by 35 points.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Both numbers come from a real run in this session; enforcement was confirmed by the pytest-cov output line rather than assumed from config.
  - Staleness of `.coverage` is directly evidenced by the two missing-source errors naming deleted files.
- **Weaknesses:**
  - This is the weakest finding in the report — process hygiene, not a specific regression that could reach production.
  - 88 is a judgment call; if coverage varies between the SQLite fallback used here and the Postgres path used in CI, the floor may need to sit slightly lower.
- **Suggested checks:**
  - Run `make coverage` against Postgres and confirm the figure matches the 89.09% measured under the SQLite fallback before fixing the number.

## Discarded candidates

### `safe_write` / `get_session` rollback contract has no test

Checked directly because this project's `CLAUDE.md` calls it out. The contract is genuinely well
covered: `tests/test_database_session.py` asserts rollback counts across four scenarios (`:57`,
`:79`, `:125`, `:141`), `tests/test_request_context.py:77` covers the commit-failure path with a
fake session, and `tests/test_route_factories_atomicity.py` raises real `IntegrityError`s at `:117`
and `:149`. No finding here.

### Authorization test matrix for `perfil/policy.py` is missing

Also checked because `CLAUDE.md` names it. `tests/test_perfil.py` contains 18 tests forming a real
role × action × field matrix, including negative cases (`test_vendedor_sem_perfil_nao_acessa_nada`,
`test_campos_de_pagina_fora_do_perfil_sao_negados`, `test_operacoes_sao_opt_in`), and
`perfil/core.py` measures 99%. Coverage is adequate; the gap is at the route layer only, reported as
imp-20260801-004.

### Dangerously-mocked persistence tests

Reviewed `_FakeSession` (`tests/test_ui.py:67`), `_client_with_failing_final_commit` (`:2825`), and
`_client_with_contract_write_failure` (`:2882`). Each is scoped to inject one specific failure while
the real session still performs the write under test — the correct use of a fake. Tests such as
`test_ui_compras_nao_grava_comprovante_se_commit_final_falhar` assert real filesystem and DB state
afterwards, not call counts. No misleading mocks found.

### Order-dependent tests from shared fixture state

`tests/database.py` truncates all tables per engine creation and isolates Postgres schemas per
xdist worker (`_worker_schema`); `conftest.py` resets module-level rate limiters via an autouse
fixture and clears `app.dependency_overrides` on teardown. The suite also passed under
`-p no:randomly`. Fixture hygiene is sound.

### Skipped or xfail tests with no tracked reason

Only one skip exists — `tests/test_migrations.py:11`, a `skipif` guard — and the run reported exactly
`1 skipped`. Not a suite-health problem.

### CI reports coverage but never fails on it

Initially suspected because `.github/workflows/ci.yml:60` omits `--cov-fail-under`. Verified false:
pytest-cov reads `fail_under` from `[tool.coverage.report]` in `pyproject.toml`, and the local run
confirmed the threshold is applied. The remaining, weaker concern — that the floor is set too low —
is reported as imp-20260801-013.

### Date-dependent tests using `datetime.now()`

`tests/test_ui.py:2190` and `tests/test_auditoria.py:99` derive `hoje` from the current date. Both
seed data relative to that same `hoje` and assert with inequalities (`>= 1`) or on data they created,
so neither breaks at a month or year boundary. Not flaky in practice.

### `tests/test_ui.py` is a 3,805-line monolith

Real maintainability concern — it is 31% of all test code and mixes UI rendering, uploads,
authorization, and auditoria. But it is well organized with shared helpers and no correctness or
coverage consequence, so it does not meet the Medium-impact bar for this review.
