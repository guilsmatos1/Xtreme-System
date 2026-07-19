---
paths:
  - "bases/xtreme_system/api/templates/**"
  - "bases/xtreme_system/api/static/**"
  - "**/*.html"
---

# Frontend (Jinja2 + HTMX)

- This project has no JS framework — server-rendered Jinja2 templates plus vanilla `htmx.min.js`. Don't introduce React/Vue/build tooling for a single feature.
- Partial templates (prefixed `_`, e.g. `_row_venda.html`, `_linhas_vendas.html`) are HTMX swap targets — keep them minimal fragments, not full pages. Full pages extend `base.html`.
- Use HTMX attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`) over hand-written `fetch`/JS unless the interaction genuinely needs client-side logic (see `columns.js`).
- Styling lives in `static/app.css` — reuse existing classes/tokens before adding new ones. No inline `style=` unless truly one-off.
- Forms and error responses returned to HTMX targets should render the same partial template used for the success case, so validation errors show in place.
- Accessibility: labeled form inputs, sufficient contrast, keyboard-operable controls — this is an internal tool but still used daily by non-technical staff.
- Don't add client-side state management; server state (DB) + HTMX swaps is the pattern here.
