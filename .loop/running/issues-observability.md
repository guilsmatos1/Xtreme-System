# Improvement opportunities

- **Generated:** 2026-08-01T00:53:06-03:00
- **Total:** 14

## imp-20260801-001 — Log start, outcome, and actor of every database restore/import

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, disaster-recovery, audit
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `components/xtreme_system/exportacao/core.py`
- **Related opportunities:** imp-20260801-002, imp-20260801-005, imp-20260801-012

### Location

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:265` — `ui_configuracoes_importar`

```python
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
        while chunk := await arquivo.read(1024 * 1024):
            f.write(chunk)
    detach_request_session(request, keep=(user,))
    try:
        await run_in_threadpool(exportacao.restore_database_from_file, tmp_path)
    except exportacao.RestoreEmAndamentoError as exc:
        return HTMLResponse(f"<p>{exc}</p>", status_code=409)
    except exportacao.ExportacaoError as exc:
```

### Description

This route runs `pg_restore --clean --if-exists` against the live database — the single most
destructive operation in the system, since it drops and recreates every table. The module declares
`logger = structlog.get_logger(__name__)` at line 40 but never calls it: there is no log line when a
restore starts, when it succeeds, when it is rejected because another restore holds the lock
(`RestoreEmAndamentoError`, line 279), or when `pg_restore` fails outright (`ExportacaoError`, line
281). The only trace an operator has is the HTML fragment rendered back to the admin's browser, which
is gone the moment the tab closes. If data disappears after a restore, there is nothing in the logs
that says a restore ran at all, who ran it, from which upload, or whether the pre-restore safety dump
at `exportacao.core.py:121` (`_salvar_backup_pre_restore`) actually completed.

### Why it matters

A destructive, irreversible, admin-triggered operation with zero operational record. Post-incident
reconstruction ("why is production data from last Tuesday?") requires correlating filesystem
timestamps in `backup_dir` against nothing at all — the actor and the exact failure point are
unrecoverable. This also removes the only evidence path for a malicious or accidental restore, which
is exactly the event most worth having an audit trail for.

### Concrete fix

Emit three structured events around the restore call using the module's already-declared `logger`:
one before `run_in_threadpool`, one on each failure branch, and one on success.

### Example

```python
logger.info("database_restore_started", actor_id=user.id, filename=arquivo.filename)
try:
    await run_in_threadpool(exportacao.restore_database_from_file, tmp_path)
except exportacao.RestoreEmAndamentoError:
    logger.warning("database_restore_rejected_lock_held", actor_id=user.id)
    ...
except exportacao.ExportacaoError as exc:
    logger.exception("database_restore_failed", actor_id=user.id, erro=str(exc))
    ...
else:
    logger.info("database_restore_succeeded", actor_id=user.id)
```

### Potential savings

Turns "we cannot tell whether a restore happened" into a single log query on
`event="database_restore_*"`, and gives the pre-restore dump a discoverable correlation point.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Verified the whole handler body (lines 265-318) contains no `logger` call.
  - Verified `logger` is already declared in the module at line 40, so the fix needs no new wiring.
  - Verified the underlying operation is `pg_restore --clean` at `exportacao/core.py:134-143`.
- **Weaknesses:**
  - The `auditar()` table may record some admin actions; I did not confirm whether restore is audited
    to the DB. Even if it were, a DB-level audit row is destroyed by the very restore it records.
- **Suggested checks:**
  - Confirm no reverse proxy access log already captures the POST with an actor identity.

## imp-20260801-002 — Capture pg_dump/pg_restore stderr instead of discarding it

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, subprocess, disaster-recovery
- **Files affected:** `components/xtreme_system/exportacao/core.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-012

### Location

`components/xtreme_system/exportacao/core.py:60` — `_run_pg_command`, `dump_database_to_file`

```python
def _run_pg_command(
    cmd: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603
            cmd,
            env=env,
            capture_output=True,
            check=False,
            timeout=_PG_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
```

### Description

`capture_output=True` collects `stderr`, and every caller then throws it away. `dump_database_to_file`
(line 79-83) checks `result.returncode != 0` and raises `ExportacaoError(_DUMP_FAILED)` — a fixed
string, "Não foi possível exportar o banco de dados." `restore_database_from_file` (line 144-146) does
the same with `_RESTORE_FAILED`, and `_listar_tabelas_do_dump` (line 98-100) with `_INVALID_BACKUP`.
PostgreSQL's actual diagnosis — wrong server version, authentication failure, disk full, permission
denied on a specific relation — is inside `result.stderr` and is never read, logged, or attached to
the exception. The module imports no logger at all.

### Why it matters

Backup and restore are the operations you only exercise under pressure. When an export starts failing,
the operator sees one identical Portuguese sentence for a version mismatch, a full disk, and a bad
password, and must reproduce the failure by hand with the same credentials to learn anything. That
turns a one-line diagnosis into an interactive debugging session during an incident. It also means a
silently failing nightly export is indistinguishable from a permissions problem.

### Concrete fix

Add a module logger and log the decoded, truncated `stderr` plus the command name and return code at
the point where a non-zero return code is detected. Do not put `stderr` into the user-facing exception
message — it can contain host and user details.

### Example

```python
logger = structlog.get_logger(__name__)

def _check(result: subprocess.CompletedProcess[bytes], cmd: list[str], msg: str) -> None:
    if result.returncode != 0:
        logger.error(
            "pg_command_failed",
            command=Path(cmd[0]).name,
            returncode=result.returncode,
            stderr=result.stderr.decode(errors="replace")[:2000],
        )
        raise ExportacaoError(msg)
```

