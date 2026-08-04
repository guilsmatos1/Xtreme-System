---
name: coding--analyze--security
description: Analyze security weaknesses (injection, authz, secrets, unsafe input). Use when asked for a security review, vulnerability audit, or auth/permissions check.
metadata:
    skill-organizer:
        original-name: coding--analyze--security
        source-relative-path: coding/analyze/security
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Security

Analyze this codebase thoroughly and identify the best opportunities to reduce real security risk —
without changing correct existing behavior. Prioritize issues that let an attacker read/write data
they shouldn't, escalate privileges, exfiltrate secrets, or crash the system, over stylistic or
theoretical hardening. This is defensive analysis only: identify and explain, never craft or stage
an actual exploit payload.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Injection
  - string-built SQL/HTML/shell/template fragments using request-derived data instead of
    parameterized queries, ORM constructs, or auto-escaping templates
  - `subprocess`/`os.system`/`eval`/`exec` calls fed any value derived from user input
  - unsafe deserialization (`pickle`, `yaml.load` without `SafeLoader`, `eval`-based parsing) of
    externally supplied data
2. Authentication and session handling
  - password/token comparison not constant-time, or hashing that isn't a modern KDF (bcrypt/argon2/
    scrypt) for stored credentials
  - session tokens/cookies missing `HttpOnly`, `Secure`, or a sane `SameSite`
  - login/reset flows that reveal whether an account exists (user enumeration) via differing errors,
    status codes, or timing
  - missing rate limiting or lockout on auth endpoints
3. Authorization
  - route handlers under `bases/xtreme_system/api/routes/*.py` that fetch/mutate an entity by ID
    without checking the requester owns or is scoped to it (IDOR) — cross-check against
    `components/xtreme_system/perfil/policy.py` for the intended scoping rule
  - authorization checks performed client-side (hidden buttons/HTMX swaps) with no server-side
    enforcement of the same rule
  - privilege checks that use a role/flag inconsistently across similar endpoints
4. Secrets and sensitive data
  - hardcoded API keys, passwords, tokens, or connection strings in source, config, or test fixtures
  - secrets logged, included in error responses, or embedded in URLs (query strings) instead of
    headers/body
  - sensitive fields (documents, financial data, credentials) returned in API payloads beyond what
    the consuming UI needs
5. Input validation and boundaries
  - request bodies/query params trusted without schema validation (missing/loose Pydantic models,
    unchecked type coercion) before reaching business logic or the DB layer
  - file upload endpoints missing type/size/path checks (path traversal via filename)
  - missing validation on redirect targets (open redirect) or on URLs fetched server-side (SSRF)
6. Transport and configuration
  - `DEBUG`/verbose error pages reachable in a way that could leak stack traces or internals in
    production paths
  - CORS configured with a wildcard origin alongside credentialed requests
  - missing CSRF protection on state-changing HTMX/form endpoints that rely on cookies for auth
  - dependencies with known CVEs pinned in `requirements`/lockfiles (flag by name/version; do not
    attempt to exploit)
7. Data exposure
  - internal exceptions, SQL, or file paths surfaced in API responses or rendered templates
  - overly broad `SELECT *`/serializer output exposing fields (password hashes, internal IDs, other
    tenants' data) never consumed by the frontend
8. Testing and coverage
  - authorization rules with no test asserting the negative case (that a non-owner/lower-role request
    is rejected)
  - no test covering the exact injection-prone code path after a fix

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - route handlers under `bases/xtreme_system/api/routes/*.py` (HTTP boundary, auth/authorization)
  - `components/xtreme_system/perfil/policy.py` and any permission/role-check helpers
  - raw SQL, `subprocess`, `eval`/`exec`, and file-upload/download code paths
  - auth/session/login/password-reset flows and cookie/token configuration
  - config/settings modules and `.env`/fixture files for hardcoded secrets
3. For each candidate, read enough surrounding context (the full handler, the data it reads/writes,
   and the policy it should be enforcing) to judge exploitability — but read scoped, never whole
   files. Sweep first (`rg -n "execute\(|subprocess|eval\(|session\[|request\." <files>`), then `Read`
   with `offset`/`limit` only the ranges that sweep points at.
4. Prefer citing the existing auth/policy contract as the target of consolidation over inventing a
   new security abstraction.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet.
6. Do not attempt to run, craft, or output a working exploit/payload — describe the vulnerability and
   the fix, not a proof-of-concept attack string.

## What Strong Findings Look Like

Strong finding:

```text
GET /api/vehicles/{id}/documents fetches the document by id and streams it back without checking
that request.user.empresa_id matches the vehicle's owning empresa — any authenticated user can read
any other tenant's documents by incrementing the id (IDOR).
```

Weak finding:

```text
This endpoint could use more validation.
```

Do not report cosmetic findings (e.g. a debug-only code path that is never reachable in production,
or a theoretical issue with no realistic trigger) unless they materially affect confidentiality,
integrity, or availability. Do not lower the bar just to reach a round number of findings.

## Domain notes

- Defensive analysis only: never craft or stage an exploit payload.
- Never output a working exploit payload, credential, or token found in the codebase verbatim — describe it and redact the sensitive value.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-security.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
