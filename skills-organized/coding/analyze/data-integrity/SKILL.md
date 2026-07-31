---
name: coding--analyze--data-integrity
description: Analyze the codebase for data-integrity risks — missing DB constraints, unsafe migrations, orphaned/inconsistent records, and application logic that can leave the database in a contradictory state — prioritized by the risk of silent, hard-to-detect corruption. Use when asked to review data integrity, audit the schema/migrations, find missing constraints or referential-integrity gaps, or produce a prioritized list of concrete data-integrity issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--data-integrity
        source-relative-path: coding/analyze/data-integrity
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Data Integrity

Analyze this codebase thoroughly and identify the best opportunities to protect the database from
silent, hard-to-detect corruption — without changing correct existing behavior. Prioritize gaps where
the database itself (not just application code) can end up in a contradictory state — orphaned rows,
violated business invariants, unsafe migrations — over stylistic schema preferences.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Missing or weak constraints
  - foreign keys defined at the ORM/model level without a matching DB-level `FOREIGN KEY` constraint,
    letting a raw insert or a bug bypass referential integrity
  - columns that should be `NOT NULL` (required business fields) left nullable, relying only on
    application-level validation
  - business invariants enforceable with a `CHECK` constraint or `UNIQUE` index (e.g. non-negative
    stock, unique invoice number per tenant) instead enforced only in Python, where a second code path
    or a direct DB write can violate them
2. Cascade and deletion behavior
  - `ON DELETE`/`ON DELETE CASCADE` behavior that doesn't match what the application logic assumes
    (e.g. code assumes children are cleaned up, but the FK has no cascade and deletion actually fails
    or leaves orphans)
  - soft-delete columns (`deleted_at`, `ativo`) not respected consistently — some queries filter them
    out, others don't, risking "deleted" records reappearing or being double-counted
3. Transactional integrity across multiple writes
  - a business operation that writes to two or more tables/entities without both writes happening in
    the same transaction — if the process crashes between them, the database is left half-updated
  - use of `bases/xtreme_system/api/crud_writes.py` (`safe_write`) — is a multi-step write flow
    bypassing it, doing raw commits per statement instead of one atomic transaction?
  - `session.rollback()` called in a handler that also continues to use the same session for further
    writes in the request without re-verifying its state
4. Migrations
  - a migration that adds a `NOT NULL` column to an existing table with no default and no backfill
    step, which fails against production data with existing rows
  - destructive migrations (dropping a column/table) with no confirmed absence of remaining
    references in application code
  - migrations that assume a specific data shape (e.g. all existing rows satisfy a new `CHECK`
    constraint) with no data audit/backfill before applying it
  - irreversible migrations with no down-migration where one would be feasible
5. Duplicate and orphaned data
  - tables that should have a `UNIQUE` constraint (e.g. one profile per user, one active cart per
    session) but don't, allowing accidental duplicates from a race or a retried request
  - child rows whose parent foreign key can point to a deleted/non-existent parent because the
    relationship isn't enforced at the DB level
6. Concurrency and race conditions on shared data
  - read-then-write patterns on a shared counter/balance/stock field (read value, compute new value,
    write back) with no row-level lock (`SELECT ... FOR UPDATE`) or optimistic concurrency check,
    letting two concurrent requests overwrite each other's update
  - "check-then-act" logic (e.g. check stock available, then decrement) that isn't atomic, allowing
    overselling under concurrent requests
