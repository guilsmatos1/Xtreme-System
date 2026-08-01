---
name: coding--analyze--security
description: Analyze the codebase for security weaknesses — injection, broken auth/authorization, exposed secrets, unsafe deserialization, missing input validation, and other OWASP-class risks — prioritized by exploitability and blast radius. Use when asked to review security, find vulnerabilities, audit auth/permissions, check for injection or exposed secrets, or produce a prioritized list of concrete security issues tied to specific files and line numbers.
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

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

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

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "authentication, authorization, and input handling"`
- a specific dimension: `graphify query "<dimension, e.g. SQL construction, secrets, CORS>"`
- a concept in isolation: `graphify explain "<concept, e.g. policy.py, session cookie config>"`
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

It applies with full force here: authorization checks are scattered one call at a time across many
route handlers, so it's tempting to pull whole files to find them. Sweep call sites first, read only
the block each hit belongs to, and never re-read a file already in context.

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

## Output Requirements

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the vulnerability class
- **Location**: file, line range, function, and a real code snippet (10-15 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (e.g. "injection", "authorization/IDOR",
  "secrets exposure", "input validation")
- **Description**: specific explanation tied to the code, including what request/actor triggers it
- **Why it matters**: confidentiality, integrity, availability, or compliance consequence
- **Concrete fix**: smallest useful fix with example (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g. "closes
  cross-tenant document read", "removes hardcoded credential from source history") — omit rather than
  guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g. "security", "injection", "auth", "secrets", "idor")
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

- The output path is `.loop/running/issues-security.md`. Pass it to `coding--generate--issues-md`,
  which creates the directory when missing, overwrites any existing report, sets `Generated` and
  `Total` from the actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer failure modes that let an attacker read/write unauthorized data, escalate privilege, or
  exfiltrate secrets over theoretical or defense-in-depth-only suggestions.
- Name the tradeoff when a fix (e.g. adding rate limiting, rotating a secret) has real cost or
  requires coordination (key rotation, session invalidation).
- If multiple endpoints share the same problem (e.g. the same missing ownership check across three
  routes), cite the best representative examples and list every affected file, instead of repeating
  yourself.
- If a suspected issue is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`, and
  lower its priority/confidence_score accordingly — never silently upgrade an uncertain hunch to a
  confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of
  confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.
- Never output a working exploit payload, credential, or token found in the codebase verbatim in the
  report — describe it and redact the sensitive value.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-security.md` ONLY.