### Potential savings

Cuts diagnosis of a failed backup from "reproduce the pg_dump by hand with production credentials" to
reading one log line.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Read the full 159-line module; it contains no logging import or call.
  - Verified all three non-zero-returncode branches (lines 82, 99, 145) discard `result.stderr`.
- **Weaknesses:**
  - `stderr` truncation length is a judgement call, not derived from an existing convention.
- **Suggested checks:**
  - Confirm `PGPASSWORD` cannot appear in `pg_restore` stderr output before logging it verbatim.

## imp-20260801-003 — Log authentication outcomes (failed and successful logins)

- **Impact:** High
- **Category:** Security
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, security, auth, alerting-readiness
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/auth.py`, `bases/xtreme_system/api/routes/json.py`
- **Related opportunities:** imp-20260801-005, imp-20260801-009, imp-20260801-010

### Location

`bases/xtreme_system/api/routes/ui_routes/auth.py:28` — `ui_login`

```python
def ui_login(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    user = usuario.get_by_username(session, username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(password, user.senha_hash)
    ):
```

### Description

Neither login path emits a log line. `auth.py` declares `logger` at line 15 and never uses it; the
JSON API twin at `bases/xtreme_system/api/routes/json.py:72-85` raises
`HTTPException(401, "Usuário ou senha inválidos")` with no logging either. Failed authentication,
successful authentication, and logins against a deactivated account (`not user.ativo`) all produce
identical silence. There is no record of which account was targeted, from which IP, or how many times.

### Why it matters

This is the single most important security signal a business application produces. Without it, a
credential-stuffing run against the admin account is invisible until it succeeds, and "who logged in
before the data changed?" is unanswerable. It also makes the login rate limiter
(`setup.py:310-319`, see imp-20260801-009) unmeasurable: you cannot tell whether it is firing
correctly or whether it is even being hit. Any alert on "brute force attempt" is impossible to build
today because there is no event to count.

### Concrete fix

Log one structured event per outcome in both login handlers, including the attempted username, the
client IP, and the failure reason — never the password.

### Example

```python
logger.warning(
    "login_failed",
    username=username,
    motivo="inativo" if user and not user.ativo else "credenciais",
    client_ip=request.client.host if request.client else None,
)
...
logger.info("login_succeeded", user_id=user.id, username=user.username)
```

### Potential savings

Makes a brute-force alert (`count(event="login_failed") by username`) buildable with no further code
changes, and gives every subsequent data change a preceding "who was here" line.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Read `auth.py` in full (66 lines): the declared `logger` has zero call sites.
  - Verified the JSON `/login` handler at `json.py:72-85` is also silent.
  - `request_id` is already bound by the `_request_context` middleware, so the events correlate for
    free.
- **Weaknesses:**
  - Logging the attempted username records a string a user typed; if someone types their password
    into the username field it lands in logs. Worth noting as a tradeoff.
- **Suggested checks:**
  - Decide whether the username should be hashed or truncated in logs per the project's PII stance.

## imp-20260801-004 — /health discards the database error that made it return 503

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, health-check, database
- **Files affected:** `bases/xtreme_system/api/routes/json.py`
- **Related opportunities:** imp-20260801-014

### Location

`bases/xtreme_system/api/routes/json.py:47` — `health`

```python
def health(session: SessionDep) -> JSONResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            {
                "status": "degradado",
                "database": "indisponivel",
                "database_target": get_database_target(),
            },
            status_code=503,
        )
```

### Description

The health endpoint catches `SQLAlchemyError` — the base class for every SQLAlchemy failure,
including `OperationalError`, `ProgrammingError`, and connection-pool exhaustion — and converts it to
a flat `"database": "indisponivel"` string with no logging whatsoever. The exception object is never
bound, so the driver's message ("could not connect to server", "too many connections", "SSL
connection has been closed unexpectedly") is destroyed at the `except` line. The module has no logger
at all.

### Why it matters

The health check is the one endpoint an orchestrator, load balancer, or uptime monitor polls
continuously, so it is the earliest and most frequently-sampled failure signal in the system. Today a
503 tells the operator only "database bad" — indistinguishable between a restarted Postgres, an
exhausted connection pool, and a mid-restore lock. Because `get_database_target()` is reported, the
system clearly cares about primary-vs-fallback state; losing the error behind it wastes that. Every
503 also means the process is silently swallowing an exception at potentially high polling frequency,
so a rate-limited log is the right shape.

### Concrete fix

Bind the exception and log it once with `logger.exception`, including the active database target.
Because health is polled frequently, log at `warning`/`exception` only on state transitions or accept
the volume knowingly.

### Example

```python
logger = structlog.get_logger(__name__)


def health(session: SessionDep) -> JSONResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception(
            "health_check_database_unavailable",
            database_target=get_database_target(),
        )
        return JSONResponse({"status": "degradado", ...}, status_code=503)
```

### Potential savings

Turns an opaque 503 into a root-caused one without an extra round trip to the DB host.

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Read the full handler; the `except` binds no exception variable and no logger exists in the file.
  - `get_database_target()` is already imported, so the fallback-state context is free to add.
- **Weaknesses:**
  - Log volume is a genuine tradeoff: a health probe every second during a long outage produces a
    stack trace per probe. The fix should acknowledge this (transition-only logging or sampling).
- **Suggested checks:**
  - Check the deployment's health-probe interval before choosing unconditional logging.

## imp-20260801-005 — Eleven route modules declare a logger and never call it

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, systemic, critical-path
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `bases/xtreme_system/api/routes/ui_routes/usuarios.py`, `bases/xtreme_system/api/routes/ui_routes/perfis.py`, `bases/xtreme_system/api/routes/ui_routes/auth.py`, `bases/xtreme_system/api/routes/ui_routes/conta.py`, `bases/xtreme_system/api/routes/ui_routes/clientes.py`, `bases/xtreme_system/api/routes/ui_routes/auditoria.py`, `bases/xtreme_system/api/routes/ui_routes/dashboard.py`, `bases/xtreme_system/api/routes/ui_routes/relatorios.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-003, imp-20260801-006, imp-20260801-011

