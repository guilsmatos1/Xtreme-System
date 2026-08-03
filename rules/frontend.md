---
paths:
  - "bases/xtreme_system/api/templates/**"
  - "bases/xtreme_system/api/static/**"
  - "**/*.html"
---

# Frontend (Jinja2 + HTMX)

- No SPA framework and no build step — server-rendered Jinja2 templates plus vendored `htmx.min.js` and `alpine.min.js`. Don't introduce React/Vue or any bundler/toolchain; there is no Node dependency and `package-lock.json` is intentionally empty.
- Alpine (3.15.x, vendored in `static/` with `persist`/`focus`/`mask`) is allowed **only for ephemeral view state**: wizard step, open/closed, show/hide a field. Anything that outlives the page — domain data, what gets saved — stays on the server and travels over htmx.
- Alpine logic goes in `static/components.js` via `Alpine.data()`; templates only reference a component by name (`x-data="wizard(1)"`) and use simple directives (`x-show`, `x-bind`, `x-on`, `:class`). Don't write complex expressions inside attributes: it scatters logic across 78 templates, and Alpine's CSP-friendly build forbids arrow functions, template literals, destructuring, spread and `document`/`window`/`JSON` access in attributes.
- Beware `x-show` when the element is hidden by the stylesheet itself: `x-show` toggles inline `display`, so an element whose CSS default is `display: none` (like `.wizard-step`) will stay hidden. Bind the existing state class with `:class` instead.
- Scripts loaded once (`static/*.js`) must re-initialise on `htmx:load` — form fragments arrive by swap, long after `DOMContentLoaded`. See `reference.js`; `tests/e2e/test_reference_field.py` guards that contract.
- Partial templates (prefixed `_`, e.g. `_row_venda.html`, `_linhas_vendas.html`) are HTMX swap targets — keep them minimal fragments, not full pages. Full pages extend `base.html`.
- Use HTMX attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`) over hand-written `fetch`/JS unless the interaction genuinely needs client-side logic (see `columns.js`).
- Styling lives in `static/app.css` — reuse existing classes/tokens before adding new ones. No inline `style=` unless truly one-off.
- Forms and error responses returned to HTMX targets should render the same partial template used for the success case, so validation errors show in place.
- Accessibility: labeled form inputs, sufficient contrast, keyboard-operable controls — this is an internal tool but still used daily by non-technical staff.
- Don't add client-side state management for domain data; server state (DB) + HTMX swaps is the pattern here. Alpine's `$persist` is for user preferences only (theme, column layout), never for records.
