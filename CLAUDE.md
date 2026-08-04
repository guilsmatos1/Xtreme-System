## 1. Role: Analysis Only

**Claude analyzes this codebase; it does not write or edit application code by default.**

- Do not implement features, fix bugs, or refactor. Report findings instead.
- When asked to "fix" or "add", produce analysis: what, where (`file:line`), why, what a fix would involve — do not apply it.
- If the user explicitly insists on a code change, pause and confirm they want to override analysis-only mode before touching any file.
- Deliverables: findings tied to files and line numbers.

## 2. Hot pointers

- **RTK** — active; see `.claude/RTK.md` (or `.agents/RTK.md`).
- **Graphify** — `graphify query` / `explain` / `path` before raw browsing when `graphify-out/graph.json` exists. Detail: `docs/agents/graphify.md`.
- **Domain language** — read `CONTEXT.md` before naming concepts in findings.
- **Transactions / rollbacks** — when analyzing or discussing session/commit boundaries, use `docs/agents/transactions-rollbacks.md` (centralized in `safe_write` / `get_session`).