### Location

`bases/xtreme_system/api/routes/ui_routes/vendas.py:63` — module scope

```python
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp
from xtreme_system.workflow.core import (
    recompute_vehicle_status_on_delete,
    validate_venda_create,
    validate_venda_update,
)

logger = structlog.get_logger(__name__)

# ---- Vendas (UI) ----

_CadastrarVendaDep = Annotated[
    usuario.Usuario, Depends(require_operacao("vendas", "cadastrar"))
]
```

### Description

Sixteen modules bind a structlog logger; eleven of them never emit a single record. A per-file count
of `logger.(info|warning|error|exception|debug)` call sites returns zero for `vendas.py`,
`compras.py`, `configuracoes.py`, `usuarios.py`, `perfis.py`, `auth.py`, `conta.py`, `clientes.py`,
`auditoria.py`, `dashboard.py`, and `relatorios.py`. Only `setup.py` (2), `database/core.py` (2),
`database/connection.py` (2), `investidores.py` (1), and `whatsapp/core.py` (1) actually log. That is
eight log statements for the entire application. The affected modules own every business-critical
write in the system: sale creation and closing, purchase entry, user and profile management, company
configuration and database restore.

The declared-but-unused logger is meaningful evidence rather than a style nit — it shows the
convention was established deliberately (correct import, correct `__name__` binding, `structlog`
already configured with request-id contextvars in `components/xtreme_system/logging/core.py`) and then
never applied. The infrastructure to fix this is complete; only the call sites are missing.

### Why it matters

Every business error path in these modules returns a rendered HTML fragment to the user and leaves no
server-side trace. When a salesperson reports "I couldn't close the sale yesterday afternoon," there
is nothing to look at. The operator's entire view of the application is the eight statements above,
plus whatever uvicorn's access log provides. Practically, mean-time-to-diagnose for any user-reported
functional failure is bounded below by "reproduce it yourself," because the logs contain no record
that the failure occurred.

### Concrete fix

Do not blanket-instrument. Add a `logger.warning` on the business-rule rejection branches and a
`logger.info` on successful writes in the highest-value handlers first: sale create/update/close
(`vendas.py`), purchase create/update (`compras.py`), user and profile writes (`usuarios.py`,
`perfis.py`), and company/database configuration (`configuracoes.py`). Bind the entity id and actor id
in every event; `request_id` is added automatically by the middleware.

### Example

```python
logger.info(
    "venda_criada",
    venda_id=obj.id,
    actor_id=user.id,
    cliente_id=cliente_obj.id,
)
logger.warning(
    "venda_rejeitada",
    motivo=msg,
    actor_id=user.id,
)
```

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Counted call sites mechanically across all 16 files that declare a logger; the eleven zero-count
    files are verified, not sampled.
  - Confirmed structlog is fully configured with contextvar merging and a request-id binding, so the
    missing piece really is the call sites.
- **Weaknesses:**
  - This finding is systemic and overlaps deliberately with imp-20260801-001, -003, and -006, which
    call out the highest-value individual sites. It should be treated as the umbrella, not as extra
    work on top of them.
  - "Add logging to eleven modules" is not a single reviewable change; the fix as written is a
    prioritization, not a complete plan.
- **Suggested checks:**
  - Confirm no separate access-log middleware exists outside the FastAPI app (e.g. in the
    reverse proxy or `casaos/` deployment config) that would already record request outcomes.

## imp-20260801-006 — safe_write turns every IntegrityError into a 409 with no trace of the cause

- **Impact:** High
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, database, critical-path
- **Files affected:** `bases/xtreme_system/api/crud_writes.py`
- **Related opportunities:** imp-20260801-005, imp-20260801-007, imp-20260801-014

### Location

`bases/xtreme_system/api/crud_writes.py:20` — `safe_write`

```python
def safe_write(op: Callable[[], ResultT], *, conflict_msg: str) -> ResultT:
    try:
        return op()
    except IntegrityError:
        raise HTTPException(status_code=409, detail=conflict_msg) from None


def run_hook(
    hook: Callable[[Session, ArgT], object] | None,
    session: Session,
    arg: ArgT,
) -> None:
    if hook:
        hook(session, arg)
```

### Description

`safe_write` is the shared write wrapper for the application's business writes. It catches
`IntegrityError` and re-raises an `HTTPException(409, conflict_msg)` with `from None`, which
explicitly severs the exception chain — the original `IntegrityError`, including the constraint name
and the driver's `orig` message, is discarded before anything can log it. The caller receives only a
generic conflict message such as "Venda já existe". The module imports no logger.

The `from None` is the crux: even the global `_request_context` middleware, which would log an
unhandled exception at `setup.py:226`, never sees it, because an `HTTPException` is a handled response
rather than an error.

### Why it matters

A 409 could mean a duplicate plate, a violated foreign key, a NOT NULL violation from a code bug, or a
check constraint the application never intended to hit. All four look identical to an operator and
identical to the user. If a schema change introduces an unexpected constraint violation on a hot write
path, users see "already exists" for a bug that has nothing to do with duplication, and no log line
ever distinguishes the two. That failure mode can persist indefinitely because nothing counts it.

