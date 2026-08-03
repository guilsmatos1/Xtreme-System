# Improvement opportunities

- **Generated:** 2026-08-01T13:02:06-03:00
- **Total:** 15

## imp-20260801-001 — Validation errors wipe every field the user typed in cliente, custo, usuário and lançamento forms

- **Impact:** High
- **Category:** Error presentation
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** forms, error-handling, data-loss, htmx, jinja
- **Files affected:** `bases/xtreme_system/api/templates/_form_cliente.html`, `bases/xtreme_system/api/templates/_form_custo_veiculo.html`, `bases/xtreme_system/api/templates/_form_usuario.html`, `bases/xtreme_system/api/templates/_form_lancamento.html`, `bases/xtreme_system/api/crud_ui/responses.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-004

### Location

`bases/xtreme_system/api/templates/_form_cliente.html:11` — create/edit cliente modal body

```html
        {% if erro %}{{ ui.alert(erro) }}{% endif %}
        <div class="form-grid">
          <label class="field field--full">
            <span class="field__label">Nome *</span>
            <input class="input" name="nome" value="{{ cliente.nome if cliente else '' }}" required autofocus>
          </label>

          <label class="field">
            <span class="field__label">Documento (CPF/CNPJ) *</span>
            <input class="input" name="documento" value="{{ cliente.documento if cliente else '' }}" required>
          </label>
```

### Description

`form_response()` in `crud_ui/responses.py:66-77` always injects a `dados` dict holding the raw
submitted form into the error re-render context. `_form_veiculo.html` (25 uses) and
`_form_compra.html` (33 uses) consume it. `_form_cliente.html`, `_form_custo_veiculo.html`,
`_form_usuario.html` and `_form_lancamento.html` use it zero times — every input reads
`{{ cliente.<field> if cliente else '' }}`. On a create, `cliente` is `None`, so a rejected submit
re-renders all thirteen fields blank. On an edit, the fields snap back to the stored row, silently
discarding the changes the user was making.

### Why it matters

The most common rejection on these forms is a duplicate `documento` — exactly the case where the
user has already typed name, document, address, city, state, CEP and profession. The modal comes
back empty with a red banner, and the whole form has to be retyped from memory. Because the swap
target is `#modal` with `innerHTML`, there is no browser back-button recovery either.

### Concrete fix

Route each value through `dados` with the entity as fallback, mirroring the pattern already used in
`_form_veiculo.html`:
`value="{{ dados.get('nome', cliente.nome if cliente else '') }}"`. No route or Python change is
needed — `dados` is already in context for every one of these templates.

### Domain details

#### Screens

- Clientes → Novo cliente / Editar cliente
- Custos de veículos → Novo custo
- Usuários → Novo usuário
- Investidores → Lançamentos → Novo lançamento

#### Frequency of exposure

Daily. Cliente creation happens on every walk-in and is also embedded in the venda wizard flow.

#### Propagation

Fix is per-template but the pattern is already proven in two sibling templates, so it is copy-shaped
and mechanical.

#### Acceptance criteria

- Submitting a cliente form with a duplicate document re-renders the modal with every typed value
  intact.
- Editing a cliente and triggering a validation error keeps the edited values, not the stored ones.
- The same holds for custo, usuário and lançamento forms.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - `dados` availability confirmed in `crud_ui/responses.py:66-77`, not assumed.
  - The divergence is measurable: 33 and 25 uses in compra/veículo versus 0 in the four templates.
- **Weaknesses:**
  - I did not exercise the running app; the reasoning is from template and response-builder code.
  - I did not confirm every error path for custo/usuário/lançamento reaches `form_response` rather
    than a plain redirect.
- **Suggested checks:**
  - POST a duplicate `documento` to `/ui/clientes` and inspect the returned HTML for the typed values.

## imp-20260801-002 — Rateio percentage fields reject the comma format their own placeholder teaches, permanently disabling "Confirmar fechamento"

- **Impact:** High
- **Category:** Form ergonomics
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** forms, i18n, money, dead-end, vendas
- **Files affected:** `bases/xtreme_system/api/templates/_modal_fechamento_venda.html`, `bases/xtreme_system/api/static/filters.js`
- **Related opportunities:** imp-20260801-009

### Location

`bases/xtreme_system/api/templates/_modal_fechamento_venda.html:56` — rateio block and submit guard

```html
            <input class="input" name="percentual" type="number" min="0" max="100" step="0.01" placeholder="0,00" required>
          </label>
          {% endfor %}
          <p id="rateio-total" role="status" aria-live="polite">Total: 0,00% — deve somar 100%</p>
        </div>
        {% endif %}
      </div>
      <div class="modal__foot">
        <button class="btn btn--ghost" type="button" onclick="document.getElementById('modal').innerHTML=''">Cancelar</button>
        <button class="btn btn--primary" type="submit" {% if not preview.elegivel or (preview.lucro_liquido > 0 and preview.investidores and pode_ver_campo(user, 'vendas', 'participacao')) %}disabled{% endif %}>Confirmar fechamento</button>
      </div>
```

### Description

The field is `type="number"` but carries `placeholder="0,00"` and sits next to a live total that
prints `0,00%`. A pt-BR user follows that cue and types `33,33`. An `<input type="number">` treats a
comma as invalid, so `.value` reads back as the empty string. The inline script at lines 74-83 does
`sum += Number(field.value) || 0`, the total stays at `0,00%`, and `submit.disabled = !valid` keeps
"Confirmar fechamento" permanently greyed out. Nothing on screen says why. Every other money input in
the app uses `type="text" inputmode="decimal"` and is normalized by `filters.js:82-88`, so this
control is also the odd one out.

### Why it matters

Fechamento is the irreversible profit-distribution step — the confirm text itself says "Esta ação não
pode ser desfeita." A dead submit button with a total stuck at zero and no error text is the worst
possible failure mode: the user cannot tell whether the system is broken, whether they lack
permission, or whether they typed something wrong.

### Concrete fix

Switch the field to the app's existing money convention so `filters.js` normalizes it on submit —
replace `type="number" min="0" max="100" step="0.01"` with `type="text" inputmode="decimal"`, keeping
the `placeholder="0,00"` and `required` — and change the script's accumulator to reuse the same normalization
(`Number(String(field.value).replace(',', '.'))`). Alternatively keep `type="number"` and change the
placeholder to `0.00` — but that breaks locale consistency with every other numeric field.

### Domain details

#### Screens

- Vendas → row action "Fechar venda" → Fechamento modal (rateio de lucro)

#### Frequency of exposure

Every closed sale with a positive profit and at least one investor.

#### Propagation

Single template plus a two-line script change; no other screen uses `type="number"` for a decimal.

#### Acceptance criteria

- Typing `33,33` in a rateio field updates the running total to `33,33%`.
- Three fields summing to `100,00%` enable "Confirmar fechamento".
- The submitted `percentual` values arrive at the server as dot-decimals.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Behavior of `<input type="number">` with a comma is well-defined: the value sanitizes to `""`.
  - The contradiction is visible in one line — comma placeholder on a number input.
  - The disabled-button dead end is traceable to line 80 of the same file.
