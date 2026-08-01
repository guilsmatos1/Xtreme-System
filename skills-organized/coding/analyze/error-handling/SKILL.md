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

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

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

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "exception handling, rollback, and error propagation"`
- a specific dimension: `graphify query "<dimension, e.g. swallowed exceptions, retry logic>"`
- a concept in isolation: `graphify explain "<concept, e.g. safe_write, get_session>"`
- relationship between two areas: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Never re-derive the whole
file tree or definition list by hand when graphify can answer the same question with a fraction of
the tokens.

## Reading Budget

Follow [../references/reading-budget.md](../references/reading-budget.md) — the shared cost
discipline for every `coding--analyze--*` skill (repo path:
`skills-organized/coding/analyze/references/reading-budget.md`).

It applies with full force here: error paths are scattered one or two lines at a time across many
route handlers and workflows, so it's tempting to pull whole files to find them. Sweep
`except`/`raise`/`rollback` sites first, read only the block each hit belongs to, and never re-read a
file already in context.

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

## Output Requirements

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the failure mode
- **Location**: file, line range, function, and a real code snippet (10-15 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "silent failure", "rollback/session",
  "leaked internals", "resilience")
- **Description**: specific explanation tied to the code, including what input/failure triggers it
- **Why it matters**: correctness, data integrity, security, or operational consequence
- **Concrete fix**: smallest useful fix with example (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "prevents
  dirty-session commits on concurrent writes", "stops leaking DB schema in API error bodies") — omit
  rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g. "error-handling", "rollback", "security", "observability")
- **Files affected**: list of all files involved in the fix
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and
  whether this finding is uncertain (see schema below)

## Output Format

Do not format the report yourself. Invoke the `coding--generate--issues-md` skill and hand it the
retained opportunities in final ranked order, the discarded candidates with their reasons, every
analysis-specific field, and the output path below. That skill owns the shared Issues Markdown
contract and is the single definition of the format; it preserves analysis-specific fields under
`Domain details` and validates the finished document.

## Persistence

- The output path is `.loop/running/issues-error-handling.md`. Pass it to
  `coding--generate--issues-md`, which creates the directory when missing, overwrites any existing
  report, sets `Generated` and `Total` from the actual document, and validates it against the
  contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize,
  drop, or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer failure modes that can lose data, hide operational problems, or leak internals over style
  preferences about catch-block shape.
- Name the tradeoff when a fix (e.g. adding retries, adding a translation layer) has real cost.
- If multiple files share the same problem (e.g. the same missing-rollback pattern in three routes),
  cite the best representative examples and list every affected file, instead of repeating yourself.
- If a suspected issue is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`, and
  lower its priority/confidence_score accordingly — never silently upgrade an uncertain hunch to a
  confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-error-handling.md` ONLY.