### Concrete fix

Bind the exception, log it with the constraint detail at `warning`, and keep the user-facing message
unchanged.

### Example

```python
logger = structlog.get_logger(__name__)


def safe_write(op: Callable[[], ResultT], *, conflict_msg: str) -> ResultT:
    try:
        return op()
    except IntegrityError as exc:
        logger.warning(
            "write_conflict",
            conflict_msg=conflict_msg,
            erro=str(exc.orig),
        )
        raise HTTPException(status_code=409, detail=conflict_msg) from None
```

### Potential savings

Distinguishes a genuine duplicate from a schema bug immediately, instead of after a user-reported
"already exists" that nobody can reproduce.

### Self-critique

- **Confidence:** 9.5/10
- **Uncertain:** No
- **Strengths:**
  - Read the whole 76-line module; no logger, and the `from None` is explicit in the source.
  - Confirmed callers (e.g. `vendas.py:476-503`) re-catch the resulting `HTTPException` and render a
    template, so nothing downstream recovers the lost detail either.
- **Weaknesses:**
  - `str(exc.orig)` for a Postgres integrity error can include column values from the failed row,
    which may be PII (a client name or document number). The fix should log the constraint name
    rather than the full driver message if that matters.
- **Suggested checks:**
  - Inspect one real `IntegrityError.orig` payload from this schema to confirm what would be logged.

## imp-20260801-007 — Every session.rollback() site rolls back silently

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, database, rollback, transactions
- **Files affected:** `bases/xtreme_system/api/crud_ui/responses.py`, `bases/xtreme_system/api/routes/ui_routes/nested_writes.py`, `bases/xtreme_system/api/crud_ui/simple.py`, `bases/xtreme_system/api/routes/ui_routes/veiculos.py`, `bases/xtreme_system/api/routes/ui_routes/vendas.py`, `bases/xtreme_system/api/routes/ui_routes/compras.py`
- **Related opportunities:** imp-20260801-006, imp-20260801-013, imp-20260801-014

### Location

`bases/xtreme_system/api/crud_ui/responses.py:134` — `rollback_integrity_error_response`

```python
def rollback_integrity_error_response(
    session: Session, build_response: Callable[[], HTMLResponse]
) -> HTMLResponse:
    session.rollback()
    return build_response()


def list_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    *,
    user: object,
    list_key: str,
```

### Description

`rollback_integrity_error_response` is the shared "a write conflicted, undo the transaction and render
the error" helper, invoked from at least `simple.py:109/138/160`, `veiculos.py:301/410`,
`vendas.py:497/564`, `compras.py:462`, `perfis.py:123/155/181`, and `investidores.py:208/268`. It
rolls back and returns without logging anything. A sibling helper,
`nested_writes.py:27` (`rollback_se_criou_aninhados`), discards partially-created nested entities the
same way — silently.

A rollback is the clearest available marker that a user's work was thrown away. Right now that event
is invisible everywhere, and the two functions that centralize it are the cheapest possible place to
make it visible: one log line in each covers roughly a dozen call sites.

### Why it matters

Rollback frequency is a leading indicator. A spike means a constraint is being hit that users did not
expect, a UI is submitting bad data, or two flows are racing. Without a signal, that spike is only
discovered when users complain, and the diagnosis has no timeline to anchor on. This compounds with
imp-20260801-006: both the cause (the `IntegrityError`) and the effect (the rollback) are unlogged, so
a failed write leaves no evidence at either end.

### Concrete fix

Add one `logger.warning` inside `rollback_integrity_error_response` and one inside
`rollback_se_criou_aninhados`, naming the entity/label being rolled back. Do not add per-call-site
logging — the two helpers already cover the population.

### Example

```python
def rollback_integrity_error_response(
    session: Session, build_response: Callable[[], HTMLResponse]
) -> HTMLResponse:
    logger.warning("write_rolled_back", reason="integrity_error")
    session.rollback()
    return build_response()


def rollback_se_criou_aninhados(session: Session, *dados: object | None) -> None:
    if any(dado is not None for dado in dados):
        logger.warning("nested_write_rolled_back")
        session.rollback()
```

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Read the helper in full: five lines, no logging, no exception context available.
  - Enumerated call sites via a repo-wide sweep rather than assuming.
- **Weaknesses:**
  - The helper does not receive the entity label, so the log line is less specific than a per-site
    one would be. Passing a label through would widen the change beyond "smallest useful fix".
  - Combined with imp-20260801-006, the same failure would produce two log lines; that is intentional
    (cause and effect) but is a volume consideration.
- **Suggested checks:**
  - Verify no call site relies on `rollback_integrity_error_response` being side-effect-free for
    testing (a log call is harmless, but worth a glance at `tests/`).

## imp-20260801-008 — WhatsApp sale notification failures log without any correlating identifier

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** high
- **Risk level:** low
- **Tags:** observability, logging, background-job, correlation, external-api
- **Files affected:** `components/xtreme_system/whatsapp/core.py`
- **Related opportunities:** imp-20260801-012

### Location

`components/xtreme_system/whatsapp/core.py:134` — `_notificar_em_background`

```python
    config = WhatsappConfig(
        id=0,
        evolution_api_url=api_url,
        evolution_api_key=api_key,
        evolution_instance=instance,
        evolution_group_id=group_id,
    )
    try:
        _enviar(config, texto)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        logger.warning("whatsapp_notify_failed", error=str(exc))
```

