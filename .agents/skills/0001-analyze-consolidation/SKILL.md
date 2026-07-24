---
name: 0001-analyze-consolidation
description: Analyze the codebase for code consolidation opportunities — duplicated, near-duplicated, and redundant code that can be unified without losing any functionality. Use when asked to find duplication, copy-paste, repeated logic, parallel implementations of the same rule, redundant helpers/templates/queries, or a prioritized list of safe behavior-preserving merges.
---

# Analyze Consolidation

Find the places where this codebase says the same thing more than once, and propose how to say it
once — **without removing, weakening, or changing any existing behavior**.

The question is not "is this code good?" — it is **"where does one logical rule live in two or more
places, and what is the smallest behavior-preserving change that makes it live in one?"**

Consolidation here means: unify duplicates, collapse parallel implementations, reuse what already
exists. It does **not** mean invent new abstractions, add configurability, or generalize for
hypothetical future cases.

## Scope

The system is a vehicle dealership management platform (Polylith + FastAPI + HTMX + Jinja).
Look for duplication across all layers, and especially **across** layers:

- `components/xtreme_system/*/core.py` — business rules restated in more than one component.
- `components/xtreme_system/*/workflows.py` — repeated multi-step sequences and validation chains.
- `bases/xtreme_system/api/routes/` and `routes/ui_routes/` — route handlers that differ only in
  the entity they touch; repeated parsing, filtering, pagination, permission and error handling.
- `bases/xtreme_system/api/templates/` — near-identical Jinja blocks that should be one macro in
  `_macros.html`; forms, tables, filters, modals copy-pasted per domain.
- `bases/xtreme_system/api/crud_writes.py`, `components/xtreme_system/database/core.py` —
  transaction/commit/rollback patterns re-implemented per caller.
- Query construction — the same filter/join/ordering rebuilt in several routes.
- Formatting and coercion — currency, date, CPF/CNPJ, placa, decimal parsing done ad hoc.
- `tests/` — duplicated fixtures and setup that hide which behavior is actually pinned.

Read `ARCHITECTURE.md` first to respect layer boundaries: a consolidation that pulls route-level
logic into a component, or pushes component logic into a route, must be justified against the rules
in `CLAUDE.md` ("Placing validation") — invariants in `core.py`, FK/availability in `workflows.py`,
route-specific 400/409 in the routes.

## What Counts as a Consolidation Opportunity

1. **Literal duplication** — the same block copy-pasted in 2+ places.
2. **Near duplication** — same shape, differing only in a name, a field, or a constant.
3. **Parallel implementations** — the same rule computed twice with divergent details
   (this is the highest-value kind: the divergence is usually a latent bug).
4. **Reimplemented existing helper** — code that redoes what a function/macro already in the repo
   does; the fix is a call, not a new abstraction.
5. **Redundant layers** — a wrapper that only forwards, an indirection with a single caller on both
   sides, a component that exists only to re-export another.
6. **Template duplication** — repeated Jinja fragments that `_macros.html` should own.
7. **Dead-by-duplication** — one of the copies is unreachable or unused; the consolidation is a
   deletion. Verify with a repo-wide search before claiming it.

## What Does NOT Count

- Similar-looking code that encodes genuinely different rules. Coincidental shape is not duplication.
- Tests that intentionally repeat setup to stay readable and independent.
- Splitting large files/functions, typing weak contracts, breaking cycles — that is
  `0003-analyze-llm-adherence`.
- General code-quality or performance findings — that is `0001-analyze-codebase`.
- Any change that removes a capability, a validation, an error message, a status code, or a
  logged/audited event. If the copies differ in behavior, the consolidated version must keep the
  union of the behaviors, and you must say explicitly how.

## Method

1. Read `ARCHITECTURE.md`, `API.md`, `DATABASE.md`, and `CLAUDE.md`.
2. Sweep for repetition mechanically before judging: search for repeated function names, repeated
   literals and messages, repeated query fragments, repeated Jinja blocks. Use `rg` broadly.
3. For each candidate, open **every** occurrence and diff them line by line. Write down the exact
   differences — that list is what determines whether consolidation is safe.
4. Classify the candidate using the categories above.
5. Determine the target home for the unified code, respecting layer boundaries. Prefer an existing
   module, function, or macro over a new one. Creating a new shared helper is allowed only when no
   suitable home exists, and it must have at least 2 real callers.
6. Establish how behavior preservation will be proven: which existing tests cover the call sites,
   and which new test is needed to pin a difference that would otherwise be lost.
7. Rank by **duplication risk × blast radius**, discounted by migration cost. A rule duplicated
   across components outranks three identical HTML snippets.
8. Keep the 10 best.

## Rules

- Every finding must cite **all** duplicate sites with `path/to/file.py:line`. A finding with one
  site is not a consolidation finding.
- State the differences between the copies explicitly, even when there are none ("byte-identical").
- If the copies diverge, the proposal must say which behavior wins, or that both are preserved
  behind an explicit parameter — never silently pick one.
- Propose the smallest change that removes the duplication. No new layers, no configurability that
  wasn't already implied by the existing copies.
- If consolidating would cross a layer boundary defined in `ARCHITECTURE.md`, say so and either
  justify it or lower the priority.
- Do not propose the change if you cannot name how it is verified.
- If you are unsure two blocks are truly equivalent, mark the finding as uncertain and lower its
  priority rather than asserting it.
- Analysis only — do not edit code in this skill.

## Output Format

Use exactly this text format for each of the 10 items, highest value first. No Markdown tables.

```text
## <short title of the consolidation>

Type: literal duplication | near duplication | parallel implementation | reimplemented helper | redundant layer | template duplication | dead-by-duplication
Sites:
- path/to/file.py:123
- path/to/other.py:45
Layer: component | workflow | route | template | test | cross-layer
Duplication risk: High | Medium | Low
Blast radius: <how many call sites / screens / endpoints are affected>
Estimated effort: Low | Medium | High
Behavior change: none (required) — <one line stating why nothing is lost>

What is duplicated:
<the logical rule or block that appears more than once>

Differences between the copies:
<line-by-line differences, or "byte-identical">

Proposed consolidation:
<the target home and the smallest change that unifies the sites>

How functionality is preserved:
<which behaviors of each copy survive, and where the union is handled>

Verification:
- <existing test or check that must still pass>
- <new test needed to pin a preserved difference, if any>
```

Close the report with two short sections:

```text
## Descartados

<3–6 candidates you considered and rejected, one line each, with the reason —
especially the ones that only look like duplication>

## Riscos

<any consolidation above that could plausibly change behavior, and what to watch>
```

## Persistence

- Write the final report to `docs/0001-consolidation-analysis.md`.
- Overwrite the file if it already exists, unless the user asks for another filename.
- Markdown only, no tables, matching the format above item by item.

**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**
The report is the deliverable and it goes to `docs/0001-consolidation-analysis.md` ONLY.
Reply in the terminal with a single line pointing to the file.
