---
name: coding--analyze--concurrency
description: Analyze the codebase for concurrency weaknesses — race conditions, non-atomic check-then-act logic, missing locks on shared/mutable state, and non-idempotent writes vulnerable to retries or duplicate requests — prioritized by how likely concurrent access is and how bad the outcome would be. Use when asked to review concurrency, find race conditions, audit locking/idempotency, check for double-submit or duplicate-write bugs, or produce a prioritized list of concrete concurrency issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--concurrency
        source-relative-path: coding/analyze/concurrency
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Concurrency

Analyze this codebase thoroughly and identify the best opportunities to eliminate race conditions and
unsafe concurrent access — without changing correct existing behavior. Prioritize paths where
concurrent requests are realistic (shared counters/balances/stock, double-submitted forms, retried
webhooks, background jobs that can overlap) over theoretical races with no plausible trigger. This is
a distinct lens from `coding--analyze--data-integrity`: that skill asks whether the *schema* enforces
an invariant; this one asks whether the *application logic* can race with itself.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Check-then-act races
  - "check availability, then act" logic (check stock/balance/slot is available, then decrement/book
    it) executed as two separate steps with no lock or atomic operation between them, allowing two
    concurrent requests to both pass the check and overcommit
  - "check existence, then create" logic (look up by unique key, create if absent) with no `UNIQUE`
    constraint or `INSERT ... ON CONFLICT`-style guard, letting a race create duplicates
2. Read-modify-write on shared state
  - a shared counter, balance, or aggregate field read into memory, modified, and written back without
    `SELECT ... FOR UPDATE`, an atomic `UPDATE ... SET x = x + 1`, or optimistic-concurrency
    versioning — two concurrent updates can silently overwrite each other, losing one of them
  - in-memory caches or module-level mutable state shared across requests/threads with no lock,
    where concurrent writers can corrupt or lose updates
3. Idempotency and duplicate submission
  - form/API endpoints that create a record (order, payment, invoice) with no idempotency key or
    unique constraint guarding against a double-submitted request (double-click, client retry, browser
    back-button resubmit) creating two records for one user action
  - webhook handlers (payment/provider callbacks) with no deduplication by the provider's event id,
    so a retried webhook delivery re-applies the same effect twice (e.g. crediting a payment twice)
4. Locking granularity and correctness
  - a lock acquired on the wrong key/scope (e.g. locking per-request instead of per-entity), so it
    doesn't actually prevent the concurrent access it appears to guard against
  - locks held across slow operations (an external HTTP call, a large computation) inside a critical
    section, creating contention or timeout risk under load without actually needing that scope locked
  - lock acquisition order that differs between two code paths touching the same two resources,
    risking deadlock under concurrent execution
5. Background jobs and scheduled tasks
  - a scheduled/cron job with no guard against overlapping runs (previous run still in progress when
    the next one fires), where overlap would cause duplicate processing or contention on the same rows
  - job/queue consumers that fetch-then-process a work item without marking it claimed atomically,
    letting two workers pick up and process the same item
6. Session and transaction boundaries
  - a multi-step business operation split across multiple transactions/commits instead of one, where a
    concurrent request interleaved between those commits can observe or act on a partially-applied
    state
  - long-lived sessions/transactions held open across user think-time (e.g. a multi-step form wizard
    holding one DB transaction across requests), increasing lock contention and the odds of stale-data
    conflicts
7. Testing and regression safety
  - no test simulating concurrent requests against a check-then-act or read-modify-write path (e.g. via
    threads, async tasks, or two overlapping transactions in a test) to prove the race is actually
    closed
  - a previously-fixed race with no regression test, risking silent reintroduction on a future refactor

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - stock/inventory, balance/wallet, seat/slot-booking, and counter-increment logic anywhere in
    `bases/xtreme_system/api/crud_writes.py` and related business modules
  - payment/webhook handlers under `bases/xtreme_system/api/routes/*.py`
  - "get or create" patterns (`rg -n "if not .*: .*create|get_or_create"`) for missing uniqueness
    guards
  - scheduled/background job entry points for overlap guards
  - any explicit locking primitives already in use (`FOR UPDATE`, `threading.Lock`, `asyncio.Lock`,
    Redis-based locks) to see where they're used correctly and where a comparable path lacks one
3. For each candidate, read the full operation (from the check/read to the final write/commit) to
   confirm the race is real and not already closed by a constraint or lock elsewhere — but read
   scoped, never whole files. Sweep signatures and query/lock call sites first
   (`rg -n "FOR UPDATE|\.lock\(|session\.query\(.*\)\.first\(\)"`), then `Read` with `offset`/`limit`
   only the ranges that sweep points at.
4. Prefer citing an existing correct locking/idempotency pattern already used elsewhere in the
   codebase as the target fix over inventing a new concurrency-control mechanism.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet
   showing the non-atomic sequence.
6. Judge impact by realistic concurrency: a path only ever triggered by a single background job with
   no overlap possibility is not the same finding as a user-facing endpoint hit by many concurrent
   requests.

## What Strong Findings Look Like

Strong finding:

```text
reservar_vaga in bases/xtreme_system/api/crud_writes.py:187 reads vaga.disponivel, checks it's True in
Python, then sets it to False and commits — with no SELECT ... FOR UPDATE and no CHECK/UNIQUE guard.
Two concurrent booking requests for the same vaga can both read disponivel=True before either commits,
both proceed, and both succeed, double-booking the same slot.
```

Weak finding:

```text
This code might have a race condition somewhere.
```

Do not report cosmetic findings (e.g. a check-then-act on data that only one process ever touches, or
protected by an outer lock not visible in the snippet but confirmed present) unless a concrete
concurrent trigger is plausible. Do not lower the bar just to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-concurrency.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