### Description

This is the only background work in the application, and it does log its failure — but the event
carries no identifier that ties it to anything. It has no `venda_id`, no actor, and no `request_id`:
the work runs on a `ThreadPoolExecutor` thread (`_NOTIFICACAO_EXECUTOR`, line 21, `max_workers=2`),
and `structlog.contextvars` are per-context, so the `request_id` bound by the middleware at
`setup.py:222` is not present in the worker thread. The resulting line is effectively
`whatsapp_notify_failed error=<timeout>` with nothing to join on.

Two secondary gaps compound it. First, the `except` clause enumerates four exception types; anything
else raised inside `_enviar` — an `AttributeError` from a malformed config, a `KeyError` from the
template — propagates into the `Future` returned by `submit()`, which nobody inspects, so it is
swallowed with no log at all. Second, there is no success event, so "notifications stopped arriving"
cannot be distinguished from "no sales were made."

### Why it matters

When a salesperson says the WhatsApp group did not receive a sale, the operator has, at best, a
timestamped failure with no sale attached, and at worst nothing (the unhandled-exception path). Adding
`venda_id` makes that lookup a single query. The unhandled path is the more serious half: a config bug
that raises outside the four listed types disables sale notifications entirely and produces zero
signal, indefinitely.

### Concrete fix

Pass `venda_id` (and the request id, captured on the request thread) into `_notificar_em_background`
and bind them to the log event; broaden the handler to also catch `Exception` so nothing is swallowed
by the `Future`.

### Example

```python
def _notificar_em_background(..., venda_id: int, request_id: str | None) -> None:
    log = logger.bind(venda_id=venda_id, request_id=request_id)
    try:
        _enviar(config, texto)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        log.warning("whatsapp_notify_failed", error=str(exc))
    except Exception:
        log.exception("whatsapp_notify_error")
    else:
        log.info("whatsapp_notify_sent")
```

### Potential savings

Turns "did sale 4312's notification go out?" from unanswerable into one log query.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Verified the executor is a plain `ThreadPoolExecutor` (line 21-24) with no context propagation.
  - Verified `notificar_venda` (line 147) has `venda_obj` in scope at the point it schedules the send,
    so the id is available with no extra query.
  - Verified `submit()`'s `Future` is discarded at line 169, so unlisted exceptions have no sink.
- **Weaknesses:**
  - The contextvar-not-propagating claim is reasoned from `ThreadPoolExecutor` semantics rather than
    observed in a running log; it is standard behavior but not empirically confirmed here.
  - Adding a success `info` log per sale is a volume increase, though small at this scale.
- **Suggested checks:**
  - Run one sale end-to-end with `log_json=true` and confirm whether `request_id` appears on the
    `whatsapp_notify_failed` line.

## imp-20260801-009 — Rate-limit rejections produce a 429 with no log

- **Impact:** Medium
- **Category:** Security
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** observability, logging, security, rate-limit, alerting-readiness
- **Files affected:** `bases/xtreme_system/api/setup.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-010

### Location

`bases/xtreme_system/api/setup.py:307` — `_rate_limit`

```python
    client_ip = _client_ip(request)
    store = _get_rate_limit_store()

    if request.method == "POST" and path.endswith("/login"):
        allowed, retry_after = store.allow(
            f"login:{client_ip}", _LOGIN_LIMIT, _LOGIN_WINDOW_SECONDS
        )
        if not allowed:
            return _rate_limit_response(
                request,
                "Muitas tentativas de login. Tente novamente em instantes.",
                retry_after,
            )
```

### Description

Both rejection branches — the login-specific limiter at line 314 and the general limiter at line 324 —
return a 429 response without logging. The middleware sits in a module that does have a working logger
(used twice elsewhere, lines 166 and 226), so the omission is a gap in coverage rather than missing
infrastructure. The `client_ip` and the computed bucket (`user:<username>` or `ip:<addr>`, from
`_rate_limit_bucket` at line 278) are both already in scope at the rejection point.

### Why it matters

Rate limiting is a control you must be able to observe to trust. Without a log you cannot tell whether
a limit is too tight (legitimate users being blocked, showing up as unexplained "the system says too
many requests" complaints) or whether it is being hammered by an attacker. Combined with the absence of
login logging (imp-20260801-003), a sustained credential-stuffing attempt against this system produces
exactly zero log records — the attack and the defense are both invisible.

### Concrete fix

Log one `warning` in each rejection branch with the bucket, the path, and the client IP.

### Example

```python
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                bucket=f"login:{client_ip}",
                path=path,
                retry_after=retry_after,
            )
            return _rate_limit_response(
                request,
                "Muitas tentativas de login. Tente novamente em instantes.",
                retry_after,
            )
```

### Self-critique

- **Confidence:** 9/10
- **Uncertain:** No
- **Strengths:**
  - Read the middleware in full (lines 301-330); both rejection branches are verified silent.
  - The module logger is already in use nearby, so the fix is a two-line change.
- **Weaknesses:**
  - Under an actual flood, one log line per rejected request is itself a volume risk; a sampled or
    aggregated counter would be the more robust shape, which is a larger change than described.
- **Suggested checks:**
  - Confirm `_get_rate_limit_store()` is in-process only — if so, the log is the only cross-instance
    view of limiter behavior.

## imp-20260801-010 — Authorization denials (403) are never logged

- **Impact:** Medium
- **Category:** Security
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** observability, logging, security, authorization, audit
- **Files affected:** `bases/xtreme_system/api/setup.py`
- **Related opportunities:** imp-20260801-003, imp-20260801-009

### Location

`bases/xtreme_system/api/setup.py:362` — `_handle_nao_admin`, `_handle_nao_autorizado`

```python
@app.exception_handler(NaoAdminError)
def _handle_nao_admin(_request: Request, _exc: NaoAdminError) -> HTMLResponse:
    return HTMLResponse("<p>Requer papel admin</p>", status_code=403)


