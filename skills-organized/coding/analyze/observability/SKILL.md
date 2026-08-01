---
name: coding--analyze--observability
description: Analyze the codebase for observability gaps — missing or unstructured logging, absent metrics/tracing on critical paths, and errors that fail silently with no operational signal — prioritized by how much operational blindness they create. Use when asked to review logging, observability, monitoring, tracing, or metrics coverage, or produce a prioritized list of concrete observability issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--observability
        source-relative-path: coding/analyze/observability
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Observability

Analyze this codebase thoroughly and identify the best opportunities to improve operational
visibility — logging, metrics, and tracing — without changing correct existing behavior. Prioritize
gaps that would leave an operator blind to a real production failure (silent errors, unmonitored
critical paths, unstructured logs that can't be searched/alerted on) over stylistic logging
preferences. This is a distinct lens from `coding--analyze--error-handling`: that skill asks whether an
error is *handled* correctly; this one asks whether an operator would *know* it happened.

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Silent failures with no operational signal
  - `except` blocks that catch and discard an error with no `log`/`logger` call at all — the failure
    leaves no trace anywhere an operator could find it
  - background jobs/scheduled tasks that can fail with no alerting path — a stuck or crashed job looks
    identical to a job that never needed to run
  - retried operations where only the final failure is logged, hiding how many attempts silently
    failed first
2. Logging coverage on critical paths
  - business-critical operations (payment/financial writes, stock adjustments, auth events) with no
    log statement marking success or failure
  - `bases/xtreme_system/api/crud_writes.py` (`safe_write`) callers and `session.rollback()` call
    sites — is the rollback itself logged with enough context to diagnose what triggered it?
  - route handlers under `bases/xtreme_system/api/routes/*.py` that return a 5xx with no
    corresponding log entry capturing the exception and request context
3. Log quality and structure
  - logs missing correlation context (request id, user id, entity id) needed to trace one failure
    across multiple log lines/services
  - unstructured string-interpolated log messages where a structured/keyed format would let the same
    failure be queried and alerted on reliably
  - inconsistent log levels for comparable severity (the same class of failure logged as `error` in
    one place and `info`/`debug` in another, so alerting rules miss half of it)
  - log messages that don't state what went wrong or what the system did next (e.g. just "Error" or
    "Falha" with no cause)
4. Sensitive data in logs
  - tokens, passwords, full request/response bodies, or PII written to logs at any level — this is
    both an observability-quality and a security concern; flag it here if the primary lens is "we log
    too much/the wrong thing," and defer exploitation framing to `coding--analyze--security`
5. Metrics and tracing
  - no counter/timer around operations known to be expensive or failure-prone (external HTTP calls,
    DB writes with retries), making a regression invisible until a user complains
  - no health-check/readiness signal for a service or background worker that can silently stop
    processing work
  - tracing spans missing around a multi-step business transaction that crosses several
    functions/modules, making it hard to reconstruct what happened during an incident
6. Alerting readiness
  - error conditions that are logged but structured in a way that makes it impractical to build an
    alert on them (no stable error code/category field, message text that varies per instance so it
    can't be grouped)
  - critical thresholds (queue backlog, failed job count, stock reaching zero) with no logged/metriced
    signal that could feed an alert, even though the underlying data is already computed somewhere in
    the code
7. Test and regression safety for observability
  - a previously-fixed silent-failure bug with no test asserting that the fix still logs/raises today
    (regression could silently reintroduce the blind spot)

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - `except` blocks across the codebase, cross-referenced against whether they log
    (`rg -n "except " --include "*.py" -A3` style sweep for blocks with no `log`/`logger` call)
  - route handlers under `bases/xtreme_system/api/routes/*.py` and their 4xx/5xx paths
  - `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and every `session.rollback()` site for
    logging context
  - background/scheduled job entry points
  - existing logging configuration/setup to understand what structure and levels are already
    available but underused
3. For each candidate, read the surrounding function to confirm there truly is no log/metric on that
   path (not just a different log call slightly earlier/later in the flow) — but read scoped, never
   whole files. Sweep `except`/`log`/`logger` sites first, then `Read` with `offset`/`limit` only the
   ranges that sweep points at.
4. Prefer citing the existing logging setup/conventions already used elsewhere in the codebase as the
   target pattern to extend, over inventing a new logging framework or format.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet.
6. Do not flag verbose debug-level logging that's already present but simply not emphasized — focus on
   genuine blind spots where nothing is logged/metriced at all on a path that matters operationally.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "logging, error handling, and background job execution"`
- a specific dimension: `graphify query "<dimension, e.g. silent failures, structured logging, metrics>"`
- a concept in isolation: `graphify explain "<concept, e.g. safe_write, logging setup>"`
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

It applies with full force here: confirming a silent failure requires checking that no log call
exists anywhere in a function, which tempts a full-file read. Sweep `except`/`log`/`logger` keywords
first across candidate files, and only read the specific function block once a sweep hit suggests a
gap.

## What Strong Findings Look Like

Strong finding:

```text
process_pagamento_webhook in bases/xtreme_system/api/routes/pagamentos.py:140 catches
`requests.RequestException` around the confirmation call to the payment provider, sets status to
"pending", and returns 200 with no log call at all. A failed confirmation call today looks identical
in the logs to one that never happened — an operator investigating a stuck payment has no trace to
start from.
```

Weak finding:

```text
This function could log more.
```

Do not report cosmetic findings (e.g. missing debug-level logging in a rarely-hit, low-consequence
code path) unless they materially affect an operator's ability to detect or diagnose a real production
issue. Do not lower the bar just to reach a round number of findings.

## Output Requirements

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the observability gap
- **Location**: file, line range, function, and a real code snippet (10-15 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "silent failure", "missing critical-
  path logging", "unstructured logs", "missing metrics/tracing", "alerting readiness")
- **Description**: specific explanation tied to the code, including what failure would go undetected
  and for how long
- **Why it matters**: mean-time-to-detect/diagnose consequence, or the business cost of a blind spot
  (e.g. a stuck payment, a silently-failed background job)
- **Concrete fix**: smallest useful fix with example (log call with what context to include, or a
  metric/counter to add)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "cuts
  diagnosis time for stuck payments from hours of manual DB inspection to one log query") — omit
  rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g. "observability", "logging", "silent-failure", "metrics", "tracing")
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

- The output path is `.loop/running/issues-observability.md`. Pass it to `coding--generate--issues-md`,
  which creates the directory when missing, overwrites any existing report, sets `Generated` and
  `Total` from the actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer blind spots on genuinely critical paths (money, auth, data writes, background jobs) over
  missing debug logging with no operational consequence.
- Name the tradeoff when a fix has real cost (log volume/cost increase, added latency from
  synchronous logging of large payloads).
- If the same gap appears across many handlers (e.g. no rollback logging across three write paths),
  cite the best representative examples and list every affected file, instead of repeating yourself.
- If a suspected gap is uncertain (e.g. logging might exist upstream via middleware not reviewed), set
  `self_critique.uncertain: true`, list it in `weaknesses`, and lower its priority/confidence_score
  accordingly — never silently upgrade an uncertain hunch to a confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.
- Flag logged sensitive data (tokens, passwords, PII) plainly, but do not reproduce the sensitive value
  itself in the report — describe it and redact.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-observability.md` ONLY.
