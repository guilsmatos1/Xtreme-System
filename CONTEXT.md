# Xtreme System — Domain Language

Shared vocabulary for agents. Prefer these terms in code, tickets, specs, and chat.
Create or update ADRs under `docs/adr/` for load-bearing decisions; do not re-litigate them here.

## Language

**Polylith brick**:
A deployable unit under `bases/` or `components/` in namespace `xtreme_system`. Public API lives in that brick's `core.py`.
_Avoid_: package, microservice (unless comparing), module (use **brick** for Polylith units; use **module** only for a Python module file)

**Base**:
The FastAPI application brick at `bases/xtreme_system/api/` — routes, templates, statics, app wiring.
_Avoid_: backend root, API package

**Component**:
A domain brick under `components/xtreme_system/<name>/` (e.g. `veiculo`, `venda`, `cliente`). Owns its models, schemas, and CRUD; other bricks import via `from xtreme_system.<name> import core as <name>`.
_Avoid_: service, bounded context (unless discussing DDD mapping)

**Empresa**:
The tenant / dealership scope most records belong to. Authorization usually checks the requester is scoped to the same `empresa`.
_Avoid_: company, tenant (say **Empresa** in domain talk; "tenant" only when explaining multi-tenancy)

**Veículo**:
A vehicle inventory unit — status transitions gate sales and consignments.
_Avoid_: car, auto (except UI copy)

**Venda**:
A vehicle sale workflow, including fechamento and related documents/comprovantes.
_Avoid_: order (unless mapping to e-commerce analogies)

**Cliente**:
A customer (buyer/seller party) with documents and images.
_Avoid_: user (a **Usuario** is a login identity; a **Cliente** is a business party)

**Usuario**:
A login identity with perfil/roles. Distinct from **Cliente**.
_Avoid_: account (ambiguous — say **Usuario** or **Cliente**)

**Perfil / policy**:
Authorization rules — see `components/xtreme_system/perfil/policy.py`. Server-side enforcement is required; HTMX visibility is not authz.
_Avoid_: permissions helper (prefer **policy**)

**HTMX UI**:
Cookie-authenticated browser UI under `/ui/...`, Jinja templates, partial swaps. Distinct from the JSON API (Bearer JWT).
_Avoid_: frontend SPA, React app

**safe_write / get_session**:
Central write and session/rollback helpers (`bases/.../crud_writes.py`, `components/.../database/core.py`). Rollback is centralized in `get_session` unless a handler swallows `IntegrityError` and returns without re-raising.
_Avoid_: manual session.commit sprinkled in routes without the shared helpers

**Issue**:
A Linear work item (GUI-*). Analysis skills write Markdown opportunities; `devops--linear--send` turns them into Issues.
_Avoid_: ticket (except when quoting Linear UI), task (unless a worker step)

**Worktree**:
An Orca-managed git worktree for an Issue implementation run.
_Avoid_: branch folder, sandbox (say **worktree**)

**Skill**:
An agent skill under `skills-organized/`, synced to `.agents/skills` and `.claude/skills` via skill-organizer.
_Avoid_: prompt file, slash command (those are invocation styles)

## Relationships

- A **Base** mounts many **Component** bricks.
- An **Empresa** scopes **Veículo**, **Venda**, **Cliente**, and most documents.
- A **Usuario** acts under a **Perfil/policy**; a **Cliente** is data, not a login.
- An **Issue** may be implemented in a **Worktree** by a dispatched **Skill**.

## Flagged ambiguities

- "account" — resolve to **Usuario** (login) or **Cliente** (party), never leave bare.
- "order" — resolve to **Venda** (or compra/consignação) in this domain.
- "module" — prefer **brick** for Polylith units; "module" for a single `.py` file only.