@app.exception_handler(NaoAutorizadoError)
def _handle_nao_autorizado(_request: Request, _exc: NaoAutorizadoError) -> HTMLResponse:
    return HTMLResponse(
        "<p>Seu perfil não tem acesso a esta página.</p>", status_code=403
    )


@app.exception_handler(Exception)
def _handle_erro_interno(request: Request, _exc: Exception) -> Response:
    if request.url.path.startswith("/ui/"):
        return HTMLResponse("<p>Erro interno. Contate suporte.</p>", status_code=500)
```

### Description

The two authorization-denial handlers discard both the request and the exception (note the `_request`
/ `_exc` underscore-prefixed parameters, signalling deliberate non-use) and render a 403 with no log.
`NaoAutorizadoError` is raised from real access-control checks including the authenticated-uploads
route at `setup.py:342-343`, where a user requesting a file they may not see is turned away with no
record.

### Why it matters

A permission denial is a security-relevant event in both directions. Repeated denials for one user
usually mean a misconfigured profile — a support problem that currently surfaces only as "the system
won't let me in," with no way to see which route or which permission was refused. A burst of denials
across many routes for one account looks like probing. Neither pattern is detectable today, and the
upload-authorization path in particular is exactly where you would want a record of who tried to
fetch what.

### Concrete fix

Log a `warning` in each handler with the path and the requesting identity. The handlers must start
using their `request` parameter (drop the underscore prefix).

### Example

```python
@app.exception_handler(NaoAutorizadoError)
def _handle_nao_autorizado(request: Request, _exc: NaoAutorizadoError) -> HTMLResponse:
    logger.warning(
        "acesso_negado",
        path=request.url.path,
        motivo="perfil",
    )
    return HTMLResponse(
        "<p>Seu perfil não tem acesso a esta página.</p>", status_code=403
    )
```

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Read both handlers verbatim; the underscore-prefixed parameters confirm nothing is inspected.
  - Traced `NaoAutorizadoError` to a real raise site at `setup.py:343` in the upload access check.
- **Weaknesses:**
  - The exception handler does not carry the authenticated user, so the log line would identify the
    request by path and `request_id` rather than by user id unless the raise sites are changed to
    attach it. That makes the smallest fix less useful than it first appears.
- **Suggested checks:**
  - Check whether `request.state` holds the resolved user at the time the handler runs; if so, the
    user id can be included without touching raise sites.

## imp-20260801-011 — Sale-closing features silently disable themselves when their tables are absent

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, migrations, feature-degradation
- **Files affected:** `components/xtreme_system/fechamento_venda/core.py`
- **Related opportunities:** imp-20260801-005

### Location

`components/xtreme_system/fechamento_venda/core.py:177` — `_schema_disponivel`, `get`

```python
    inspector = inspect(session.connection())
    disponivel = inspector.has_table(
        FechamentoVenda.__tablename__
    ) and inspector.has_table(ParticipacaoFechamentoVenda.__tablename__)
    _SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel
    return disponivel


def get(session: Session, fechamento_id: int) -> FechamentoVenda | None:
    if not _schema_disponivel(session):
        return None
    return crud.get(session, FechamentoVenda, fechamento_id)
```

### Description

When the `fechamento_venda` / `participacao_fechamento_venda` tables are missing, this helper returns
`False` and every dependent read degrades quietly: `get` returns `None` (line 185), `get_by_venda`
returns `None` (line 191), `ids_by_venda_ids` returns `{}` (line 196). No log is emitted, and the
result is cached per-engine in `_SCHEMA_DISPONIVEL_POR_ENGINE`, so the check happens once at startup
and the degraded mode persists for the process lifetime. The module has no logger.

The degraded state is indistinguishable from the normal one: a sale that has been closed and a sale
whose closure table does not exist both render as "not closed." Profit-sharing data for investors
simply does not appear.

### Why it matters

This is a designed graceful-degradation path — reasonable behavior, but invisible. If a migration is
skipped on one deployment, the application starts, serves traffic, and quietly omits sale-closing and
investor participation data forever, with no error and no log line. Discovery depends entirely on a
human noticing missing financial data. A single `warning` at the moment the check first resolves to
`False` converts an indefinite silent outage into a startup-time signal.

### Concrete fix

Log once, at the point the cache is populated with a negative result.

### Example

```python
    _SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel
    if not disponivel:
        logger.warning(
            "fechamento_venda_schema_ausente",
            tabelas=[FechamentoVenda.__tablename__,
                     ParticipacaoFechamentoVenda.__tablename__],
        )
    return disponivel
