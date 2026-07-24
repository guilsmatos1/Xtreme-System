---
name: 0001-analyze-ui-ux
description: Analyze the system's UI/UX and visual design and identify the 10 highest-impact interface improvements, prioritized by how much friction they remove for the daily user. Use when asked for a UX review, design audit, interface critique, accessibility check, visual consistency review, form/table usability analysis, or a prioritized list of concrete UI improvements tied to specific templates, CSS rules, and screens.
---

# Analyze UI/UX

Analyze this system as an **interface**, not as source code and not as a feature set, and identify
the 10 best opportunities to improve the experience of using it, prioritized by how much friction
each one removes for someone who works in the system every day.

The question is not "is the code clean?" nor "what feature is missing?" — it is
**"where does the person using this screen hesitate, misread, mis-click, retype, or give up?"**

## Scope

Vehicle dealership management platform, server-rendered: FastAPI + Jinja + HTMX, hand-written CSS.
Users are dealership staff on desktop, working long sessions with dense lists and long forms.

Ground every finding in what actually exists:

- `bases/xtreme_system/api/templates/base.html` — global layout, navigation, page shell.
- `bases/xtreme_system/api/templates/_macros.html` — the de-facto design system (inputs, buttons,
  tables, modals). Inconsistency almost always means "a template bypassed a macro".
- `bases/xtreme_system/api/templates/_form_*.html` — the long forms (venda, veículo, compra are
  the biggest and the most used).
- `bases/xtreme_system/api/templates/_modal_*.html` — modal flows, uploads, nested actions.
- `bases/xtreme_system/api/templates/_linhas_*.html`, `_row_*.html` — list/table rendering.
- `bases/xtreme_system/api/static/app.css` — spacing, typography, color, states.
- `bases/xtreme_system/api/static/columns.js`, `filters.js` — client-side table behavior.
- `bases/xtreme_system/api/routes/ui_routes/*.py` — which fragment each interaction swaps in,
  and what the user sees while it happens.

Read `README.md` for the product context and `ARCHITECTURE.md` for the HTMX fragment flow before
judging any interaction.

## Analysis Dimensions

1. **Information hierarchy** — on each screen, is the most important thing the most visible thing?
   Are lists showing the columns the user actually decides with, or every column that exists?
2. **Form ergonomics** — field order matching the real-world order of the task, grouping, labels,
   placeholders vs labels, required-field signalling, sane defaults, tab order, input types
   (`type=number`, `inputmode`, masks for CPF/placa/valor), and length of the longest forms.
3. **Feedback and system state** — does the user know a request is in flight, succeeded, or failed?
   HTMX swaps without an indicator, silent failures, alerts that vanish or never appear,
   destructive actions without confirmation, no optimistic/disabled state on submit.
4. **Error presentation** — where validation errors surface, whether they point at the offending
   field, whether the user's typed data survives a failed submit.
5. **Consistency** — the same concept rendered differently across screens: button styles, table
   headers, modal structure, date/currency formatting, status badges, empty states, terminology
   (pt-BR wording drift between screens).
6. **Density and scanability** — line-height, column alignment (numbers right-aligned?),
   zebra/hover affordances, sticky headers on long tables, truncation that hides meaning.
7. **Navigation and wayfinding** — nav structure, active-state, breadcrumbs, deep links, what
   happens after a save (where does the user land?), back-button behavior with HTMX.
8. **Accessibility** — color contrast in `app.css`, focus-visible styles, labels tied to inputs,
   keyboard reachability of modals and custom controls, `aria-*` on dynamic regions, focus
   trapping and focus return on modal close, semantics of clickable non-buttons.
9. **Responsiveness** — behavior of wide tables and long forms below ~1280px and on tablets;
   horizontal scroll, overflowing modals, unusable controls at small widths.
10. **Visual craft** — spacing scale, typographic scale, color palette coherence, use of color to
    carry meaning (status, positive/negative money), shadows/borders/radii consistency, and
    whether dark/light or print/export views are broken.

## Method

1. Read `base.html` and `_macros.html` in full. That is the design system; write down what it
   defines and what it fails to define.
2. Read `app.css` looking for: how many distinct spacing values, font sizes, colors, radii and
   shadows exist; duplicated or overriding rules; `!important`; dead selectors.
3. Walk the 5 most-used screens end to end (lista de veículos, cadastro/edição de veículo,
   venda, fechamento de venda, caixa/lançamentos) and describe what the user sees at each step.
4. For each screen, grep the template for macro usage vs raw HTML. Raw HTML that duplicates a
   macro is a consistency finding with a concrete fix.
5. Check every destructive or money-changing action for confirmation and feedback.
6. Check every `hx-` attribute for a matching indicator, target and error path.
7. If the app can be run, render the main screens with the `playwright-cli` skill and screenshot
   them at 1440px and 1024px. If it cannot be run, say so and rely on template/CSS reading only —
   never invent visual observations you did not make.
8. Rank by **frequency of the affected screen × severity of the friction**, discounted by effort.
   One fix in `_macros.html` that corrects ten screens outranks a bespoke tweak on one screen.
9. Keep the 10 best.

## Rules

- Every finding must cite concrete evidence: a template path and line, a CSS selector, a macro
  name. No generic design advice that could apply to any web app.
- Describe the problem as the user experiences it first, then as the code that causes it.
- Prefer fixes in `_macros.html` and `app.css` over per-template patches; say explicitly which
  screens each fix propagates to.
- Respect the existing stack. Do not propose React, a CSS framework, a component library, a build
  step, or a full redesign. Work with Jinja macros, HTMX and hand-written CSS.
- Do not propose new features or new business rules — that is `0004-analyze-features`.
- Do not propose code-quality refactors — that is `0001-analyze-codebase`.
- Keep all user-facing copy suggestions in pt-BR, matching the existing terminology.
- If you are unsure whether a behavior exists (an indicator, a confirm dialog), search before
  claiming it's missing. If still unsure, mark it explicitly as uncertain and lower its priority.

## Output Format

Use exactly this text format for each of the 10 items, most impactful first. No Markdown tables.

```text
## <short title of the UI/UX improvement>

Screen(s): <lista de veículos | form de venda | fechamento | modais de upload | global | ...>
Category: <hierarquia | formulário | feedback | erro | consistência | densidade | navegação | acessibilidade | responsividade | visual>
Evidence: path/to/template.html:123 (and other relevant files)
User impact: High | Medium | Low
Frequency of exposure: Every session | Daily | Occasional
Estimated effort: Low | Medium | High
Propagates to: <how many screens this single fix improves>

What the user experiences today:
<the friction, described from the user's point of view, on a concrete task>

Evidence in the code:
<the template/CSS/HTMX detail that causes it, tied to the cited files>

Proposed change:
<the smallest concrete change — which macro, which CSS rule, which attribute>

Acceptance criteria:
- <verifiable statement 1>
- <verifiable statement 2>
- <verifiable statement 3>
```

Close the report with two short sections:

```text
## Sistema de design atual

<6–10 lines describing what _macros.html and app.css actually establish today: spacing scale,
type scale, palette, component set — and the concrete gaps in it>

## Descartados

<3–6 candidates you considered and rejected, one line each, with the reason>
```

## Persistence

- Write the final report to `docs/0001-ui-ux-analysis.md`.
- Overwrite the file if it already exists, unless the user asks for another filename.
- Markdown only, no tables, matching the format above item by item.

**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**
The report is the deliverable and it goes to `docs/0001-ui-ux-analysis.md` ONLY.
Reply in the terminal with a single line pointing to the file.
