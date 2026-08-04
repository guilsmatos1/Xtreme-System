---
name: coding--analyze--error-handling
description: Analyze the codebase for error-handling weaknesses — swallowed exceptions, lost context, unsafe rollback/session handling, leaked internals, and missing resilience — prioritized by correctness and operational risk. Use when asked to review error handling, exception handling, failure modes, resilience, logging/observability of errors, or a prioritized list of concrete error-handling issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--error-handling
        source-relative-path: coding/analyze/error-handling
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Error Handling

Analyze this codebase thoroughly and identify the best opportunities to improve how errors are
detected, propagated, reported, and recovered from — without changing correct existing behavior.
Prioritize issues that can silently corrupt data, hide failures from operators, leak internals to
users, or leave resources/sessions dirty over stylistic preferences about try/except shape.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Detection and capture
  - broad `except Exception` (or bare `except:`) swallowing errors that should be specific
  - missing handling at critical boundaries: DB I/O, HTTP calls, file/parsing, auth
  - silent failures: empty `except`, `pass`, `# ignore`, log-and-continue with no corrective action
  - unchecked return/status codes from external calls or subprocesses
  - `raise`/uncaught exceptions where recovery would be appropriate and cheap
2. Propagation and context
  - lost original traceback/cause (`raise Exception("msg")` instead of `raise Exception("msg") from e`)
  - inconsistent wrapping: some layers wrap domain errors, others let raw exceptions leak upward
  - low-level errors (`IntegrityError`, `OperationalError`, driver exceptions) surfaced directly to
    the API/template layer instead of translated to a domain or HTTP error
  - missing contextual data at the raise/log site (request id, user, entity id, operation)
3. Messages and observability
  - generic/empty error messages ("Error", "Something went wrong", "Erro")
  - messages or logs that leak internals (SQL, stack traces, file paths, tokens) to the response body
  - unstructured or missing logging around caught errors
  - wrong log level (everything `error`, or errors logged as `info`/`debug` and lost)
4. Recovery, resilience, and cleanup
  - no retry/backoff on transient network or I/O failures where one would help
  - retrying non-retriable failures (validation, 4xx, auth) as if they were transient
  - no timeout on outbound HTTP/DB calls that can hang
  - resources not released on error paths: open files, DB connections/sessions, locks, transactions
  - **this project's session/rollback contract**: `safe_write` in
    `bases/xtreme_system/api/crud_writes.py` and `get_session` in
    `components/xtreme_system/database/core.py` centralize rollback. Flag both directions of drift —
    a redundant `session.rollback()` in a handler that already re-raises `IntegrityError` as
    `HTTPException` (since `get_session` rolls back on its own), and a handler that catches
    `IntegrityError` internally, returns directly, and skips `session.rollback()`, leaving the
    session dirty before `get_session` tries to commit. Find candidates with
    `rg "session\.rollback\(\)" --include "*.py"` and `rg "except IntegrityError" --include "*.py"`.
5. Design and contracts
  - magic error codes/sentinels instead of typed exceptions or an enum
  - inconsistent mixing of exceptions, return-code checks, and `Optional`/sentinel returns for the
    same kind of failure across the codebase
  - functions that can fail in a meaningful way but don't signal it in their name, docstring, or
    return type
  - domain errors (business-rule violations) handled the same way as infrastructure errors (DB down,
    network timeout) when a caller would want to react differently
  - validation that happens late instead of failing fast at the boundary
6. Python/FastAPI/HTMX idioms in this codebase
  - bare `except:` or `except Exception` used for control flow instead of `except SpecificError`
  - `assert` used for input validation instead of raising a proper exception (asserts are stripped
    with `-O`)
  - route handlers (`bases/xtreme_system/api/routes/*.py`) that let a raw exception 500 instead of
    mapping it to an `HTTPException` with an appropriate status
  - HTMX partial-response error paths that return a broken/empty fragment instead of a visible error
    state for the user
  - missing `from e` when re-raising inside an `except` block
7. Testing and coverage
  - error paths with no test: only the happy path is covered for a function with a `try`/`except`
  - no test asserting the specific message, status code, or rollback behavior on failure
  - mocks in tests that swallow the real exception a unit would raise in production
8. Security and privacy
  - stack traces or internal exception details returned in API responses or rendered templates
  - sensitive data (tokens, passwords, full request bodies) written to logs on error
  - auth/authorization errors that behave differently for "user not found" vs "wrong password" in a
    way that enables user enumeration
9. Consistency and maintainability
  - different error-handling style between routes/components/workflows for the same kind of failure
  - duplicated try/except logic that should be a shared helper instead
  - missing translation layer between infra errors, domain errors, and the API/template response

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - route handlers under `bases/xtreme_system/api/routes/*.py` (HTTP boundary, status-code mapping)
  - `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and
    `components/xtreme_system/database/core.py` (`get_session`) and every caller of
    `session.rollback()`
  - auth/permission code (e.g. `components/xtreme_system/perfil/policy.py`) for enumeration-safe
    error behavior
  - external I/O: HTTP clients, file parsing, background jobs
  - HTMX partial endpoints, for what they render on failure
3. For each candidate, read enough surrounding context (the full `try`/`except` block and its
   caller) to judge whether the current behavior is correct — but read scoped, never whole files.
   Sweep signatures/exception sites first (`rg -n "except |raise |\.rollback\(\)" <files>`), then
   `Read` with `offset`/`limit` only the ranges that sweep points at.
4. Prefer citing the existing centralized rollback/write contract as the target of consolidation
   over inventing a new error-handling abstraction.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet.
6. Avoid broad refactors unless the current handling is clearly causing correctness, reliability, or
   operational risk (data corruption, leaked internals, silent failure).
7. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-error-handling.md`.

## What Strong Findings Look Like

Strong finding:

```text
The vehicle-transfer route catches IntegrityError, returns a 409 directly, but never calls
session.rollback() before returning — the next write on that session commits a half-applied
transaction because get_session only rolls back on an unhandled exception, not on this handled path.
```

Weak finding:

```text
This function could use more specific exception types.
```

Do not report cosmetic findings (e.g. `except Exception` used at a true top-level catch-all boundary
with correct logging and re-raise) unless they materially affect correctness, data integrity,
security, or operability. Do not lower the bar just to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-error-handling.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
