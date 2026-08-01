---
name: coding--analyze--performance
description: Analyze the codebase for performance weaknesses — N+1 queries, missing indexes, blocking I/O on hot paths, unbounded payloads/loops, and inefficient data access patterns — prioritized by real-world latency and resource impact. Use when asked to review performance, find slow queries, audit database access patterns, check for N+1 issues, or produce a prioritized list of concrete performance issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--performance
        source-relative-path: coding/analyze/performance
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Performance

Analyze this codebase thoroughly and identify the best opportunities to improve latency, throughput,
and resource usage — without changing correct existing behavior. Prioritize issues that scale with
data volume or concurrent load (N+1 queries, missing indexes, unbounded result sets) over micro-
optimizations that don't move real-world response times.

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Database access patterns
  - N+1 queries: a loop over a collection that issues one query per item instead of a single
    joined/batched query (look for query calls inside `for` loops or list comprehensions)
  - missing `join`/`selectinload`/`joinedload` (or equivalent) where a relationship is accessed
    per-row after a list query
  - queries with no `LIMIT`/pagination fetching potentially unbounded result sets
  - repeated identical queries within the same request (no request-scoped caching/memoization)
2. Missing or ineffective indexes
  - columns used in `WHERE`, `JOIN`, or `ORDER BY` in hot-path queries with no corresponding index in
    the model/migration
  - indexes that exist but don't match the actual query pattern (wrong column order in a composite
    index, index on a column that's always filtered together with another that isn't included)
3. Blocking operations on hot paths
  - synchronous file I/O, external HTTP calls, or CPU-heavy work (parsing, image processing) inside a
    request handler with no offload to a background job/queue
  - missing or too-generous timeouts on outbound calls that can stall a request thread
4. Unbounded loops and payloads
  - endpoints that serialize an entire table/collection with no pagination, filtering, or field
    projection
  - recursive or nested-loop logic whose cost grows faster than linearly with realistic input sizes
  - large objects (files, images, full request bodies) loaded fully into memory instead of streamed
5. Caching and memoization
  - expensive, purely-derived computations (aggregations, formatted reports) recomputed on every
    request with no cache layer, when the underlying data changes infrequently
  - cache invalidation that's missing or incorrect, risking stale reads (note as correctness risk,
    not just performance)
6. Concurrency and resource usage
  - connection/session objects created per call instead of reused/pooled where the framework expects
    pooling
  - locks held across I/O (e.g. a DB transaction held open while making an external HTTP call)
  - background jobs or long-running tasks run synchronously in the request path instead of queued
7. Frontend/HTMX-specific costs
  - HTMX partial endpoints that re-render or re-query far more data than the swapped fragment needs
  - polling endpoints hit on a short interval that could be event-driven or debounced
8. Testing and observability of performance
  - no test or assertion guarding against reintroducing an N+1 (e.g. a query-count assertion) on a
    path that was previously fixed
  - no timing/metrics instrumentation around known-expensive operations, making regressions invisible
    until a user complains

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - route handlers under `bases/xtreme_system/api/routes/*.py` that list/serialize collections
  - ORM model definitions and relationships in `components/xtreme_system/database/` for missing
    indexes and lazy-loading defaults
  - `bases/xtreme_system/api/crud_writes.py` and any bulk-write or bulk-read helpers
  - loops that call a query or external function per iteration (`rg -n "for .* in .*:\n.*\.query\(|\.get\(|\.filter\("` style sweeps)
  - report/dashboard/aggregation endpoints, which tend to concentrate expensive queries
3. For each candidate, read enough surrounding context (the full query/loop and the model it touches)
   to judge realistic data volume and call frequency — but read scoped, never whole files. Sweep
   query/loop sites first (`rg -n "\.query\(|\.filter\(|for .* in "`), then `Read` with
   `offset`/`limit` only the ranges that sweep points at.
4. Prefer citing the existing ORM/session patterns already used elsewhere in the codebase as the
   target fix (e.g. an existing `joinedload` used correctly in one route but missing in a sibling
   route) over inventing a new caching or query abstraction.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet.
6. Judge impact by realistic scale: a loop over a table that will stay small (a handful of config
   rows) is not the same finding as a loop over customer/transaction records that grows with the
   business.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "database query patterns, loops over collections, and model relationships"`
- a specific dimension: `graphify query "<dimension, e.g. N+1 queries, missing indexes, caching>"`
- a concept in isolation: `graphify explain "<concept, e.g. a specific model or route>"`
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

It applies with full force here: N+1s and missing-index candidates are found by matching a query call
against a loop or a model definition elsewhere, so it's tempting to pull whole files to trace the
relationship. Sweep query/loop sites and model definitions first, read only the blocks each hit points
to, and never re-read a file already in context.

## What Strong Findings Look Like

Strong finding:

```text
list_vendas_by_cliente in bases/xtreme_system/api/routes/vendas.py loops over every venda returned by
the initial query and accesses venda.cliente.nome, issuing one additional SELECT per venda (N+1).
With a client history page showing 200+ vendas, this is 200+ extra round trips per request; a single
joinedload(Venda.cliente) on the initial query would collapse this to one query.
```

Weak finding:

```text
This function could probably be made faster.
```

Do not report cosmetic findings (e.g. a loop over a config table with at most 5 rows, or a
micro-optimization with no measurable effect at realistic scale) unless they materially affect
latency or resource usage under real load. Do not lower the bar just to reach a round number of
findings.

## Output Requirements

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the performance issue
- **Location**: file, line range, function, and a real code snippet (10-15 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "N+1 query", "missing index",
  "blocking I/O", "unbounded payload", "caching")
- **Description**: specific explanation tied to the code, including what data volume/traffic pattern
  triggers the cost
- **Why it matters**: latency, throughput, resource cost, or scalability consequence
- **Concrete fix**: smallest useful fix with example (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "collapses
  200 queries into 1 on the client history page", "removes a full-table scan on a 500k-row table") —
  omit rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g. "performance", "n+1", "indexing", "caching", "blocking-io")
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

- The output path is `.loop/running/issues-performance.md`. Pass it to `coding--generate--issues-md`,
  which creates the directory when missing, overwrites any existing report, sets `Generated` and
  `Total` from the actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer failure modes that scale with data volume or concurrent load over micro-optimizations with
  no measurable real-world effect.
- Name the tradeoff when a fix (e.g. adding a cache, adding an index) has real cost (staleness risk,
  write-path overhead, migration risk).
- If multiple routes share the same problem (e.g. the same missing `joinedload` pattern in three
  list endpoints), cite the best representative examples and list every affected file, instead of
  repeating yourself.
- If a suspected issue is uncertain (e.g. actual data volume in production is unknown), set
  `self_critique.uncertain: true`, list it in `weaknesses`, and lower its priority/confidence_score
  accordingly — never silently upgrade an uncertain hunch to a confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-performance.md` ONLY.
