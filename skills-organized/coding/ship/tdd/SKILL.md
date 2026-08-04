---
name: coding--ship--tdd
description: Test-driven development with red-green loop. Use when building test-first, fixing bugs via failing tests, or mentioning red-green-refactor.
metadata:
    skill-organizer:
        original-name: coding--ship--tdd
        source-relative-path: coding/ship/tdd
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Test-Driven Development

TDD is the red → green loop. Consult every section on every cycle.

Read `CONTEXT.md` so test names match domain language. Respect ADRs in the area you touch.

## What a good test is

Tests verify behavior through public interfaces, not internals. A good test reads like a spec and survives refactors.

See [tests.md](tests.md) and [mocking.md](mocking.md).

## Seams

A **seam** is the public boundary you observe without reaching inside. Tests live at seams.

**Test only at pre-agreed seams.** Write the seam list and confirm with the user before any test. Ask: "What's the public interface, and which seams should we test?"

In this repo, prefer seams at brick `core.py` APIs, HTTP routes, or HTMX flows — not private helpers.

## Anti-patterns

- **Implementation-coupled** — mocks internal collaborators, private methods, or DB side-channels; breaks on refactor with unchanged behavior.
- **Tautological** — expected value recomputed the same way as the code; use independent fixtures / worked examples.
- **Horizontal slicing** — all tests then all code. Prefer **vertical slices**: one test → minimal implementation → repeat (**tracer bullets**).

## Rules of the loop

- **Red before green.** Failing test first; only enough code to pass.
- **One slice at a time.** One seam, one test, one minimal implementation.
- **Refactoring is not part of this loop.** Defer structural cleanup to `coding--review--standards-spec` / a dedicated refactor pass.
