## Agent-Readable Workspace Map

Read these files according to the task:

- `README.md` — local setup, common commands, how to run, basic authentication, and product overview.
- `ARCHITECTURE.md` — structural changes, flow between FastAPI/HTMX/Polylith components, authentication, middleware, and layer boundaries.
- `API.md` — new or changed endpoints, payloads, status codes, HTTP authentication, and integration-facing contracts.
- `DATABASE.md` — database schema, Alembic migrations, SQLAlchemy models, enums, indexes, constraints, and relationships.

Shortcuts by intent:

- Changing schema, migrations, models, or enums → read `DATABASE.md`.
- Creating or changing a JSON/HTMX endpoint → read `API.md` and, if it affects internal flow, `ARCHITECTURE.md`.
- Changing authentication, permissions, middleware, or Polylith organization → read `ARCHITECTURE.md`.
- Running, testing, or configuring the environment → read `README.md`.
- Placing validation → business invariants go in `components/*/core.py`; FK existence / availability checks in `workflows.py`; route-specific 400/409 in `bases/api/routes/`. Ex: `FechamentoVendaError` raised in `fechamento_venda/core.py`, caught at the route layer.

Minimal, on-demand reading:

- Grep/graphify first — open only the files the issue names. Don't read docs out of habit.
- Read `README.md` / `ARCHITECTURE.md` / `API.md` / `DATABASE.md` only when the change is ambiguous about contract, architecture, auth, or schema. A bug fix that already carries `file:line` does NOT trigger reading those 4 docs.
- When the issue gives `file:line`, read `line-30..line+30` in a single call — never the whole file in multiple chunks.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Lean Diff by Default

**Inspect diffs cheaply. Read the full diff at most once.**

- After editing, inspect with `git diff --stat` + `git diff --name-only` (via RTK) — don't read the full diff by default.
- Read the full `git diff` at most once, only right before a sensitive commit or when genuinely in doubt.
- When `git status` is clean, skip `diff`/`log` entirely.

## 5. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 6. RTK

RTK is active — every shell command is auto-rewritten for token savings. See .opencode/RTK.md.

## 7. Others

- Changing transaction boundaries, commits, or rollbacks → read `bases/xtreme_system/api/crud_writes.py` (safe_write) and `components/xtreme_system/database/core.py` (get_session). Find all callers of `session.rollback()` with `rg "session\.rollback\(\)" --include "*.py"` before editing. Rollback is centralized in `get_session()`. If a handler re-raises an `IntegrityError` as `HTTPException`, `get_session` will rollback on its own — do not call `session.rollback()` in that path. When a handler catches `IntegrityError` internally and returns a response directly, the handler must call `session.rollback()` to reset the session state before `get_session` attempts its commit.

## 8. Direct Commands & Linear Verbosity

**Run exact commands as given. Keep Linear reads summary-first.**

- If the user gives an exact command (e.g. `orca linear issue GUI-XXX --full`), run exactly that command and skip `orca status`/discovery and loading the whole skill — unless the command mutates Linear.
- For unspecified Linear reads, default to `--json` (summary); use `--full` only when comments/attachments are actually needed.

## 9. Fewer Intermediate Updates

**Speak when it changes a decision. Otherwise, work quietly.**

- Silent-unless-blocked for small/medium tasks.
- Limit progress updates to 2–4 total: start/criteria, before a substantial edit, when blocked, final verification.
- Don't emit an update for read/test/status steps that aren't blocking (e.g. "I'll run the tests", "I'll check the diff").

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