7. Application-level consistency
  - denormalized/duplicated data (a total stored redundantly alongside the line items that sum to it)
    with no mechanism keeping them in sync, risking drift
  - default values applied inconsistently between the DB schema, the ORM model, and form/validation
    layers, so a record can end up with different "empty" representations (`NULL` vs `""` vs `0`)
    depending on which path created it

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - model/schema definitions under `components/xtreme_system/database/` for constraints, nullability,
    and relationship cascade behavior
  - migration files (chronological) for unsafe schema changes against non-empty tables
  - `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and every multi-step write flow that
    touches more than one table/entity
  - business logic around stock, balances, counters, or any "check availability then commit" flow
3. For each candidate, read the model definition, the migration history for that table, and the call
   sites that write to it, to judge whether the current guarantees are actually enforced — but read
   scoped, never whole files. Sweep model/migration definitions first
   (`rg -n "ForeignKey|nullable=|UniqueConstraint|CheckConstraint"`), then `Read` with
   `offset`/`limit` only the ranges that sweep points at.
4. Prefer citing the existing `safe_write`/transaction contract as the target of consolidation over
   inventing a new integrity mechanism.
5. Tie every recommendation to a specific file, function/table, and line range, with a real code
   snippet or schema definition.
6. Distinguish clearly between an application-level validation gap (already covered by
   `coding--analyze--error-handling`) and a true data-integrity gap (the invariant can be violated even
   if the Python code is correct, e.g. via a second writer, a raw script, or a race).

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "database models, constraints, migrations, and multi-table writes"`
- a specific dimension: `graphify query "<dimension, e.g. foreign keys, unique constraints, migrations>"`
- a concept in isolation: `graphify explain "<concept, e.g. safe_write, a specific model>"`
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

It applies with full force here: proving a constraint gap requires cross-referencing a model
definition, its migration history, and every write path that touches it, so it's tempting to pull
whole files at each step. Sweep constraint/FK declarations and write call sites first, read only the
blocks each hit points to, and never re-read a file already in context.

## What Strong Findings Look Like

Strong finding:

```text
Estoque.quantidade is decremented via a read-then-write in reservar_item
(bases/xtreme_system/api/crud_writes.py:212) with no SELECT ... FOR UPDATE and no CHECK constraint
preventing a negative value. Two concurrent reservation requests against the same item can both read
the same quantidade, both decrement it, and leave the column negative — a state the schema itself
should have rejected.
```

Weak finding:

```text
This table could use better constraints.
```

Do not report cosmetic findings (e.g. a missing index that's a performance concern, not an integrity
one — route that to `coding--analyze--performance` instead) unless they materially risk the database
reaching a contradictory or corrupted state. Do not lower the bar just to reach a round number of
findings.

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the integrity gap
- **Location**: file, line range, table/model, and a real code snippet or schema definition (8-12
  lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "missing constraint", "unsafe
  migration", "race condition", "orphaned data", "transactional integrity")
- **Description**: specific explanation tied to the code/schema, including what sequence of events
  produces the corrupted state
- **Why it matters**: correctness, financial, or operational consequence of the corrupted data
- **Concrete fix**: smallest useful fix with example (constraint DDL, lock strategy, or transaction
  boundary change)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "prevents
  negative stock under concurrent reservations", "stops orphaned line items after a parent delete") —
  omit rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk — schema changes on live tables carry
  real migration risk; call it out explicitly)
- **Tags**: searchable labels (e.g. "data-integrity", "constraints", "migration", "race-condition")
- **Files affected**: list of all files involved in the fix (models, migrations, call sites)
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

- The output path is `.loop/running/issues-data-integrity.md`. Pass it to `coding--generate--issues-md`,
  which creates the directory when missing, overwrites any existing report, sets `Generated` and
  `Total` from the actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer gaps where the database itself can reach a contradictory state (via a race, a second writer,
  or a partial failure) over gaps that are already fully guarded by correct, single-path application
  logic.
- Name the tradeoff when a fix requires a migration on a live table (locking, downtime, backfill cost)
  — this is real production risk, not a footnote.
- If multiple tables share the same missing-constraint pattern, cite the best representative examples
  and list every affected file/table, instead of repeating yourself.
- If a suspected issue is uncertain (e.g. whether a race is actually reachable given current traffic
  patterns), set `self_critique.uncertain: true`, list it in `weaknesses`, and lower its
  priority/confidence_score accordingly — never silently upgrade an uncertain hunch to a confident
  finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-data-integrity.md` ONLY.