- **Weaknesses:**
  - Not reproduced in a browser; a user with a keyboard layout or locale that types `.` never hits it.
  - `filters.js` targets `input[inputmode="decimal"]`, so the proposed fix depends on adding that
    attribute, which I did not test end-to-end.
- **Suggested checks:**
  - Open a fechamento with two investors and type comma values; confirm the button stays disabled.

## imp-20260801-003 — Raw Pydantic field paths and English validation text are shown to end users in the error banner

- **Impact:** High
- **Category:** Error presentation
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** error-handling, i18n, forms, copy
- **Files affected:** `bases/xtreme_system/api/crud_ui/responses.py`, `bases/xtreme_system/api/routes/ui_routes/venda_write.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `bases/xtreme_system/api/routes/ui_routes/lancamentos.py`, `bases/xtreme_system/api/templates/_macros.html`
- **Related opportunities:** imp-20260801-001, imp-20260801-015

### Location

`bases/xtreme_system/api/crud_ui/responses.py:22` — `validation_error_detail`

```python
_HTMX_SUCCESS_EVENTS = {
    "htmx:toast": {"message": "Alterações salvas com sucesso."},
    "htmx:close-modal": {},
}


def validation_error_detail(exc: ValidationError) -> str:
    """Format Pydantic errors without discarding the field that failed."""
    return "; ".join(
        f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()
    )
```

### Description

Five UI routes funnel Pydantic failures through `validation_error_detail`, whose output is a
semicolon-joined list of `<python_field_path>: <english pydantic message>` — for example
`valor_venda: Input should be a valid decimal`. That string lands in `{{ ui.alert(erro) }}` at the
top of the modal body. The interface is otherwise entirely Portuguese, and the field paths are
internal snake_case attribute names, not the labels shown next to the inputs ("Valor da venda *").
The message is also detached from the field: on the long venda and compra forms the offending input
may be several screens below the banner, or on an inactive wizard step.

### Why it matters

A daily user reading `veic_troca_preco: Input should be a valid decimal` cannot map it to the field
labelled "Valor de avaliação *" without guessing. Multiple simultaneous errors collapse into one
run-on line. The result is retry-by-trial on money-bearing forms, and support escalations for what is
really a formatting typo.

### Concrete fix

Add a field-label map next to `validation_error_detail` (or attach `label` metadata to the schemas)
and render one Portuguese sentence per error, then pass the failing field names to the template so
the matching `.field` can be marked. The smallest first step is translating the common Pydantic
messages and substituting labels for `loc` paths:

a module-level `_LABELS` map (`{"valor_venda": "Valor da venda", ...}`) and a `_MSGS` map keyed by
Pydantic error type (`{"decimal_parsing": "informe um valor numérico válido", ...}`).

### Domain details

#### Screens

- Vendas (novo/editar), Compras (novo/editar), Veículos (editar), Perfis, Lançamentos

#### Frequency of exposure

Every rejected submit on the five highest-traffic write flows.

#### Propagation

Central: one helper feeds all five call sites, so the message fix is single-point. Per-field
highlighting would additionally touch the form templates.

#### Acceptance criteria

- A rejected decimal on "Valor da venda" produces a Portuguese message naming that label.
- Two simultaneous errors render as two separate lines, not one semicolon-joined string.
- No raw snake_case attribute name appears in user-facing copy.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The formatter and all five call sites were read directly.
  - The rendering path to `ui.alert` is confirmed in the form templates.
- **Weaknesses:**
  - I did not enumerate which Pydantic messages actually occur most often, so the translation table
    scope is estimated.
  - Some schemas may already carry custom Portuguese messages that would pass through unchanged; I
    did not audit the schema layer.
- **Suggested checks:**
  - Submit a non-numeric `valor_venda` and capture the exact banner text.

## imp-20260801-004 — Editing a venda and hitting a validation error silently reverts the form to the stored values

- **Impact:** High
- **Category:** Error presentation
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** forms, data-loss, vendas, htmx
- **Files affected:** `bases/xtreme_system/api/templates/_form_venda.html`, `bases/xtreme_system/api/routes/ui_routes/vendas.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-015

### Location

`bases/xtreme_system/api/templates/_form_venda.html:18` — edit branch of the venda form

```html
          <label class="field">
            <span class="field__label">KM</span>
            <input class="input" name="km" type="number" min="0" value="{{ venda.km if venda.km is not none else '' }}">
          </label>
          {% endif %}
          {% if pode_ver_campo(user, 'vendas', 'status') %}
          <label class="field">
            <span class="field__label">Status *</span>
            <select class="select" name="status" required>
              {% for s in status %}
              <option value="{{ s.value }}"{% if venda.status == s %} selected{% endif %}>{{ s.value | replace("_", " ") | title }}</option>
              {% endfor %}
```

### Description

`_atualizar_venda` (`vendas.py:468-472`) hands the rejected submit to
`_resposta_erro_preparacao_venda(..., venda_obj=obj, dados=resultado.dados)`, and `_erro_venda`
(`vendas.py:340-359`) passes both through. But the template's edit branch — lines 15 to 180 — reads
exclusively from `venda.*`, the unmodified ORM row. The only exception is
`dados.get('veiculo_troca_label', ...)` at line 80. So the user's edits to KM, status, valor da
venda, entrada, débitos, forma de pagamento, parcelas, valor pendente, datas de pagamento and
observações are all discarded on the way back. The 409-conflict path at `vendas.py:486-495` does not
even pass `dados`.

### Why it matters

The venda edit form carries roughly fifteen fields including every money value. Reverting them while
showing an error banner is worse than showing nothing: the form now looks correct, so a user who
does not re-check every field will resubmit unchanged values and either see the same error or,
worse, save a partial correction they believe they made.

### Concrete fix

Apply the `dados.get(<name>, <venda fallback>)` pattern already used in the wizard branch of the same
file to the edit branch, and pass `dados=dados_form` in the 409 branch of `_atualizar_venda` the way
`_criar_venda` already does at `vendas.py:451`.

### Domain details

#### Screens

- Vendas → row action "Editar venda"

#### Frequency of exposure

Every rejected venda edit — the most money-dense edit form in the system.

#### Propagation

One template branch plus one route argument; the create path already demonstrates the correct shape.

#### Acceptance criteria

- Editing `valor_venda` to an invalid value and submitting re-renders the form with the invalid text
  still present, not the stored value.
- A 409 conflict on update re-renders with the submitted values.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Both sides verified: the route passes `dados`, the edit branch ignores it.
  - The asymmetry with `_criar_venda` (which does pass `dados_form` on conflict) is explicit in code.
- **Weaknesses:**
  - I did not check whether `resultado.dados` is fully populated on the update path or only on create.
  - Not exercised against a running server.
- **Suggested checks:**
  - Log `resultado.dados` on an update rejection to confirm it carries the full submitted form.

## imp-20260801-005 — Table headers never actually stick, so long lists lose their column labels while scrolling

