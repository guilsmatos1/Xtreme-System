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

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-api-consistency.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