```

### Potential savings

Converts an open-ended "investor data is missing and nobody knows why" investigation into a single
startup warning.

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Read the helper and its three consumers (lines 185-200); all return empty results with no logging.
  - The per-engine cache means the suggested log fires once, so volume is not a concern.
- **Weaknesses:**
  - I did not confirm whether this degradation is expected in normal operation (e.g. during tests or a
    staged rollout), which would make a `warning` noisy. If it is routine in tests, `info` is the
    better level.
- **Suggested checks:**
  - Check whether the test suite runs against a schema missing these tables; if so, choose the level
    accordingly.

## imp-20260801-012 — No timing or counter metrics on any expensive or failure-prone operation

- **Impact:** Medium
- **Category:** Performance
- **Estimated effort:** Medium
- **Priority:** medium
- **Risk level:** medium
- **Tags:** observability, metrics, tracing, alerting-readiness, performance
- **Files affected:** `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`, `components/xtreme_system/exportacao/core.py`, `components/xtreme_system/whatsapp/core.py`, `components/xtreme_system/logging/core.py`
- **Related opportunities:** imp-20260801-001, imp-20260801-002, imp-20260801-008, imp-20260801-013

### Location

`bases/xtreme_system/api/routes/ui_routes/configuracoes.py:229` — `ui_configuracoes_exportar`

```python
def ui_configuracoes_exportar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> Response:
    detach_request_session(request, keep=(user,))
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        tmp_path = f.name
    try:
        exportacao.dump_database_to_file(tmp_path)
    except exportacao.ExportacaoError as exc:
        os.unlink(tmp_path)
```

### Description

The codebase has no metrics layer of any kind — no counters, no timers, no `/metrics` endpoint, no
tracing spans. There is a `/health` endpoint (`json.py:47`) and structured logging, and nothing else.
The operations most worth measuring are all unmeasured:

- `pg_dump` / `pg_restore` (`exportacao/core.py:60`), which run with a 300-second timeout — meaning
  the system already anticipates they can take minutes — with no record of how long they actually take
  or how often they time out.
- The Evolution API HTTP call (`whatsapp/core.py:126`) with a 10-second timeout, dispatched to a
  2-worker executor with an unbounded queue and no backlog signal.
- Database write latency on the shared `safe_write` path.

Because durations are never recorded, a backup that creeps from 20 seconds to 250 seconds crosses the
timeout threshold with no prior warning — the first signal is a hard failure.

### Why it matters

Regressions in these paths are invisible until they break. The `_PG_COMMAND_TIMEOUT_SECONDS = 300`
constant is a cliff the system will eventually walk off as the database grows, and there is no gradual
signal approaching it. Similarly, a saturated 2-worker notification executor would queue silently.

### Concrete fix

Do not add a metrics stack for this. The cheapest meaningful step, consistent with the existing
structlog setup, is to log durations as a keyed field on the events proposed elsewhere in this report,
which makes them queryable and alertable without new infrastructure. Introduce a real metrics
exporter only if a monitoring backend exists to receive it.

### Example

```python
inicio = time.monotonic()
exportacao.dump_database_to_file(tmp_path)
logger.info(
    "database_dump_concluido",
    duracao_s=round(time.monotonic() - inicio, 2),
    tamanho_bytes=Path(tmp_path).stat().st_size,
    actor_id=user.id,
)
```

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - Verified there is no metrics dependency and no `/metrics` route; `/health` is the only operational
    endpoint.
  - The 300s and 10s timeout constants are real and confirm the operations are known to be slow.
- **Weaknesses:**
  - "Add metrics" is only actionable if a collection backend exists; I found no evidence of one, which
    is why the fix deliberately proposes duration fields on log events instead of a metrics library.
    A reviewer may reasonably judge this to be a deployment decision rather than a code finding.
  - For a single-tenant application of this size, a full metrics stack may be disproportionate; the
    finding is scoped down accordingly but remains the softest item in this list.
- **Suggested checks:**
  - Confirm whether the `casaos/` deployment includes any Prometheus/Grafana-style collector.

## imp-20260801-013 — Upload cleanup deletes files on rollback with no record

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** observability, logging, silent-failure, uploads, data-loss
- **Files affected:** `components/xtreme_system/upload_file/core.py`, `bases/xtreme_system/api/routes/ui_routes/uploads.py`, `bases/xtreme_system/api/routes/ui_routes/configuracoes.py`
- **Related opportunities:** imp-20260801-007, imp-20260801-012

### Location

`components/xtreme_system/upload_file/core.py:44` — `escrever_upload_atomico`

```python
def escrever_upload_atomico(
    session: Session, upload_dir: Path, filename: str, content: bytes
) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / filename
    tmp_path = upload_dir / f".{filename}.tmp"
    try:
        tmp_path.write_bytes(content)
        with tmp_path.open("rb") as arquivo:
            os.fsync(arquivo.fileno())
        os.replace(tmp_path, path)
    except Exception:
```

### Description

Uploaded files are tied to the database transaction through post-rollback and post-commit callbacks.
Three cleanup paths delete files from disk with no log: the `except` branch at line 55-57, the
rollback callback `_remove_upload_on_rollback` at line 59-63, and the batch cleanup in
`uploads.py:64-68` which unlinks every file written during a failed multi-file upload. The
`configuracoes.py:196-198` logo path does the same.

There is partial coverage here worth crediting: `database/core.py:95` and `:115` log
`post_rollback_callback_failed` / `post_commit_callback_failed` when a callback itself raises. So a
cleanup that *errors* is logged; a cleanup that *succeeds* in deleting the user's file is not.

### Why it matters

From the user's side, the file vanished. From the operator's side, there is no record it ever existed
or that the system deleted it. When a user reports "I attached three photos and only one saved," there
is no way to confirm whether the upload failed, the transaction rolled back and cleanup ran as
designed, or something deleted the file later. Since these callbacks are correct-by-design, the value
here is purely evidentiary — but it is the difference between a five-minute answer and an unresolvable
report.

### Concrete fix

Log at `info` inside the rollback callback and the batch cleanup loop, naming the file(s) removed.

### Example

```python
    def _remove_upload_on_rollback(
        *, path: Path = path, tmp_path: Path = tmp_path
    ) -> None:
        logger.info(
            "upload_removido_por_rollback",
            path=str(path),
        )
        path.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)
