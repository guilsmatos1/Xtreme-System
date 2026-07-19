---
paths:
  - "bases/xtreme_system/api/routes/**"
  - "components/*/core.py"
  - "components/*/workflows.py"
---

# Error Handling

- Business invariants raise typed errors in `core.py` (e.g. `FechamentoVendaError`), never a generic `Exception`.
- FK existence / availability checks belong in `workflows.py`, not `core.py`.
- Route-specific 400/409 responses are handled in `bases/api/routes/`, translating domain errors into `HTTPException`.
- Never swallow errors silently. Log or re-raise with context about what operation failed.
- Transactions and rollback are centralized in `get_session()` (`components/xtreme_system/database/core.py`). Before touching commit/rollback logic, read that function and `safe_write` in `bases/xtreme_system/api/crud_writes.py`, and `rg "session\.rollback\(\)"` for existing callers.
- If a handler re-raises `IntegrityError` as `HTTPException`, don't call `session.rollback()` yourself — `get_session` does it.
- If a handler catches `IntegrityError` and returns a response directly (without re-raising), it must call `session.rollback()` itself to reset session state before `get_session` commits.
- HTTP error responses: correct status codes (400 validation, 401/403 auth, 404 not found, 409 conflict, 500 unexpected). Never leak stack traces or raw DB errors to the client.
