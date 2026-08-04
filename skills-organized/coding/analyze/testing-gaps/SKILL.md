---
name: coding--analyze--testing-gaps
description: Analyze the codebase for test-coverage weaknesses — untested critical paths, flaky or dangerously-mocked tests, missing negative/edge-case coverage, and untested rollback/authorization behavior — prioritized by the risk of an undetected regression. Use when asked to review test coverage, find testing gaps, audit test quality, check for flaky/mocked tests, or produce a prioritized list of concrete testing issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--testing-gaps
        source-relative-path: coding/analyze/testing-gaps
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Testing Gaps

Analyze this codebase thoroughly and identify the best opportunities to improve test coverage and
test quality — without changing correct existing behavior. Prioritize gaps that let a real regression
reach production undetected (money, data integrity, auth, rollback) over stylistic test-style
preferences.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Untested critical paths
  - business-rule functions (pricing, totals, stock/inventory adjustments, tax/fee calculation) with
    no test at all
  - write paths through `bases/xtreme_system/api/crud_writes.py` (`safe_write`) with no test exercising
    a constraint violation or rollback
  - route handlers under `bases/xtreme_system/api/routes/*.py` with only a happy-path test, or no test
2. Missing negative and edge-case coverage
  - only the success case is tested for a function with a `try`/`except`, an `if`/`else` branch, or a
    validation check — the failure/rejection branch is never exercised
  - boundary values untested (zero, negative, empty, max-length, duplicate) where the code has
    explicit logic for them
  - authorization tests that only assert the allowed case, never that a non-owner/lower-role request
    is rejected (cross-check against `components/xtreme_system/perfil/policy.py`)
3. Dangerous or misleading mocks
  - mocks that swallow the real exception a unit would raise in production, making a broken code path
    look green
  - database/session mocked in a test that exists specifically to verify persistence or rollback
    behavior — the mock proves the code was *called*, not that the write/rollback was correct
  - over-mocked integration tests where every collaborator is stubbed, so the test only verifies that
    functions call each other, not that the result is correct
4. Flaky and order-dependent tests
  - tests relying on real wall-clock time, unseeded randomness, or external network calls without a
    fixture/fake
  - tests that pass/fail depending on execution order due to shared mutable state (module-level
    globals, un-rolled-back DB fixtures)
  - tests with sleeps/retries papering over a real race condition instead of asserting on a
    deterministic condition
5. Fixture and setup correctness
  - test fixtures that don't reset session/DB state between tests, letting one test's leftover data
    pass another test that should have failed
  - fixtures duplicated ad hoc per test file instead of a shared factory, causing subtle drift between
    what's "typical" test data in different suites
6. Assertion quality
  - tests that only assert `status_code == 200` or "no exception raised" without checking the actual
    response body/state changed correctly
  - snapshot/golden-file tests with no reviewer ever having verified the snapshot is actually correct
  - tests asserting on implementation details (call counts, internal method names) instead of
    observable behavior, making them brittle to safe refactors
7. Coverage of this project's centralized contracts
  - `safe_write`/`get_session` rollback contract: is there a test that deliberately triggers an
    `IntegrityError` and asserts the session was left clean afterward? Find candidates with
    `rg "except IntegrityError" --include "*.py"` and check whether each has a corresponding test
  - shared policy/permission helpers with no test matrix covering each role × each action
8. Test suite health
  - tests skipped/xfail with no tracked reason or expiry
  - test files that no longer import cleanly, or whose imports reference removed/renamed code (a sign
    the suite silently stopped running)

## Process

1. Explore the project structure before diving into specific files, mapping source modules to their
   corresponding test files (or the absence of one).
2. Identify likely hotspots:
  - route handlers under `bases/xtreme_system/api/routes/*.py` and their test coverage
  - `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and every caller, checking for rollback
    tests
  - `components/xtreme_system/perfil/policy.py` and its authorization test matrix
  - business-rule modules (pricing, stock, financial calculations) and their test files
  - test fixtures/conftest files for state leakage and mock scope
3. For each candidate, read the source function and its test file (or confirm none exists) to judge
   whether current coverage is adequate — but read scoped, never whole files. Sweep test files first
   (`rg -n "def test_|@pytest.mark" <files>`), then `Read` with `offset`/`limit` only the ranges that
   sweep points at.
4. Prefer citing the existing test structure/conventions as the target of extension over inventing a
   new testing framework or pattern.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet
   showing the gap (the untested branch, or the mock that hides the risk).
6. Do not flag a missing test for trivial code (pure getters, `__repr__`, framework boilerplate) —
   focus on logic with real failure consequences.

## What Strong Findings Look Like

Strong finding:

```text
create_venda in bases/xtreme_system/api/crud_writes.py has three tests, all happy-path. None of them
trigger an IntegrityError (e.g. duplicate invoice number) to verify safe_write's rollback actually
leaves the session clean — a regression that broke rollback here would pass the full suite today.
```

Weak finding:

```text
This module could use more tests.
```

Do not report cosmetic findings (e.g. a trivial helper with no branching logic that lacks a unit
test) unless they materially affect the risk of an undetected regression. Do not lower the bar just
to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-testing-gaps.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