```

### Self-critique

- **Confidence:** 8/10
- **Uncertain:** No
- **Strengths:**
  - Read all three cleanup paths; none logs on the success path.
  - Confirmed the adjacent callback-failure logging in `database/core.py` exists, so the fix extends an
    established convention rather than inventing one.
- **Weaknesses:**
  - Lower operational severity than the rest of this list: the behavior is correct, and the missing
    log is evidentiary rather than a live blind spot on a failing path.
  - Filenames are UUID-based, so the log line is only useful when joined with the DB row that
    referenced it.
- **Suggested checks:**
  - Confirm whether upload URLs are considered sensitive before logging full paths.

## imp-20260801-014 — Request-scoped commit/rollback decisions are not logged

- **Impact:** Medium
- **Category:** Error handling and logging
- **Estimated effort:** Low
- **Priority:** medium
- **Risk level:** low
- **Tags:** observability, logging, database, transactions, request-lifecycle
- **Files affected:** `components/xtreme_system/database/core.py`
- **Related opportunities:** imp-20260801-004, imp-20260801-006, imp-20260801-007

### Location

`components/xtreme_system/database/core.py:166` — `finish_request_session`

```python
    try:
        if error is not None:
            session.rollback()
        elif _should_commit_session(request):
            session.commit()
            invoke_post_commit(session)
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
```

### Description

This function and its dependency-injection twin `get_session` (line 182-200) own the transaction
boundary for every request in the application. Both contain an `except Exception: session.rollback();
raise` clause that fires when the **commit itself** fails — a serialization failure, a deferred
constraint violation, a connection drop mid-commit — and neither logs. The module has a logger and
uses it twice nearby (lines 96 and 116), so the omission is inconsistent with its own file.

A commit failure here is not the same as the handled `IntegrityError` conflicts covered by
imp-20260801-006: it happens after the handler has already decided the request succeeded. The
exception does re-raise and will be caught by the `_request_context` middleware, which logs
`unhandled_error` at `setup.py:226` — so this is not fully silent. What is lost is the attribution:
the middleware log says an unhandled error occurred at a URL, not that the transaction failed at commit
time after the handler completed successfully.

### Concrete fix

Log at `error` inside the `except` clause in both `finish_request_session` and `get_session` before
re-raising, so the commit-time failure is distinguishable from a handler-time one.

### Example

```python
    except Exception:
        logger.exception(
            "request_commit_failed",
            method=request.method,
            path=request.url.path,
        )
        session.rollback()
        raise
```

### Self-critique

- **Confidence:** 7.5/10
- **Uncertain:** Yes
- **Strengths:**
  - Read both functions in full; neither logs, while the same module logs in two other places.
  - Confirmed `tests/test_request_context.py:62` has a
    `test_commit_failure_returns_error_before_success_response` test, so this path is exercised and a
    log assertion could be added cheaply.
- **Weaknesses:**
  - This is the weakest "silent failure" claim in the report: the middleware at `setup.py:226` does
    log the re-raised exception, so an operator is not blind — only under-informed about *where* it
    failed. Priority is set accordingly.
  - I did not verify that every path into `finish_request_session` is wrapped by the
    `_request_context` middleware; the detached-session path in particular returns early.
- **Suggested checks:**
  - Trigger a commit failure locally and confirm the middleware log line alone is enough to identify
    it as a commit-time failure.

## Discarded candidates

### `_handle_erro_interno` catch-all returns 500 without logging

`bases/xtreme_system/api/setup.py:374` registers an `Exception` handler that returns a 500 with no log
call. This looks like a major blind spot but is not: in Starlette the user-defined `_request_context`
middleware (line 210) sits inside `ServerErrorMiddleware` and catches the exception first, logging it
via `logger.exception("unhandled_error", ...)` at line 226 before returning its own 500. The handler
is therefore near-unreachable for requests passing through the middleware stack.
`tests/test_request_context.py:45` (`test_unhandled_error_logs_once_cleans_context_and_keeps_request_id`)
confirms the logging happens exactly once. Discarded as already covered.

### No per-request access log

Only unhandled exceptions are logged per request; there is no "request completed" line with method,
path, status, and duration. This was folded into imp-20260801-005 rather than listed separately,
because uvicorn emits its own access log and is routed through the same structlog processors by
`configure_logging()` (`components/xtreme_system/logging/core.py:64-66`), which likely already covers
the basic case. Reported separately it would be a duplicate with unverified premises.

### Missing debug logging in `veiculo.get_by_placa`

`components/xtreme_system/veiculo/core.py:270-274` catches `PlacaInvalidaError` and returns `None`
without logging. This is a lookup helper where an invalid plate is an ordinary, expected input
(a user typing a malformed plate into a search box), not a failure. Logging it would add noise with no
operational value. Discarded as Low impact.

### `auditar()` skips tables silently

`components/xtreme_system/auditoria/core.py:78-79` returns early for tables in `AUDIT_SKIP` with no
log. This is a static, intentional configuration rather than a runtime failure, and logging every
skipped write would be pure volume. Discarded as Low impact.

### `client_resolution.py` validation `except` blocks

`bases/xtreme_system/api/routes/ui_routes/client_resolution.py:25` and `:50` swallow `ValueError` /
`ValidationError` during form parsing. These are user-input validation paths whose outcome is already
surfaced to the user as a form error; the failures are expected and high-frequency. Covered in
aggregate by imp-20260801-005 rather than as an individual finding.