- **Impact:** Medium
- **Category:** Density and scanability
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** css, tables, scanability, sticky
- **Files affected:** `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-014

### Location

`bases/xtreme_system/api/static/app.css:401` — `.table-wrap` / `thead th`

```css
.table-wrap { position: relative; overflow-x: auto; border-radius: var(--r-lg); border: 1px solid var(--border); background: var(--surface); }
table { width: 100%; border-collapse: collapse; font-size: .83rem; }
thead th {
  text-align: left; font-weight: 650; font-size: .7rem; letter-spacing: .04em;
  text-transform: uppercase; color: var(--text-secondary);
  padding: var(--s-2) var(--s-3); background: var(--surface-2);
  border-bottom: 1px solid var(--border-strong); white-space: nowrap;
  position: sticky; top: 0; z-index: 2;
}
tbody td { padding: 6px var(--s-3); border-bottom: 1px solid var(--border); vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
tbody tr { transition: background .1s; }
```

### Description

`thead th` declares `position: sticky; top: 0`, and the responsive block at line 755 refines it to
`top: var(--topbar-h)` — clear evidence the intent is a header that survives page scroll. But
`.table-wrap` sets `overflow-x: auto`, which per CSS makes the computed `overflow-y` `auto` as well,
turning the wrapper into the sticky element's scroll container. The wrapper has no height constraint,
so it never scrolls vertically; the page body scrolls instead. The header therefore sticks to the top
of a container that is already fully visible — a no-op. Scrolling a 200-row Estoque table leaves the
user reading fourteen unlabelled columns. The related `td.col-actions` sticky rule at line 419-425
works, because horizontal scrolling does happen inside the wrapper.

### Why it matters

These tables are wide (`.table--wide { min-width: 900px }`) and column-configurable, so users
reorder and hide columns per their workflow. Once the labels scroll away, an unlabelled money column
is genuinely ambiguous — "Preço Anunciado", "Débitos" and "Valor" all render as right-aligned
currency. Users scroll back up to re-orient, repeatedly.

### Concrete fix

Give `.table-wrap` a bounded height so it becomes the real scroller, or drop the wrapper from the
sticky chain. The smallest change is one declaration —
`.table-wrap { max-height: calc(100dvh - 220px); overflow: auto; }` — which makes the wrapper the
real scroller. Keep the existing `thead th { top: 0 }`; the mobile override at line 755 can then be removed since
the header is no longer positioned against the viewport.

### Domain details

#### Screens

- Veículos, Vendas, Compras, Clientes, Custos, Usuários, Investidores, Auditoria — every list.

#### Frequency of exposure

Continuous. Table scanning is the primary daily activity in this system.

#### Propagation

One CSS rule fixes every list at once.

#### Acceptance criteria

- Scrolling any list past 20 rows keeps the column headers visible.
- The sticky `col-actions` column continues to work during horizontal scroll.
- The layout does not double-scroll (page and wrapper both scrolling) on desktop.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The `overflow-x: auto` → computed `overflow-y: auto` interaction is specified CSS behavior, not a
    guess, and the responsive `top: var(--topbar-h)` override documents the intended effect.
- **Weaknesses:**
  - Not rendered in a browser, so I cannot state which of the two possible symptoms (no stick at all
    versus sticking to an off-screen container edge) the user actually sees.
  - A bounded `max-height` changes page rhythm and may interact with the pagination bar; the exact
    offset needs design review.
- **Suggested checks:**
  - Load Estoque with 100+ vehicles and scroll; observe whether the header row leaves the viewport.

## imp-20260801-006 — Modal save/next buttons scroll out of view on the long venda, compra and veículo forms

- **Impact:** Medium
- **Category:** Feedback and system state
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** css, modals, forms, discoverability
- **Files affected:** `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-015

### Location

`bases/xtreme_system/api/static/app.css:457` — `.modal__panel` / `.modal__foot`

```css
.modal__panel {
  width: 100%; max-width: 560px; max-height: 90dvh; overflow-y: auto;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-lg); box-shadow: var(--shadow-lg);
  animation: pop .16s cubic-bezier(.16,1,.3,1);
}
.modal__head { display: flex; align-items: center; justify-content: space-between; padding: var(--s-4) var(--s-4) var(--s-3); border-bottom: 1px solid var(--border); }
.modal__head h3 { font-size: 1rem; }
.modal__body { padding: var(--s-4); display: flex; flex-direction: column; gap: var(--s-3); }
.modal__section { font-size: .82rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .04em; }
.modal__foot { display: flex; justify-content: flex-end; gap: var(--s-3); padding: var(--s-3) var(--s-4); border-top: 1px solid var(--border); background: var(--surface-2); border-radius: 0 0 var(--r-lg) var(--r-lg); }
```

### Description

`overflow-y: auto` is on `.modal__panel`, which contains head, body and foot. The whole panel
scrolls, so `.modal__foot` — holding Cancelar, Voltar, Próximo and Salvar — scrolls away with the
content. The venda edit form renders roughly fifteen fields in a two-column grid, the veículo form
(`_form_veiculo.html`, 314 lines) and compra form (350 lines) are comparable. At `max-height: 90dvh`
on a 768px-tall laptop, the action row is below the fold from the moment the modal opens.

### Why it matters

The primary action of a modal should never require discovery. On the wizard specifically, the
"Próximo" button is how users advance — a user who does not scroll can conclude the form is stuck.
Users also lose the ability to cancel without scrolling, which pushes them toward the backdrop click,
which then triggers the "Descartar as alterações?" confirm — an extra dialog for what should be one
click.

### Concrete fix

Move the scroll to the body and pin head and foot: make `.modal__panel` a column flex container with
`overflow: hidden`, give `.modal__body` `overflow-y: auto; flex: 1; min-height: 0`, and set
`.modal__head, .modal__foot { flex: none }`. This is one CSS block and applies to every modal in the app, including the shared `anexos_modal`
macro and the column configurator.

### Domain details

#### Screens

- Nova/Editar venda, Nova/Editar compra, Editar veículo, Fechamento, Anexos, Colunas

#### Frequency of exposure

Every write operation in the system goes through a modal.

#### Propagation

Single CSS rule; all modals share `.modal__panel`.

#### Acceptance criteria

- Opening "Nova venda" on a 768px-tall viewport shows the Próximo button without scrolling.
- The modal body scrolls independently while head and foot stay fixed.
- The `anexos_modal` upload form, which sits outside `.modal__body`, still renders correctly.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Structure verified across templates: `.modal__foot` is a sibling of `.modal__body` inside the
    scrolling `.modal__panel` in every form.
- **Weaknesses:**
  - Not rendered, so the exact viewport height at which the footer falls below the fold is reasoned,
    not measured.
  - `anexos_modal` puts its upload `<form>` after `.modal__body` rather than in a `.modal__foot`, so
    the flex change needs a check there.
- **Suggested checks:**
  - Screenshot "Nova venda" at 1280x720 and confirm the footer position.

## imp-20260801-007 — Success messages are rendered with the danger alert macro, so confirmations appear as red errors

- **Impact:** Medium
- **Category:** Feedback and system state
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** feedback, css, macros, trust, consistency
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/templates/conta.html`, `bases/xtreme_system/api/templates/_macros.html`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-008

### Location

`bases/xtreme_system/api/static/app.css:649` — `.alert`, the only variant of the macro

```css
/* ---- 13. Alert / inline messages ---------------------------------------- */
.alert {
  display: flex; align-items: center; gap: var(--s-2);
  padding: var(--s-2) var(--s-3); border-radius: var(--r);
  font-size: .84rem; background: var(--danger-soft); color: var(--danger);
  border: 1px solid color-mix(in srgb, var(--danger) 22%, transparent);
}
.alert svg { width: 16px; height: 16px; flex: none; }

/* ---- 14. Toast (#msg, oob-swapped) --------------------------------------- */
#msg:empty { display: none; }
```

### Description

`_macros.html:149-151` defines a single `alert(msg)` macro: `role="alert"`, an `alert-triangle` icon,
and the `.alert` class — which is hard-coded to `--danger-soft` background and `--danger` text. Two
templates pass a success string into it: `configuracoes.html:15`
(`{% if sucesso %}{{ ui.alert(sucesso) }}{% endif %}`) and `conta.html:45`. A user who exports a
backup or changes their password is told so in a red box with a warning triangle, immediately above
the identically-styled red box used for real failures on line 16.

### Why it matters

Colour is the fastest signal in the interface, and here it says the opposite of the truth. On the
Configurações screen the success and error banners are adjacent lines in the template, so a user
cannot distinguish "backup exported" from "backup failed" by appearance at all. On the conta screen
the message follows a password change — precisely the moment a user needs certainty. The rest of the
app already has correct success semantics via the green-bordered `#msg` toast, which makes this an
inconsistency as well as a misread.

### Concrete fix

Add a `variante="danger"` parameter to the `alert()` macro in `_macros.html:149`, using it to pick the
class (`alert--{{ variante }}`), the icon (`check` versus `alert-triangle`) and the ARIA role
(`status` versus `alert`). Then add `.alert--success { background: var(--success-soft); color:
var(--success); }` to `app.css`, mirroring the existing badge variants, and pass
`variante="success"` at the two `sucesso` call sites.

### Domain details

#### Screens

- Configurações (backup export/restore, WhatsApp, empresa, tema)
- Conta (troca de senha)

#### Frequency of exposure

Every settings save and every password change.

#### Propagation

One macro plus one CSS rule; two call sites updated.

#### Acceptance criteria

- A successful backup export shows a green confirmation with a check icon.
- A failed export still shows the red danger alert.
- Screen readers get `role="status"` for success and `role="alert"` for failure.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Fully verifiable statically: one macro, one CSS class, two `sucesso` call sites, all read.
  - The success-styling precedent already exists in `#msg` and `.badge--success`.
- **Weaknesses:**
  - I did not confirm that `sucesso` is actually populated on all the settings actions; if some paths
    never set it, the exposure is narrower than stated.
- **Suggested checks:**
  - Trigger a settings save and confirm the banner colour.

## imp-20260801-008 — The compra delete confirmation prints a literal backslash-n instead of a line break

- **Impact:** Medium
- **Category:** Consistency
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** destructive, copy, htmx, confirm
- **Files affected:** `bases/xtreme_system/api/templates/_row_compra.html`, `bases/xtreme_system/api/templates/base.html`
- **Related opportunities:** imp-20260801-007, imp-20260801-010

### Location

`bases/xtreme_system/api/templates/_row_compra.html:18` — row actions

```html
      <a class="btn btn--ghost btn--sm btn--focus action-view" href="/ui/veiculos/{{ c.veiculo.id }}/detalhes" aria-label="Ver detalhes de {{ c.veiculo.modelo }}">{{ ui.icon("eye") }}</a>
      {% if pode_editar %}
      <button class="btn btn--ghost btn--sm action-edit" hx-get="/ui/compras/{{ c.id }}/editar" hx-target="#modal" hx-swap="innerHTML" aria-label="Editar compra {{ c.id }}">{{ ui.icon("edit") }}</button>
      {% endif %}
      {% if pode_abrir_comprovante %}
      {% include "_action_compra_comprovantes.html" %}
      {% endif %}
      {% if pode_excluir %}
      <button class="btn btn--ghost btn--sm btn--danger action-delete" hx-post="/ui/compras/{{ c.id }}/excluir" hx-target="#linhas" hx-swap="outerHTML" hx-confirm="Excluir esta compra?\n\nAtenção: O veículo {{ c.veiculo.modelo }} ({{ c.veiculo.placa }}) também será deletado." aria-label="Excluir compra {{ c.id }}">{{ ui.icon("trash") }}</button>
      {% endif %}
    </div>
  </td>
```

### Description

The `hx-confirm` string embeds `\n\n`. In an HTML attribute that is two literal characters, not a
newline — the escape sequence only means "newline" inside a JavaScript string literal. The app
replaces the native `confirm()` with `showConfirmDialog` (`base.html:183-206`), which assigns the
question via `textContent` on a `<p>`. So the dialog renders one run-on line reading
`Excluir esta compra?\n\nAtenção: O veículo Corolla (ABC1D23) também será deletado.` Even had the
newline been real, `textContent` in a non-`pre` element collapses it to a space.

### Why it matters

This is the most consequential confirmation in the app — deleting a compra cascades to the vehicle.
The warning is the one piece of copy that stops an accidental cascade, and it is rendered with
visible escape artefacts that read as a bug. Users who see obviously broken UI text trust the rest of
the message less, and the emphasis the author intended (a separate warning paragraph) is lost
entirely.

### Concrete fix

Split the confirm into structured text. Either drop the escape and let it be one sentence, or extend
`showConfirmDialog` to accept an optional detail line and pass it via a second attribute. The
one-line version is to delete the `\n\n` so the attribute reads
`hx-confirm="Excluir esta compra? O veículo ... também será deletado."`. If multi-paragraph confirms are wanted app-wide, have `showConfirmDialog` split the question on a
sentinel and render each part as its own `<p>`.

### Domain details

#### Screens

- Compras → row action "Excluir compra"

#### Frequency of exposure

Every compra deletion; low volume but maximum consequence.

#### Propagation

One attribute, or one shared dialog helper if multi-line support is added.

#### Acceptance criteria

- The confirm dialog shows no `\n` characters.
- The cascade warning about the vehicle remains visible and distinguishable from the question.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - The literal `\n\n` is present in the template source, and `showConfirmDialog`'s use of
    `textContent` is confirmed at `base.html:194`.
- **Weaknesses:**
  - Not rendered; I am reasoning about HTML attribute parsing rather than observing the dialog.
- **Suggested checks:**
  - Click delete on a compra and read the dialog text.

## imp-20260801-009 — Only the compra form guards against double submit; every other money form can be submitted twice

- **Impact:** Medium
- **Category:** Feedback and system state
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** htmx, forms, double-submit, consistency, money
- **Files affected:** `bases/xtreme_system/api/templates/_form_compra.html`, `bases/xtreme_system/api/templates/_form_venda.html`, `bases/xtreme_system/api/templates/_form_cliente.html`, `bases/xtreme_system/api/templates/_form_custo_veiculo.html`, `bases/xtreme_system/api/templates/_modal_fechamento_venda.html`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-002

### Location

`bases/xtreme_system/api/templates/_form_compra.html:4` — the only form with submit guards

```html
  <div class="modal__panel{% if not compra %} modal__panel--wizard{% endif %}" role="dialog" aria-modal="true" aria-labelledby="mc-title">
    <div class="modal__head">
      <h3 id="mc-title">{{ 'Editar compra' if compra else 'Nova compra' }}</h3>
      <button class="icon-btn" data-testid="compra-wizard-close" type="button" aria-label="Fechar"
              onclick="closeModalOnBackdrop(this.closest('.modal'))">{{ ui.icon("close") }}</button>
    </div>
    <form hx-post="/ui/compras{% if compra %}/{{ compra.id }}{% endif %}" hx-target="#modal" hx-swap="innerHTML"
          hx-encoding="multipart/form-data" enctype="multipart/form-data"
          hx-sync="this:drop" hx-disabled-elt="find button[type='submit']"
          {% if not compra %}id="form-nova-compra"{% endif %}>
      <div class="modal__body">
        {% if erro %}{{ ui.alert(erro) }}{% endif %}
```

### Description

`_form_compra.html` is the only template in the app carrying `hx-sync="this:drop"` and
`hx-disabled-elt="find button[type='submit']"`. Everywhere else — venda create and edit, cliente,
custo, usuário, lançamento, and the fechamento confirm — relies solely on the CSS at
`app.css:810-811`, which sets `pointer-events: none` and a spinner on `form.htmx-request .btn--primary`
while a request is in flight. `pointer-events: none` blocks mouse clicks but not keyboard activation:
a user who presses Enter, or who has the button focused and hits Space, fires a second identical POST.
The button is also not `disabled`, so it remains in the tab order and is still activatable.

### Why it matters

These forms create financial records — a venda, a compra, a custo, a fechamento with irreversible
profit distribution. On a slow save, a keyboard-driven user pressing Enter twice creates a duplicate.
The CSS spinner also has no effect on `.btn--default` buttons, so the wizard's "Próximo"/"Voltar"
row gives no visual state at all. And because the guard exists in exactly one template, the
protection level is inconsistent in a way no reviewer would predict.

### Concrete fix

Promote the compra form's two attributes to every HTMX form. The lowest-touch route is a global
default on the `<body>` tag in `base.html`
(`hx-disabled-elt="closest form button[type='submit']"`), since htmx supports inherited attributes;
or, more surgically, add `hx-sync="this:drop" hx-disabled-elt="find button[type='submit']"` to the
`<form>` tag of `_form_venda.html`, `_form_cliente.html`, `_form_custo_veiculo.html`,
`_form_usuario.html`, `_form_lancamento.html` and `_modal_fechamento_venda.html`.

### Domain details

#### Screens

- Nova/Editar venda, Novo/Editar cliente, Novo custo, Novo usuário, Novo lançamento, Fechamento

#### Frequency of exposure

Every save; the failure only manifests on slow responses, which is exactly when users retry.

#### Propagation

Either one attribute on `<body>` or one line per form template.

#### Acceptance criteria

- Pressing Enter twice quickly on a venda save issues one POST.
- The submit button is genuinely `disabled` (not just pointer-blocked) during the request.
- The wizard's "Próximo" button shows an in-flight state when it triggers a request.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The presence of the guard in exactly one template and its absence elsewhere was verified by grep.
  - `pointer-events: none` not blocking keyboard activation is specified CSS behavior.
- **Weaknesses:**
  - I did not verify server-side idempotency; the backend may already reject duplicates, which would
    reduce this from a data problem to a feedback problem.
  - htmx attribute inheritance on `<body>` needs testing against the OOB swap flows.
- **Suggested checks:**
  - Throttle the network, submit a venda twice via Enter, and count the created rows.

## imp-20260801-010 — Icon-only row actions place irreversible delete beside edit with no hover tooltips

- **Impact:** Medium
- **Category:** Accessibility and responsiveness
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** tables, destructive, tooltips, mis-click, a11y
- **Files affected:** `bases/xtreme_system/api/templates/_row_venda.html`, `bases/xtreme_system/api/templates/_row_compra.html`, `bases/xtreme_system/api/templates/_row_veiculo.html`, `bases/xtreme_system/api/templates/_row_cliente.html`, `bases/xtreme_system/api/templates/_row_custo_veiculo.html`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-008

### Location

`bases/xtreme_system/api/templates/_row_venda.html:48` — the action cluster

```html
      <button class="btn btn--ghost btn--sm action-cash" hx-get="/ui/vendas/{{ v.id }}/fechamento" hx-target="#modal" hx-swap="innerHTML" aria-label="Fechar venda {{ v.id }}">{{ ui.icon("cash") }}</button>
      {% endif %}
      {% if pode_editar %}
      <button class="btn btn--ghost btn--sm action-edit" hx-get="/ui/vendas/{{ v.id }}/editar" hx-target="#modal" hx-swap="innerHTML" aria-label="Editar venda {{ v.id }}">{{ ui.icon("edit") }}</button>
      {% endif %}
      {% if pode_excluir %}
      <button class="btn btn--ghost btn--sm btn--danger action-delete" hx-post="/ui/vendas/{{ v.id }}/excluir" hx-target="#linhas" hx-swap="outerHTML" hx-confirm="Excluir esta venda?" aria-label="Excluir venda {{ v.id }}">{{ ui.icon("trash") }}</button>
      {% endif %}
    </div>
  </td>
  {% endif %}
</tr>
```

### Description

Every list row ends with up to five icon-only buttons in a `.row-actions` flex row with
`gap: var(--s-1)` and `.btn--sm { height: 28px; padding: 0 var(--s-2) }` — roughly 28px targets
separated by 4px. They are distinguished only by icon glyph and colour (`.action-edit` green,
`.action-delete` red, `.action-cash` blue, `.action-file` orange, `.action-view` orange). They carry
`aria-label` but, with one exception, no `title` — so a mouse user gets no tooltip and must infer
meaning from a 16px glyph. `_row_venda.html:44` is the exception, using `title="Regerar contrato"`,
which makes the convention inconsistent as well as absent.

### Why it matters

Delete sits immediately adjacent to edit, at the row's right edge, at a size below the 44px comfort
target — on a laptop trackpad a 4px miss between two 28px buttons is a routine slip. The `hx-confirm`
dialog is the only thing standing between a slip and a deleted venda, and confirmations are dismissed
reflexively when they appear frequently. Two of the colours (`.action-file` and `.action-view`) are
identical orange, so colour alone does not disambiguate either. Colour-blind users lose the primary
signal entirely.

### Concrete fix

Three small changes, in order of value: add `title` matching each `aria-label` so hover explains the
icon; separate the destructive button with a left margin or a divider
(`.row-actions .action-delete { margin-left: var(--s-2); }`); and raise the touch target with
`.btn--sm { min-width: 32px }`. All three live in `app.css` plus a `title` attribute per button.

### Domain details

#### Screens

- Vendas, Compras, Veículos, Clientes, Custos, Usuários, Investidores — every list row.

#### Frequency of exposure

Continuous — row actions are the main interaction surface of the app.

#### Propagation

The spacing and sizing fixes are single CSS rules affecting all lists; the `title` attributes are
per-button across five row templates.

#### Acceptance criteria

- Hovering any row action shows a text tooltip.
- The delete button is visually separated from the adjacent non-destructive action.
- No two adjacent actions in the same row share an identical colour.

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** No
- **Strengths:**
  - Button sizing, gap and the colour classes are all read from `app.css:276-287` and `418`.
  - The `title`/`aria-label` inconsistency is verifiable in the same file.
- **Weaknesses:**
  - I have no mis-click telemetry; the risk is inferred from target size and adjacency, not measured.
  - "Users dismiss confirmations reflexively" is a general usability claim, not evidence from this app.
- **Suggested checks:**
  - Ask daily users whether they have ever deleted the wrong row.

## imp-20260801-011 — The column configurator bypasses the app's modal system: no focus management and drag-only reordering

- **Impact:** Medium
- **Category:** Accessibility and responsiveness
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** a11y, keyboard, modals, tables, javascript
- **Files affected:** `bases/xtreme_system/api/static/columns.js`, `bases/xtreme_system/api/templates/base.html`
- **Related opportunities:** imp-20260801-012

### Location

`bases/xtreme_system/api/static/columns.js:161` — `openPanel`

```javascript
    overlay.innerHTML =
      '<div class="modal__panel" role="dialog" aria-modal="true" ' +
      'aria-label="Configurar colunas" style="max-width:400px">' +
      '<div class="modal__head"><h3>Colunas</h3></div>' +
      '<div class="modal__body">' +
      '<p class="cols-hint">Arraste para reordenar. Desmarque para ocultar.</p>' +
      '<ul class="cols-list"></ul></div>' +
      '<div class="modal__foot">' +
      '<button type="button" class="btn btn--default" data-reset>Restaurar padrão</button>' +
      '<button type="button" class="btn btn--primary" data-close>Fechar</button>' +
      "</div></div>";
```

### Description

`base.html` builds real modal infrastructure — a `MutationObserver` on `#modal` that moves focus into
the panel, a Tab-cycling focus trap, Escape handling, and focus restoration to the triggering element
(lines 150-278). All of it is scoped to `document.querySelector("#modal > .modal")`. `openPanel`
appends its overlay to `document.body` instead, so it inherits none of that: focus stays on the
"Colunas" button behind the overlay, Tab walks the page underneath, and closing restores nothing.
It reimplements only Escape (line 225) and backdrop click. Separately, reordering is implemented
purely through HTML5 drag events (lines 203-218) with no keyboard alternative, and the `<li>` items
have `draggable=true` but no `role`, `tabindex` or move affordance. `showConfirmDialog` in
`base.html:183` has the same body-append pattern; it at least focuses the OK button, but also has no trap.

### Why it matters

Column configuration is a power-user feature that persists to `localStorage` and materially changes
what data a user sees every day. Making it reachable only by mouse-drag excludes keyboard and
assistive-tech users from a personalization feature everyone else has. The missing focus trap is the
more common daily annoyance: opening the panel and pressing Tab moves focus behind the overlay, so
keyboard users interact with a page they cannot see.

### Concrete fix

Render the panel into `#modal` instead of `document.body` so it inherits the existing focus, trap and
Escape behavior, dropping the duplicated Escape handler. For reordering, add "move up / move down"
buttons next to the grip — this is both the keyboard path and a faster mouse path than dragging.
Each `<li>` in the `openPanel` template gains a pair of
`<button type="button" class="btn btn--ghost btn--sm" data-move="-1" aria-label="Mover para cima">`
controls, and a single delegated `click` handler on `.cols-list` swaps the item with its sibling and
calls the existing `persist()`.

### Domain details

#### Screens

- Every list page's "Colunas" button (injected into `.page-head__actions` by `ensureButton`)

#### Frequency of exposure

Occasional per user, but the setting it controls affects every subsequent table view.

#### Propagation

One JS file. Reusing `#modal` also removes duplicated Escape/backdrop logic.

#### Acceptance criteria

- Opening "Colunas" moves keyboard focus into the panel.
- Tab cycles only within the panel; Escape closes it and returns focus to the trigger.
- Column order can be changed entirely from the keyboard.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Both sides read in full: the `#modal`-scoped machinery in `base.html` and the `document.body`
    append in `columns.js:240`.
  - The drag-only reorder path is unambiguous — `dragstart`/`dragover`/`dragend` with no key handler.
- **Weaknesses:**
  - Rendering into `#modal` may conflict if a server-driven modal is already open; the interaction
    needs checking.
  - Not tested with a screen reader, so the practical severity for AT users is estimated.
- **Suggested checks:**
  - Open "Colunas" and press Tab repeatedly; observe where focus lands.

## imp-20260801-012 — Settings tabs declare ARIA roles they do not fulfil and have an invisible keyboard focus indicator

- **Impact:** Medium
- **Category:** Accessibility and responsiveness
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** a11y, aria, keyboard, css, settings
- **Files affected:** `bases/xtreme_system/api/templates/configuracoes.html`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-011

### Location

`bases/xtreme_system/api/templates/configuracoes.html:19` — CSS-only tab implementation

```html
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-banco" {% if aba_ativa == "banco" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-whatsapp" {% if aba_ativa == "whatsapp" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-tema" {% if aba_ativa == "tema" %}checked{% endif %}>
  <input class="settings-tabs__input" type="radio" name="settings-tab"
         id="tab-empresa" {% if aba_ativa == "empresa" %}checked{% endif %}>

  <div class="settings-layout">
    <nav class="settings-nav" role="tablist" aria-label="Seções de configurações">
      <label class="settings-nav__item" for="tab-banco" role="tab">
        <span class="settings-nav__icon">{{ ui.icon("database") }}</span>
```

### Description

The tabs are a checked-radio + sibling-selector pattern. The `<nav>` claims `role="tablist"` and each
`<label>` claims `role="tab"`, but none carries `aria-selected` or `aria-controls`, and the
`<section class="settings-tabs__panel">` elements have no `role="tabpanel"` and no `aria-labelledby`.
The declared roles therefore promise a relationship the markup does not provide — a screen reader
announces four tabs with no indication of which is active and no path to the associated panel.
Separately, `app.css:509` hides the real focusable control:
`.settings-tabs__input { position: absolute; opacity: 0; pointer-events: none; }`. The radio remains
in the tab order, so keyboard focus lands on an element with zero opacity; the global
`:focus-visible { box-shadow: var(--ring) }` at line 151 renders on an invisible box. The visible
`<label>` never receives focus and has no `:focus-within` styling.

### Why it matters

A keyboard user tabbing into Configurações loses the focus indicator entirely — arrow keys do change
tabs (native radio behavior), but nothing on screen shows where focus is, so the interaction feels
random. Configurações holds destructive operations, including database restore; navigating it blind
is the wrong place to have an invisible cursor. Announcing `role="tab"` without `aria-selected` is
worse than announcing nothing, since it sets an expectation of state that never arrives.

### Concrete fix

Two changes. Style the visible label from the hidden input's focus state, which the existing
`#tab-x:checked ~ ...` selector chain already demonstrates — one rule per tab of the form
`.settings-tabs__input:focus-visible ~ .settings-layout .settings-nav label[for="tab-banco"]
{ box-shadow: var(--ring); }`. And either complete the ARIA (`role="tabpanel"` plus `aria-labelledby` on each `<section>`, and
`aria-selected` toggled server-side from `aba_ativa`) or drop the `role="tablist"`/`role="tab"`
attributes so assistive tech falls back to the accurate radio-group semantics.

### Domain details

#### Screens

- Configurações → Backup / Tema / Empresa / WhatsApp

#### Frequency of exposure

Lower than the list screens, but it is the entry point for backup, restore and company data.

#### Propagation

One template plus one CSS block; the selector pattern is already established in the file.

#### Acceptance criteria

- Tabbing into the settings navigation shows a visible focus ring on the active label.
- Arrow-key navigation between tabs moves the visible focus indicator.
- A screen reader announces the selected tab, or the tab roles are removed entirely.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - The absent `aria-selected`/`aria-controls`/`role="tabpanel"` is verifiable in the template source.
  - `opacity: 0` leaving an element focusable but invisible is standard CSS/HTML behavior.
- **Weaknesses:**
  - Not tested with a screen reader, so the exact announcement is inferred from the ARIA spec.
  - Whether users actually reach these tabs by keyboard is unknown; the mouse path works fine.
- **Suggested checks:**
  - Tab into Configurações with a visible-focus browser setting and observe the indicator.

## imp-20260801-013 — Checkbox fields in the venda form use nested labels, breaking click-to-toggle and label association

- **Impact:** Medium
- **Category:** Form ergonomics
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** forms, a11y, html-validity, vendas
- **Files affected:** `bases/xtreme_system/api/templates/_form_venda.html`
- **Related opportunities:** imp-20260801-015

### Location

`bases/xtreme_system/api/templates/_form_venda.html:66` — "Houve troca" field, edit branch

```html
          {% if pode_ver_campo(user, 'vendas', 'veiculo_troca') or pode_ver_campo(user, 'vendas', 'valor_diferenca') %}
          <label class="field field--full">
            <span class="field__label">Troca</span>
            <label>
              <input id="houve-troca" type="checkbox"{% if venda.veiculo_troca_id %} checked{% endif %}>
              Houve troca de veículo?
            </label>
          </label>
          {% endif %}
          {% if pode_ver_campo(user, 'vendas', 'veiculo_troca') %}
          <label class="field" data-troca>
            <span class="field__label">Veículo da troca</span>
```

### Description

A `<label>` may not contain another `<label>`; the HTML spec forbids it and the parse result is
browser-dependent. The pattern appears three times in `_form_venda.html` — lines 67-73 and 352-358
("Houve troca de veículo?") and lines 153-159 ("Faltou parte do pagamento?"). The outer
`<label class="field">` wraps a `<span class="field__label">` plus an inner `<label>` holding the
checkbox. Because the outer label has no `for` and contains a labelable control, clicking anywhere in
it — including the "Troca" heading text — can toggle the checkbox, while the inner label's own
association is ambiguous. Every other field in the file uses the correct single-label shape.

### Why it matters

"Houve troca de veículo?" gates an entire block of conditional fields — checking it reveals the
trade-in vehicle search and its twelve sub-fields, unchecking it clears `hidden.value` and `input.value`
in `sincronizarTroca` (line 661-672). An accidental toggle from clicking the section heading silently
wipes the trade-in vehicle the user already selected. "Faltou parte do pagamento?" similarly controls
whether a pending balance is recorded. These are the two checkboxes in the app where a stray toggle
has real consequences.

### Concrete fix

Flatten to the standard shape — change the outer `<label class="field field--full">` to a `<div>` of
the same class, keeping the inner `<label>` that already wraps the checkbox and its text. That is a
two-character change per occurrence and preserves the existing layout, since `.field` styles do not
depend on the element being a label. Better still, add a `checkbox_field()` macro to `_macros.html` alongside the existing `field()` macro,
since the pattern repeats three times in this file.

### Domain details

#### Screens

- Nova venda (wizard step 4) and Editar venda

#### Frequency of exposure

Every venda involving a trade-in or a pending payment.

#### Propagation

Three occurrences in one template; a shared macro would prevent recurrence.

#### Acceptance criteria

- Clicking the "Troca" section heading does not toggle the checkbox.
- The markup passes HTML validation with no nested-label error.
- Toggling still shows and hides the `[data-troca]` fields as before.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - The nesting is plainly present at three verified line ranges, and the correct pattern is used
    everywhere else in the same file.
  - The consequence — `sincronizarTroca` clearing the selected trade-in vehicle — is read from the
    file's own script at lines 661-672.
- **Weaknesses:**
  - Browsers vary in how they resolve nested labels; the exact click behavior may differ between
    Chrome and Safari, and I did not test either.
- **Suggested checks:**
  - Click the word "Troca" in the edit-venda modal in Chrome and Safari and see whether the box toggles.

## imp-20260801-014 — Estoque is the only list with no record count and no pagination, rendering every vehicle in one table

- **Impact:** Medium
- **Category:** Information hierarchy
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** tables, pagination, consistency, performance-ux
- **Files affected:** `bases/xtreme_system/api/templates/veiculos.html`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/templates/_linhas_veiculos.html`
- **Related opportunities:** imp-20260801-005

### Location

`bases/xtreme_system/api/routes/ui_routes/veiculos.py:112` — `_listar_veiculos`

```python
        ],
        "filtro_tipo_entradas": [
            (t.value, t.value.capitalize()) for t in veiculo.TipoEntrada
        ],
    }


