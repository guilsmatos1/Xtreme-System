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

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-performance.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
