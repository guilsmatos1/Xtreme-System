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

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

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

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "stock, balance, booking, and check-then-act write patterns"`
- a specific dimension: `graphify query "<dimension, e.g. idempotency, locking, background job overlap>"`
- a concept in isolation: `graphify explain "<concept, e.g. a specific booking/stock function>"`
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

It applies with full force here: proving a race requires reading the full check-to-write sequence,
which can span helper calls, so it's tempting to pull whole files to trace it. Sweep query/lock sites
first, read only the specific function chain each hit belongs to, and never re-read a file already in
context.

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

## Output Requirements

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the race/concurrency issue
- **Location**: file, line range, function, and a real code snippet (10-15 lines) showing the
  non-atomic sequence
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "check-then-act race", "read-modify-
  write", "idempotency", "locking granularity", "job overlap")
- **Description**: specific explanation tied to the code, including the concrete interleaving of two
  concurrent requests/jobs that produces the bad outcome
- **Why it matters**: correctness, financial, or operational consequence (overselling, double-
  crediting, lost updates, deadlock)
- **Concrete fix**: smallest useful fix with example (row lock, atomic update, unique constraint,
  idempotency key)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "prevents
  double-booking under concurrent requests", "stops duplicate payment crediting on webhook retry") —
  omit rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk — locking changes can introduce
  contention or deadlock if done carelessly; call this out explicitly)
- **Tags**: searchable labels (e.g. "concurrency", "race-condition", "idempotency", "locking")
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

- The output path is `.loop/running/issues-concurrency.md`. Pass it to `coding--generate--issues-md`,
  which creates the directory when missing, overwrites any existing report, sets `Generated` and
  `Total` from the actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based; always show the concrete interleaving of two concurrent
  actors that produces the bad outcome, not just "this could race in theory."
- Prefer paths with realistic concurrent traffic (user-facing booking/payment/stock endpoints, retried
  webhooks, overlapping scheduled jobs) over paths that are functionally single-writer today.
- Name the tradeoff when a fix adds locking/contention cost (e.g. a row lock that serializes writes on
  a hot table) versus the corruption risk it prevents.
- If the same race pattern appears across multiple resources (e.g. the same check-then-act shape for
  stock and for seat booking), cite the best representative examples and list every affected file,
  instead of repeating yourself.
- If a suspected race is uncertain (e.g. whether the endpoint is ever called concurrently in practice),
  set `self_critique.uncertain: true`, list it in `weaknesses`, and lower its priority/confidence_score
  accordingly — never silently upgrade an uncertain hunch to a confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-concurrency.md` ONLY.