def _listar_veiculos(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[veiculo.Veiculo]:
    return veiculo.list_all(session, limit=limit, offset=offset)


def _buscar_veiculos(
    session: Session, term: str, column: str | None = None
) -> list[veiculo.Veiculo]:
```

### Description

Vendas, Compras, Clientes, Custos, Usuários and Investidores all end their page template with
`{{ ui.paginacao(...) }}`, which renders the "Mostrando X–Y" counter and the Anterior/Próxima
buttons. `veiculos.html` does not — the template ends at the closing `</div>` of `.table-wrap`
(line 86), and `_linhas_veiculos.html` has no `paginacao` call in its OOB branch either. The route
defaults `limit=None`, so the entire stock table is rendered in a single response. The user therefore
has no record count anywhere on the screen, no page size control, and — combined with the header
issue in imp-20260801-005 — an unbounded scroll through unlabelled columns.

### Why it matters

Estoque is the system's home screen for the vehicle operation and its most-visited list. "How many
cars do we have in stock?" is the single most common question it should answer, and the interface
never states it — the `_stats_veiculos.html` panel is included at line 17 but the table itself gives
no count of the filtered result set. After searching or filtering, the user cannot tell whether they
are looking at 3 matches or 300 without counting rows. The unbounded render also degrades steadily as
the dealership grows, with no ceiling.

### Concrete fix

Add the pagination macro to `veiculos.html` after the table, mirroring `vendas.html:85`, and give the
route the same `limit: int = 50, offset: int = 0` signature the other list routes use. If unbounded
rendering is a deliberate choice for stock, the minimum change is showing the result count in the
`.page-head__subtitle` or the toolbar so the number is visible.

### Domain details

#### Screens

- Veículos (Estoque)

#### Frequency of exposure

Highest-traffic screen in the vehicle workflow.

#### Propagation

One template addition and one route signature change; the macro, the OOB `#paginacao` swap and the
context variables all already exist and are proven on five other lists.

#### Acceptance criteria

- Estoque shows "Mostrando 1–50" (or the equivalent count) below the table.
- Anterior/Próxima navigate the stock list.
- Applying a search or column filter updates the displayed count.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Verified by comparison: `paginacao` present in `vendas.html`, `compras.html`, `clientes.html`,
    `custos_veiculos.html`, `usuarios.html`, `investidores.html`, absent in `veiculos.html`.
  - The `limit: int | None = None` default is read directly from the route helper.
- **Weaknesses:**
  - I did not trace the `/ui/veiculos` GET handler to confirm it calls `_listar_veiculos` without a
    limit rather than passing one; the default only shows the helper's own behavior.
  - Whether unbounded rendering was a deliberate product decision for stock is unknown.
- **Suggested checks:**
  - Load `/ui/veiculos` against a database with 500 vehicles and count the rendered rows.

## imp-20260801-015 — The venda wizard reports server errors with one banner and no indication of which step holds the bad field

- **Impact:** Medium
- **Category:** Error presentation
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** low
- **Tags:** forms, wizard, error-handling, vendas
- **Files affected:** `bases/xtreme_system/api/templates/_form_venda.html`, `bases/xtreme_system/api/static/app.css`
- **Related opportunities:** imp-20260801-003, imp-20260801-004, imp-20260801-006, imp-20260801-013

### Location

`bases/xtreme_system/api/templates/_form_venda.html:182` — wizard step state and stepper

```html
        <input type="hidden" name="wizard_step" id="wizard-step" value="{{ dados.get('wizard_step', 1) }}">
        <div class="stepper">
          <div class="stepper__item is-active" data-stepper="1">
            <span class="stepper__num">1</span>
            <span class="stepper__label">Cliente</span>
          </div>
          <div class="stepper__connector" data-connector="1"></div>
          <div class="stepper__item" data-stepper="2">
            <span class="stepper__num">2</span>
            <span class="stepper__label">Veículo</span>
          </div>
```

### Description

The four-step wizard shows exactly one step at a time — `.wizard-step { display: none }` with
`.is-active { display: grid }` (`app.css:471-472`). When the server rejects a submit, the form
re-renders with `{{ ui.alert(erro) }}` at the top of the modal body and the active step restored from
`dados.wizard_step`, which is the step the user was on when they hit Salvar (step 4). The failing
field, however, is frequently on step 1 (`cli_documento`) or step 3 (`valor_venda`) — hidden inside a
collapsed fieldset. The stepper has `is-active` and `is-done` states but no error state, so nothing
marks the step that needs attention. Combined with imp-20260801-003, the user sees a message like
`cli_documento: String should have at least 11 characters` while looking at the Troca step.

### Why it matters

The venda wizard is the highest-value flow in the app and the one with the most fields. Recovering
from an error means the user must guess which of four collapsed steps holds the problem and click
back through them comparing field names against a technical error string. That turns a one-character
typo into a multi-step hunt on every rejected sale.

### Concrete fix

Have the error path return the offending field names, map them to their step, and both (a) open that
step instead of the last one and (b) mark it on the stepper with a new error state — for example
`.stepper__item.is-error .stepper__num { border-color: var(--danger); color: var(--danger); }`
alongside the existing `is-active` and `is-done` rules. The smallest useful first increment, independent of any server change, is adding a per-step error
class driven by an `erro_step` context value, and defaulting the active step to 1 when an error is
present rather than to the last step.

### Domain details

#### Screens

- Vendas → Nova venda (4-step wizard: Cliente / Veículo / Valores / Troca)

#### Frequency of exposure

Every rejected new-sale submit.

#### Propagation

One template plus one CSS rule; the server-side field-to-step mapping is the larger part and shares
its groundwork with imp-20260801-003.

#### Acceptance criteria

- A rejected submit caused by a step-1 field opens the wizard on step 1.
- The stepper visually marks the step containing the error.
- The error banner names the field label, not the form field name.

### Self-critique

- **Confidence:** 7/10
- **Uncertain:** Yes
- **Strengths:**
  - Step visibility, stepper states and `wizard_step` restoration were all read directly from the
    template and CSS.
- **Weaknesses:**
  - I could not find `wizard_step` handled anywhere in the Python routes, so whether
    `dados.wizard_step` survives the round trip at all is unverified — the wizard may in fact always
    reopen on step 1, which changes the symptom (though not the missing error state).
  - I did not enumerate which validations fire server-side versus client-side, so the frequency of
    server-rejected submits is estimated.
- **Suggested checks:**
  - Grep the venda preparation code for `wizard_step` handling and confirm what step the form reopens on.
  - Submit a wizard with an invalid document and observe which step is displayed.

## Discarded candidates

### `debitos` defaults to `"0,00"` in the compra form but empty in the venda form

Real inconsistency (`_form_compra.html:58` versus `_form_venda.html:49`) but low impact: both accept
the same input and `filters.js` normalizes either. Cosmetic rather than friction-causing.

### Generic "Alterações salvas com sucesso." toast for every write, including deletes

`crud_ui/responses.py:17-20` uses one message for create, update and delete. Slightly imprecise, but
the toast is confirmatory rather than informational and the list refresh alongside it already shows
the actual outcome. Low impact.

### `ensureButton` in `columns.js` binds one "Colunas" button per page even with multiple tables

`columns.js:120-132` queries `.page-head__actions` globally and returns early if a button exists, so a
page with two configurable tables would configure only the first. No current page renders two
`table[data-table]` elements, so it is latent rather than live.

### Hardcoded `colspan="15"` on the empty-state row

`_linhas_veiculos.html:4` spans a fixed 15 columns while the header count varies with per-user field
permissions. Because `.table--wide` sets a 900px minimum and the empty state is centered text, the
visual result is unaffected. Correctness nit, not UX friction.

### Search input has no result-count announcement for screen readers

`veiculos.html:40-44` swaps `#linhas` on keyup with a spinner via `.search:has(.input.htmx-request)`,
but nothing announces how many rows came back. Genuine, but it is a subset of imp-20260801-014's
missing-count problem and would be fixed by the same change.
