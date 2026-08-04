## Agent-Readable Workspace Map

Read on demand (not every turn):

- `CONTEXT.md` — domain glossary
- `README.md` — setup / run / auth overview
- `ARCHITECTURE.md` — FastAPI/HTMX/Polylith structure
- `API.md` — HTTP contracts
- `DATABASE.md` — schema / migrations / models
- `docs/agents/transactions-rollbacks.md` — when editing commits/rollbacks
- `docs/agents/graphify.md` — graphify command detail
- `.agents/RTK.md` — RTK command cheatsheet

## Hot rules

1. **Read cheaply** — graphify/`rg` first; open only implicated files. Given `file:line`, read ~±30 lines. Prefer `git diff --stat` / `--name-only` before a full diff. Do **not** load ARCHITECTURE/API/DATABASE for a localized bug fix.

2. **Clarify sparingly** — ask only when blocked (missing context, conflicts, destructive ambiguity). Otherwise state the assumption and proceed. ≤2–4 progress updates per task.

3. **Minimal diffs** — change only what the task requires. No drive-by refactors. Remove unused imports only if your edit made them unused.

4. **RTK** — active; shell commands are auto-rewritten. Prefer RTK forms (`rtk git`, `rtk grep`, …). Details: `.agents/RTK.md`. Do not repeat identical reads/greps/status within a task unless the tree changed.

5. **Transactions** — before changing commit/rollback boundaries, follow `docs/agents/transactions-rollbacks.md`.

6. **Linear** — run exact `orca linear …` commands as given. Unspecified reads: default `--json`; `--full` only when comments/attachments are needed.

7. **Graphify** — for codebase questions, `graphify query` first when `graphify-out/graph.json` exists. More detail: `docs/agents/graphify.md`.
