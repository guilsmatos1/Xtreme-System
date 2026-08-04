# Transactions and rollbacks

Read this **before** changing transaction boundaries, commits, or rollbacks.

## Sources of truth

1. `bases/xtreme_system/api/crud_writes.py` — `safe_write`
2. `components/xtreme_system/database/core.py` — `get_session`

Before editing, find callers:

```bash
rg "session\.rollback\(\)" --include "*.py"
```

## Rules

- Rollback is centralized in `get_session()`.
- If a handler re-raises `IntegrityError` as `HTTPException`, do **not** call
  `session.rollback()` — `get_session` handles it. A redundant rollback in that
  path is a finding worth flagging in analysis.
- If a handler catches `IntegrityError` internally and returns a response without
  re-raising, it **must** call `session.rollback()` before `get_session` attempts
  its commit — otherwise the session stays dirty (bug).
