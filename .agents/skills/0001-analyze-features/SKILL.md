---
name: 0001-analyze-features
description: Analyze the system from the product/functionality angle and identify the 10 highest-impact functional improvements, prioritized by value to the end user. Use when asked what features are missing, what workflows are incomplete or awkward, what business rules are unenforced, or for a prioritized roadmap of functional improvements tied to specific routes, components, and screens.
---

# Analyze Features

Analyze this system as a **product**, not as source code, and identify the 10 best opportunities to
improve its functionality, prioritized by value delivered to the people who use it.

The question is not "is this code well written?" — it is **"what can a user not do today, do badly,
or do in a way that lets bad data into the system?"**

## Scope

The system is a vehicle dealership management platform (Polylith + FastAPI + HTMX + Jinja).
Ground every finding in what actually exists:

- `bases/xtreme_system/api/routes/ui_routes/*.py` — the real user-facing screens and actions.
- `bases/xtreme_system/api/templates/` — what the user actually sees and can click.
- `components/xtreme_system/*/core.py` — the business rules that are (or are not) enforced.
- `components/xtreme_system/*/workflows.py` — multi-step operations and their gaps.
- `DATABASE.md` — fields that exist in the schema but are never surfaced or filled in the UI.
- `API.md` — contracts exposed to integrations and what they can't express.

Read `README.md` first for the product overview, then map the domains:
veículo, compra, venda, fechamento de venda, cliente, investidor, caixa/lançamentos, custos,
documentos, uploads/imagens, perfis e permissões, auditoria, relatórios, exportação, WhatsApp.

## Analysis Dimensions

For each domain, evaluate:

1. **Workflow completeness** — can the user finish the job end-to-end, or does the flow dead-end
   and force manual work outside the system (planilha, WhatsApp, papel)?
2. **Unenforced business rules** — invariants the domain implies but no code checks
   (e.g. selling a vehicle that isn't in stock, closing a sale without covering all costs,
   negative cash balance, duplicated CPF/placa/chassi).
3. **Dead schema** — columns, enums, and relationships in the database with no screen, no form
   field, and no report reading them.
4. **Missing reads** — data the system already stores but never shows back:
   margin per vehicle, aging of stock, investor position, receivables, cash flow over time.
5. **Manual steps that should be automatic** — recalculations, status transitions, document
   generation, notifications the user has to remember to trigger.
6. **Permissions and multi-user reality** — what a limited profile can't do that it should,
   or can do that it shouldn't; concurrent edits on the same vehicle or sale.
7. **Error recovery** — can the user undo, correct, or reopen? Cancelamento, estorno, edição de
   lançamento, reabertura de fechamento.
8. **Friction** — number of clicks/screens for the most frequent operations, re-typed data,
   absent search/filter/sort where the list grows unbounded.
9. **Integrations** — what an external system (contabilidade, banco, marketplace, WhatsApp)
   would need and can't get today.
10. **Trust** — auditability, traceability of money, and whether the user can explain a number
    the system shows them.

## Method

1. Read `README.md`, `ARCHITECTURE.md`, `DATABASE.md`, `API.md`.
2. Enumerate every UI route and the actions it exposes. Build the real feature inventory.
3. For each core domain, trace one complete happy path in the code
   (ex: compra → estoque → custos → venda → fechamento → caixa) and mark exactly where it breaks,
   stops, or requires the user to know something the system doesn't tell them.
4. Diff the schema against the UI to find dead fields (dimension 3).
5. Rank candidates by **user value × frequency of use**, discounted by implementation cost.
   Prefer one high-value gap over three cosmetic ones.
6. Keep the 10 best.

## Rules

- Every finding must cite concrete evidence: a route, a template, a model field, a function.
  No generic product advice that could apply to any system.
- Describe the gap in terms of the user's job, then in terms of the code.
- Do not propose features the business clearly doesn't want; if a gap looks intentional, say so
  and lower its priority instead of inventing a requirement.
- Do not propose rewrites, refactors, or code-quality cleanups — that is `0001-analyze-codebase`.
- If a proposal needs a schema change, say which table and column, and flag the migration cost.
- If you are unsure whether a feature already exists, search before claiming it's missing.
  If still unsure, mark it explicitly as uncertain and lower its priority.

## Output Format

Use exactly this text format for each of the 10 items, most valuable first. No Markdown tables.

```text
## <short title of the functional improvement>

Domain: <veículo | venda | fechamento | caixa | cliente | investidor | permissões | relatórios | ...>
Evidence: path/to/file.py:123 (and other relevant files)
User value: High | Medium | Low
Frequency of use: Daily | Weekly | Occasional
Estimated effort: Low | Medium | High
Schema change required: yes/no (<table.column> if yes)

What the user can't do today:
<the gap described from the user's point of view>

Evidence in the system:
<what the code/schema/templates show, tied to the cited files>

Proposed behavior:
<the smallest version of the feature that solves the problem end-to-end>

Acceptance criteria:
- <verifiable statement 1>
- <verifiable statement 2>
- <verifiable statement 3>
```

Close the report with a short section:

```text
## Descartados

<3–6 candidates you considered and rejected, one line each, with the reason>
```

## Persistence

- Write the final report to `docs/0001-feature-analysis.md`.
- Overwrite the file if it already exists, unless the user asks for another filename.
- Markdown only, no tables, matching the format above item by item.

**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**
The report is the deliverable and it goes to `docs/0001-feature-analysis.md` ONLY.
Reply in the terminal with a single line pointing to the file.
