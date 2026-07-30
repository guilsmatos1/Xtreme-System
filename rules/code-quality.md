# Code Quality

## Anti-defaults (counter common Claude tendencies)

- No premature abstractions. Three similar lines beats a helper used once.
- Don't add features or issues beyond what was asked.
- Don't refactor adjacent code while fixing a bug.
- No dead code or commented-out blocks. Git has history.
- WHY comments, never WHAT. If code needs a "what" comment, rename instead.
- No error handling or validation for scenarios that can't happen.

## Naming

- Files and modules: `snake_case.py`, matching Polylith component/base conventions (`core.py`, `workflows.py`, `models.py`).
- Booleans: `is_` / `has_` / `deve_` prefix. Functions: verb-first, matching existing PT-BR domain terms where the codebase already uses them (`fechamento_venda`, `dedup_resolver`).
- Custom exceptions: `<Domínio>Error` (e.g. `FechamentoVendaError`), raised in `core.py`.
- Constants: `SCREAMING_SNAKE_CASE`.

## File Organization

- Imports: stdlib, third-party, internal (`components.xtreme_system.*`, `bases.xtreme_system.*`), relative. Blank line between groups. `ruff` enforces ordering — don't hand-sort against it.
- One responsibility per module: business invariants in `core.py`, FK/availability checks in `workflows.py`, route-specific 400/409 handling in `bases/api/routes/`.
- Function order: public API first, then helpers in call order.
- Respect Polylith component boundaries — don't import across components except through their public `core`/`workflows` interface. `ruff`/pylint's polylith lint (pre-commit) enforces this.
