## Agent-Readable Workspace Map

Read these files according to the task, if necessary:

- `README.md` — local setup, common commands, how to run, basic authentication, and product overview.
- `ARCHITECTURE.md` — structural changes, flow between FastAPI/HTMX/Polylith components, authentication, middleware, and layer boundaries.
- `API.md` — new or changed endpoints, payloads, status codes, HTTP authentication, and integration-facing contracts.
- `DATABASE.md` — database schema, Alembic migrations, SQLAlchemy models, enums, indexes, constraints, and relationships.

## 1. On-Demand Reading

- Grep/graphify first — open only the files the issue names.
- Read the 4 docs above **only** when the change is ambiguous about contract, architecture, auth, or schema. A bug fix with `file:line` does NOT trigger reading them.
- When given `file:line`, read `line-30..line+30` in a single call.
- After a search identifies a target, read only a bounded nearby window. Inspect `git diff --stat` + `git diff --name-only` before a full diff.

## 2. Clarification vs. Silence

- **Ask** only when blocked: missing context that cannot be inferred, conflicting requirements, or ambiguous destructive operations.
- **Otherwise**: state your assumption inline and proceed. Do not ask for trivial clarifications.
- Limit progress updates to 2–4 total per task (start, before a major edit, if blocked, final verification).

## 3. Scope of Changes

- Touch only what the task requires. Do not refactor, reformat, or improve adjacent code.
- Remove imports/variables/functions only if YOUR changes made them unused. Do not remove pre-existing dead code unless asked.
- Every changed line should trace directly to the user's request.

## 4. RTK

RTK is active — every shell command is auto-rewritten for token savings. See `.agents/RTK.md`.

- Write commands using their RTK equivalents directly (e.g., `rtk read`, `rtk git`, `rtk grep`, `rtk find`, `rtk ls`) instead of the standard commands to ensure maximum token efficiency and avoid proxy overhead.
- Do not repeat an identical read, `rg`, status/diff, or validation call within a task unless the working tree or scope changed.
- Before a command likely to fail or produce large output, confirm target path and use the smallest useful invocation.

## 5. Transactions &amp; Rollbacks

When changing transaction boundaries, commits, or rollbacks:

1. Read `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and `components/xtreme_system/database/core.py` (`get_session`).
2. Run `rg "session\.rollback\(\)" --include "*.py"` to find all callers before editing.

Rules:

- Rollback is centralized in `get_session()`.
- If a handler re-raises `IntegrityError` as `HTTPException`, do **not** call `session.rollback()` — `get_session` handles it.
- If a handler catches `IntegrityError` internally and returns a response directly, it **must** call `session.rollback()` before `get_session` attempts its commit.

## 6. Linear Commands

- If the user gives an exact command (e.g. `orca linear issue GUI-XXX --full`), run it exactly. Skip `orca status`/discovery.
- For unspecified Linear reads, default to `--json`; use `--full` only when comments/attachments are needed.

## 7. Graphify

This project has a knowledge graph at `graphify-out/`.

- For codebase questions, first run `graphify query "<question>"` when `graphify-out/graph.json` exists.
- Use `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for focused concepts.
- When a task lacks an exact file target, start with `rg` or `graphify query`, then open only implicated files.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query/path/explain are insufficient.
- Dirty `graphify-out/` files after hooks are expected — not a reason to skip graphify.
- After modifying code, run `graphify update .` to keep the graph current.
- When the user types `/graphify`, use the installed graphify skill before doing anything else.

