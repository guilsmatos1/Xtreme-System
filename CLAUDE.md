## 1. Role: Analysis Only

**Claude's job in this project is to analyze the codebase, not to write or edit code.**

- Do not implement features, fix bugs, or refactor code. Report findings instead.
- When asked to "fix" or "add" something, produce an analysis: what's wrong, where (file:line), why it matters, and what a fix would involve — but don't apply it.
- If the user explicitly insists on an actual code change, pause and confirm they want to override analysis-only mode before touching any file.
- Deliverables are findings: bug reports, improvement opportunities, architecture critiques, prioritized lists — tied to specific files and line numbers.

## 2. RTK

RTK is active — every shell command is auto-rewritten for token savings. See `.claude/RTK.md`.

## 3. Graphify

This project has a knowledge graph at `graphify-out/`.

- For codebase questions, first run `graphify query "<question>"` when `graphify-out/graph.json` exists.
- Use `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for focused concepts.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query/path/explain are insufficient.

## 4. Context for Analysis

- **Transactions/rollbacks**: `bases/xtreme_system/api/crud_writes.py` (`safe_write`) and `components/xtreme_system/database/core.py` (`get_session`) centralize rollback logic. Find callers with `rg "session\.rollback\(\)" --include "*.py"`.
  - If a handler re-raises `IntegrityError` as `HTTPException`, `get_session` rolls back on its own — a redundant `session.rollback()` in that path is a finding worth flagging.
  - If a handler catches `IntegrityError` internally and returns directly without calling `session.rollback()`, that's a bug: the session is left dirty before `get_session` attempts its commit.
