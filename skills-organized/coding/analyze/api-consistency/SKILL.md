---
name: coding--analyze--api-consistency
description: Analyze the codebase for API contract inconsistencies — divergent error shapes, status codes, naming, pagination, and versioning across endpoints that do the same kind of thing differently — prioritized by how much they break client expectations. Use when asked to review API consistency, audit endpoint contracts, find inconsistent error/response formats, check naming or status-code conventions across routes, or produce a prioritized list of concrete API-consistency issues tied to specific files and line numbers.
metadata:
    skill-organizer:
        original-name: coding--analyze--api-consistency
        source-relative-path: coding/analyze/api-consistency
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze API Consistency

Analyze this codebase thoroughly and identify the best opportunities to make API contracts
consistent across endpoints — without changing correct existing behavior. Prioritize divergences that
actually break a client's ability to write one piece of code against many endpoints (error shape,
status codes, pagination, field naming) over cosmetic style differences with no client-visible effect.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Error response shape
  - some routes return `{"detail": "..."}` (FastAPI default), others return a custom
    `{"error": {...}}` or ad hoc string, for the same class of failure (validation, not-found, auth)
  - inconsistent status codes for the same logical failure across routes (e.g. one route 404s on a
    missing entity, a sibling route 400s or 500s for the same case)
  - validation errors exposed with FastAPI's raw 422 body on some routes and a hand-rolled shape on
    others
2. Success response shape
  - some list endpoints return a bare array, others wrap it in `{"items": [...], "total": ...}`, with
    no consistent rule for which gets which
  - inconsistent field naming across resources for the same concept (`created_at` vs `data_criacao`
    vs `criado_em`; `id` vs `<entity>_id`)
  - inconsistent casing (`camelCase` vs `snake_case`) mixed within the same API surface
  - some mutation endpoints (`POST`/`PUT`) return the full updated resource, others return only a
    status/id, with no documented rule for which
3. Pagination and filtering
  - some list endpoints paginate (`limit`/`offset` or cursor), others return everything unbounded, for
    resources of comparable and unbounded size
  - inconsistent pagination parameter names or semantics across endpoints (`page`/`per_page` vs
    `skip`/`limit` vs `offset`/`size`)
  - filter/sort query parameters that follow no shared naming convention across similar list endpoints
4. HTTP method and status code usage
  - a `GET` endpoint that mutates state, or a `POST` used where the operation is idempotent and a
    `PUT`/`PATCH` would match REST conventions already used elsewhere in the codebase
  - inconsistent success status codes for the same operation type (`200` vs `201` for creates, `200`
    vs `204` for deletes) across otherwise-parallel routes
5. Versioning and breaking-change hygiene
  - endpoints that changed shape (renamed/removed fields) with no version marker or migration path,
    while sibling endpoints do version or deprecate fields explicitly
  - undocumented behavior differences between routes that look like they should share a contract
    (e.g. two "list vehicles" endpoints reachable from different UI flows with different field sets)
6. HTMX-specific response consistency
  - some HTMX partial endpoints return a rendered fragment on error, others return a raw 500/plain
    error text that breaks the swap, for the same class of user-facing failure
  - inconsistent use of HTMX response headers (`HX-Trigger`, `HX-Redirect`) for equivalent flows (e.g.
    one form success redirects via `HX-Redirect`, a near-identical form just swaps a fragment)
7. Documentation and discoverability
  - route handlers with no Pydantic response model (raw `dict`/`JSONResponse`) next to sibling routes
    that do declare one, making the actual contract undiscoverable from the OpenAPI schema
  - path naming that mixes conventions (`/api/veiculo/{id}` singular vs `/api/clientes` plural) across
    resources with no evident reason

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - route handlers under `bases/xtreme_system/api/routes/*.py`, grouped by resource, to compare
    sibling endpoints for the same CRUD operation across different resources
  - shared response/error helper functions (or their absence) to see which routes use them and which
    don't
  - Pydantic response/request models under the API layer, to spot resources with no declared schema
  - HTMX partial endpoints and their error/redirect behavior
3. For each candidate, compare at least two concrete endpoints side by side (the outlier and a
   representative "normal" example) to prove the inconsistency is real, not a one-off with a good
   reason — but read scoped, never whole files. Sweep route signatures and response types first
   (`rg -n "@router\.(get|post|put|patch|delete)|response_model="`), then `Read` with
   `offset`/`limit` only the ranges that sweep points at.
4. Prefer citing the existing majority pattern in the codebase as the target of consolidation over
   inventing a brand-new convention.
5. Tie every recommendation to specific files, functions, and line ranges for both the outlier and the
   pattern it should match, with real code snippets.
6. Do not flag a difference that has a clear, documented functional reason (e.g. an internal-only
   endpoint intentionally shaped differently from a public one) as an inconsistency.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "API route handlers, response models, and error handling across endpoints"`
- a specific dimension: `graphify query "<dimension, e.g. pagination, error response shape, status codes>"`
- a concept in isolation: `graphify explain "<concept, e.g. a specific route group or response model>"`
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

It applies with full force here: proving an inconsistency requires comparing many route handlers
against each other, so it's tempting to pull whole route files repeatedly. Sweep decorator/signature
lines across all route files first, cluster by resource/operation, and only read the specific
handlers needed to confirm a divergence.

## What Strong Findings Look Like

Strong finding:

```text
list_veiculos and list_clientes both return an unbounded array with no pagination, while
list_movimentacoes (bases/xtreme_system/api/routes/financeiro.py:88) paginates with
{"items": [...], "total": ...}. Frontend code written against one list shape breaks silently against
the other two, and neither veiculos nor clientes bounds the response as the table grows.
```

Weak finding:

```text
Some endpoints use different response shapes than others.
```

Do not report cosmetic findings (e.g. two endpoints that differ only in an internal-only debug field
with no client-visible impact) unless they materially affect how a client integrates against the API.
Do not lower the bar just to reach a round number of findings.

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the inconsistency
- **Location**: file, line range, function, and a real code snippet (8-12 lines) for both the outlier
  and the pattern it should match
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "error shape", "pagination",
  "naming", "status codes", "versioning")
- **Description**: specific explanation tied to the code, including which client-facing expectation
  breaks
- **Why it matters**: integration cost, client-side bugs, or documentation/discoverability
  consequence
- **Concrete fix**: smallest useful fix with example (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "lets
  frontend use one shared error-parsing helper instead of three", "unblocks generic pagination
  component reuse") — omit rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g. "api-consistency", "error-shape", "pagination", "naming")
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

- The output path is `.loop/running/issues-api-consistency.md`. Pass it to
  `coding--generate--issues-md`, which creates the directory when missing, overwrites any existing
  report, sets `Generated` and `Total` from the actual document, and validates it against the
  contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based; always show the outlier next to the pattern it diverges
  from.
- Prefer divergences that break real client integration (error parsing, pagination assumptions) over
  stylistic differences (comment style, internal variable names) with no client-visible effect.
- Name the tradeoff when a fix requires a breaking change (renaming a field, changing a status code)
  and needs a migration/versioning path rather than a silent swap.
- If the same inconsistency appears across many routes, cite the best representative examples and
  list every affected file, instead of repeating yourself.
- If a suspected inconsistency is uncertain (e.g. might have an undocumented functional reason), set
  `self_critique.uncertain: true`, list it in `weaknesses`, and lower its priority/confidence_score
  accordingly — never silently upgrade an uncertain hunch to a confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-api-consistency.md` ONLY.
