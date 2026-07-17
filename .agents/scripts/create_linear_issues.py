import json
import subprocess
import sys

ASSIGNEE = "6b75d88f-389e-4bbb-bf7e-53528a774f93"
TEAM = "GUI"
STATE = "Backlog"

issues = [
    {
        "title": (
            "venda.search and compra.search build a cartesian"
            " product (implicit cross join)"
        ),
        "priority": "high",
        "label": "Bug",
        "body": (
            "Location: components/xtreme_system/venda/core.py:207 and"
            " components/xtreme_system/compra/core.py:126\n"
            "Impact: High\n"
            "Category: Performance\n"
            "Estimated effort: Low\n"
            "\n"
            "Description:\n"
            "Both search functions query one entity but filter on columns"
            " of other tables without ever joining them:\n"
            "\n"
            "```python\n"
            "# venda/core.py\n"
            "session.query(Venda).where(\n"
            "    or_(\n"
            "        Cliente.nome.ilike(pattern),\n"
            "        Veiculo.modelo.ilike(pattern),\n"
            "        Veiculo.placa.ilike(pattern),\n"
            "        Venda.status.ilike(pattern),\n"
            "        Venda.observacoes.ilike(pattern),\n"
            "    )\n"
            ").all()\n"
            "```\n"
            "\n"
            "Because `Cliente` and `Veiculo` are referenced in the `WHERE`"
            " clause but not joined, SQLAlchemy adds them to the `FROM`"
            " list as independent tables, producing"
            ' `Venda x Cliente x Veiculo`. The `lazy="joined"`'
            " relationships do not help.\n"
            "\n"
            "Why it matters:\n"
            "The search returns the wrong rows: a venda matches whenever"
            " any cliente or any veiculo in the whole database matches"
            " the term, and each real match is duplicated by the"
            " cross-product cardinality. Result size grows as"
            " rows(Venda) x rows(Cliente) x rows(Veiculo), so the query"
            " degrades badly as data grows. This is a correctness defect"
            " users will hit on every non-empty search term.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Join the referenced tables explicitly (and keep results"
            " distinct):\n"
            "\n"
            "```python\n"
            "session.query(Venda)\n"
            "    .join(Cliente, Venda.cliente_id == Cliente.id)\n"
            "    .join(Veiculo, Venda.veiculo_id == Veiculo.id)\n"
            "    .where(or_(Cliente.nome.ilike(pattern),"
            " Veiculo.modelo.ilike(pattern), ...))\n"
            "    .distinct()\n"
            "    .all()\n"
            "```\n"
            "\n"
            "Apply the same fix to compra.search."
        ),
    },
    {
        "title": ("Profit distribution leaves an unallocated rounding residual"),
        "priority": "high",
        "label": "Bug",
        "body": (
            "Location: components/xtreme_system/fechamento_venda/core.py:229\n"
            "Impact: High\n"
            "Category: Code quality\n"
            "Estimated effort: Low\n"
            "\n"
            "Description:\n"
            "Each investor's share is quantized independently:\n"
            "\n"
            "```python\n"
            "for item in data.participacoes:\n"
            "    valor = _quantizar(lucro * item.percentual"
            " / PERCENTUAL_TOTAL)\n"
            "    ...\n"
            "    caixa.criar_lancamento_fechamento(..."
            ", tipo=distribuicao_lucro, valor=valor, ...)\n"
            "```\n"
            "\n"
            "The sum of the per-investor `valor` need not equal"
            " `lucro_liquido`. Example: lucro = 1.00 split"
            " 33.33 / 33.33 / 33.34 yields 0.33 + 0.33 + 0.33 = 0.99,"
            " leaving 0.01 undistributed. The full receita is credited to"
            " the owning investor as one lançamento, but the"
            " distribuicao_lucro lançamentos silently fail to reconcile"
            " against lucro_liquido.\n"
            "\n"
            "Why it matters:\n"
            "This is a financial-integrity defect. Investor balances"
            " (caixa.saldo) drift by cents on every closing where the"
            " split does not divide evenly, and the drift is invisible"
            " because no invariant checks that distributions sum to the"
            " stored lucro_liquido.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Allocate the residual deterministically (e.g. give the last"
            " participant lucro - sum(others)), and assert the total:\n"
            "\n"
            "```python\n"
            "valores = [_quantizar(lucro * p.percentual"
            " / PERCENTUAL_TOTAL) for p in participacoes]\n"
            "valores[-1] += lucro - sum(valores)\n"
            "assert sum(valores) == lucro\n"
            "```"
        ),
    },
    {
        "title": (
            "In-memory rate limiter keyed by request.client.host"
            " is proxy- and worker-blind"
        ),
        "priority": "medium",
        "label": "Improvement",
        "body": (
            "Location: bases/xtreme_system/api/setup.py:90"
            " (_RateLimiter), setup.py:143\n"
            "Impact: Medium\n"
            "Category: Error handling and logging\n"
            "Estimated effort: Medium\n"
            "\n"
            "Description:\n"
            "The limiter stores a sliding window in a per-process dict"
            " keyed by `request.client.host` and never consults"
            " `X-Forwarded-For`:\n"
            "\n"
            "```python\n"
            "client_ip = request.client.host if request.client else"
            ' "desconhecido"\n'
            "```\n"
            "\n"
            "Behind a reverse proxy or load balancer (Docker/compose is"
            " present), client.host is the proxy's IP, so every client"
            " shares a single bucket. State also lives only in one process"
            ", so it is not shared across uvicorn workers or replicas.\n"
            "\n"
            "Why it matters:\n"
            "The login brute-force protection (_LOGIN_LIMIT = 5) becomes"
            " either useless (attacker's IP hidden behind the proxy along"
            " with everyone else) or a denial-of-service against all users"
            " (one shared bucket throttles the whole site after 5 login"
            " attempts). With multiple workers, the effective limit is"
            " limit x worker_count and non-deterministic. This is a"
            " security and availability control that does not behave as"
            " intended in production.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Derive the client IP from a trusted X-Forwarded-For"
            " (configure ProxyHeadersMiddleware / --forwarded-allow-ips),"
            " and move shared limiter state to an out-of-process store"
            " (Redis) if more than one worker/replica is deployed. If a"
            " single worker is guaranteed, at minimum honor the forwarded"
            " header and document the single-worker assumption."
        ),
    },
    {
        "title": (
            "File writes are not transactional — orphaned files on commit failure"
        ),
        "priority": "medium",
        "label": "Improvement",
        "body": (
            "Location: bases/xtreme_system/api/routes/ui_routes/uploads.py:34"
            " (salvar_arquivos) and"
            " bases/xtreme_system/api/routes/ui_routes/vendas.py:221"
            " (_persistir_contrato_venda)\n"
            "Impact: Medium\n"
            "Category: Maintainability\n"
            "Estimated effort: Medium\n"
            "\n"
            "Description:\n"
            "Files are written to disk during the request, then the DB"
            " row is created; the cleanup only covers the case where the"
            " create call raises:\n"
            "\n"
            "```python\n"
            'with path.open("wb") as f:\n'
            "    f.write(arquivo.file.read())\n"
            "try:\n"
            "    create_fn(session, schema.model_validate({...}))\n"
            "except Exception:\n"
            "    _remover_upload(path)\n"
            "    raise\n"
            "```\n"
            "\n"
            "But the actual commit happens later, in get_session()"
            " (database/core.py:60). If that commit fails (or any later"
            " step in the request raises after the file is written and"
            " the row flushed), get_session rolls back the DB row while"
            " the file stays on disk. register_post_commit callbacks only"
            " run after a successful commit, and after_rollback merely"
            " discards them — there is no rollback hook that deletes the"
            " just-written file.\n"
            "\n"
            "Why it matters:\n"
            "Disk accumulates orphaned upload/contract files with no DB"
            " reference. remover_orfaos handles only the inverse (DB row"
            " whose file vanished), so these orphans are never reclaimed."
            " Over time this is a storage leak and an audit/consistency"
            " gap.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Register a compensating cleanup on rollback for files written"
            " during the request, mirroring register_post_commit. For"
            " example track written paths in session.info and delete them"
            " in an after_rollback listener, or move file persistence to"
            " a post-commit step that writes only once the transaction is"
            " durable."
        ),
    },
    {
        "title": (
            'Audit trail depends on session.info["usuario_id"]'
            " set at runtime in 16 route files"
        ),
        "priority": "medium",
        "label": "Improvement",
        "body": (
            "Location: components/xtreme_system/auditoria/core.py:72"
            " (auditar), set in"
            " bases/xtreme_system/api/crud_ui/routes.py:343"
            " and 15 other route modules\n"
            "Impact: Medium\n"
            "Category: Architecture and design\n"
            "Estimated effort: Medium\n"
            "\n"
            "Description:\n"
            "Every audited write reads the acting user from mutable"
            " session state:\n"
            "\n"
            "```python\n"
            'usuario_id = session.info.get("usuario_id")\n'
            "if usuario_id is None:\n"
            "    raise AuditError\n"
            "```\n"
            "\n"
            "The contract \"set session.info['usuario_id'] before any"
            ' create/update/delete" is enforced only at runtime and is'
            " duplicated across at least 16 route files. Any new write"
            " path that forgets it fails with AuditError → HTTP 500."
            " Separately, the audit of lancamento_investimento deletion"
            " relies on the"
            " before_delete=caixa.deletar_lancamento_veiculo hook"
            " (veiculos.py:82) to delete via the ORM before the DB FK"
            ' ondelete="CASCADE" fires (caixa/core.py:36). Any deletion'
            " of a veiculo that does not go through that hook lets the"
            " database cascade remove lançamentos with no audit row.\n"
            "\n"
            "Why it matters:\n"
            "The audit invariant is invisible to the type system and easy"
            " to break silently — either as a 500 for the user, or as a"
            " silent gap in the audit trail (a compliance-relevant"
            " surface). The coupling is implicit and spread across the"
            " whole route layer.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Thread the acting user explicitly (e.g. a small write-context"
            " object passed into the CRUD layer, or a single"
            " dependency/middleware that binds usuario_id for all"
            " authenticated write routes) so the requirement is satisfied"
            " in one place. For cascade deletes, prefer explicit ORM"
            " deletion or database-level audit triggers rather than"
            " relying on every caller to invoke the before_delete hook."
        ),
    },
    {
        "title": (
            "whatsapp.get_config performs a write during read paths"
            " and can race on lazy creation"
        ),
        "priority": "medium",
        "label": "Bug",
        "body": (
            "Location: components/xtreme_system/whatsapp/core.py:49"
            " (get_config)\n"
            "Impact: Medium\n"
            "Category: Architecture and design\n"
            "Estimated effort: Low\n"
            "\n"
            "Description:\n"
            "get_config lazily inserts the singleton row when missing:\n"
            "\n"
            "```python\n"
            "def get_config(session):\n"
            "    config = session.get(WhatsappConfig, _CONFIG_ID)\n"
            "    if config is None:\n"
            "        config = WhatsappConfig(id=_CONFIG_ID)\n"
            "        session.add(config)\n"
            "        crud.flush(session)\n"
            "        session.refresh(config)\n"
            "    return config\n"
            "```\n"
            "\n"
            "It is called from notificar_venda (a side effect of creating"
            " a venda) and from the settings read path. Because"
            " get_session commits at the end of every request, a plain"
            " read that touches this function will INSERT and commit a"
            " row. Two concurrent first-time requests can both see None"
            " and both attempt to insert id=1, causing an IntegrityError"
            " on one of them.\n"
            "\n"
            "Why it matters:\n"
            "Reads with write side effects are surprising and make the"
            " endpoint non-idempotent; the race turns the very first"
            " concurrent access into a 500. It also means a GET can fail"
            " the whole request transaction under load.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Seed the singleton row via a migration (the config table"
            " already has a fixed _CONFIG_ID = 1), and have get_config"
            " return the row read-only (raise or return defaults if"
            " absent). If lazy creation must stay, use an upsert / ON"
            " CONFLICT DO NOTHING and re-fetch."
        ),
    },
    {
        "title": (
            "_schema_disponivel caches availability per-engine for the process lifetime"
        ),
        "priority": "medium",
        "label": "Improvement",
        "body": (
            "Location:"
            " components/xtreme_system/fechamento_venda/core.py:131\n"
            "Impact: Medium\n"
            "Category: Maintainability\n"
            "Estimated effort: Low\n"
            "\n"
            "Description:\n"
            "Schema availability is cached in a module-level"
            " WeakKeyDictionary keyed by engine:\n"
            "\n"
            "```python\n"
            "try:\n"
            "    return _SCHEMA_DISPONIVEL_POR_ENGINE[engine]\n"
            "except KeyError:\n"
            "    pass\n"
            "...\n"
            "_SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel\n"
            "```\n"
            "\n"
            "Once computed False (tables absent), the value is cached"
            " until the process restarts. If the app is running before"
            " make migrate and the migration is applied while it is up,"
            " the fechamento feature stays disabled (list_all returns [],"
            " confirmar raises ERRO_SCHEMA_DESATUALIZADO) until a restart."
            " It also introduces global mutable state that leaks between"
            " tests that build their own engines/sessions unless carefully"
            " isolated.\n"
            "\n"
            "Why it matters:\n"
            '"Feature silently stays off after the migration that enables'
            ' it" is an operationally confusing failure mode, and the'
            " permanent negative cache is a maintenance trap. The whole"
            " mechanism exists to tolerate a not-yet-migrated DB, which"
            " is itself a smell.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Either drop the runtime schema probe entirely and treat"
            " migrations as a hard precondition (simplest), or only cache"
            " the positive result and re-probe when it is False."
        ),
    },
    {
        "title": (
            "Cross-module reliance on private symbols weakens"
            " Polylith component boundaries"
        ),
        "priority": "low",
        "label": "Improvement",
        "body": (
            "Location: components/xtreme_system/crud/core.py:7,"
            " caixa/core.py:12, fechamento_venda/core.py:12"
            " (all import _snapshot, auditar from auditoria.core)\n"
            "Impact: Low\n"
            "Category: Architecture and design\n"
            "Estimated effort: Medium\n"
            "\n"
            "Description:\n"
            "_snapshot is an underscore-prefixed (private) function, yet"
            " it is imported and called across component boundaries (crud,"
            " caixa, fechamento_venda). Similarly, route modules import"
            " _found, _NaoAutenticadoError, etc. across base boundaries."
            ' The leading underscore signals "internal", but these are'
            " de-facto public contracts used repo-wide.\n"
            "\n"
            "Why it matters:\n"
            "Changing _snapshot's signature or behavior silently affects"
            " audit output for every component. The privacy marker is"
            " misleading and undermines the modular boundaries Polylith is"
            " meant to provide, making safe local edits harder to reason"
            " about.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Promote the genuinely shared helpers to public names"
            " (snapshot, and an explicit __all__ in auditoria.core), and"
            " keep truly private helpers underscored and unimported. This"
            " is a rename, not a redesign — do it in one pass to avoid"
            " churn."
        ),
    },
    {
        "title": (
            "Near-duplicated create/update route registration blocks"
            " in crud_ui/routes.py"
        ),
        "priority": "low",
        "label": "Improvement",
        "body": (
            "Location:"
            " bases/xtreme_system/api/crud_ui/routes.py:339"
            " (register_create_route) and routes.py:423"
            " (register_update_route)\n"
            "Impact: Low\n"
            "Category: Code quality\n"
            "Estimated effort: Medium\n"
            "\n"
            "Description:\n"
            "register_create_route and register_update_route share ~60"
            " lines of nearly identical control flow: same"
            " ValidationError/HTTPException → error_response, same"
            " IntegrityError → session.rollback()"
            " + conflict_form_response, same query_list + ok_response"
            " tail. The only differences are the presence of item_id/obj"
            " and which hook runs.\n"
            "\n"
            "Why it matters:\n"
            "The error-handling policy (which exceptions map to which"
            " response, when to roll back) is duplicated, so the two"
            " paths can drift — e.g. a fix to conflict handling applied"
            " to one and not the other. This is exactly the kind of"
            " divergence that produces inconsistent API behavior over"
            " time.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Extract the shared validate → write → respond pipeline into"
            " one helper parameterized by the write callable and the item"
            " context, so create and update differ only in what they pass"
            " in. Keep the change surgical — one internal helper, no"
            " behavior change — and cover it with the existing"
            " test_route_factories_* tests."
        ),
    },
    {
        "title": ("No test asserts search excludes non-matching rows"),
        "priority": "low",
        "label": "Improvement",
        "body": (
            "Location: tests/ (no coverage for venda.search"
            " / compra.search filtering correctness)\n"
            "Impact: Low\n"
            "Category: Testing\n"
            "Estimated effort: Low\n"
            "\n"
            "Description:\n"
            "There is broad CRUD/API test coverage, but nothing exercises"
            " that a search term returns only matching rows. This is why"
            " the cartesian-product defect in Finding #1 went unnoticed:"
            " a test that inserts one matching and one non-matching venda"
            " and asserts a single result would fail today.\n"
            "\n"
            "Why it matters:\n"
            "Search correctness is user-facing and currently wrong"
            " (Finding #1). Without a negative-case test, the fix can"
            " regress silently, and similar join bugs in future search"
            " functions will not be caught.\n"
            "\n"
            "Concrete fix suggestion:\n"
            "Add a focused test per searchable entity: seed two rows"
            " (one matching, one not), assert the result contains exactly"
            " the matching row and no duplicates. Add it before fixing"
            " Finding #1 so it reproduces the bug first, then passes.\n"
            "\n"
            "Example:\n"
            "\n"
            "```python\n"
            "def test_venda_search_excludes_non_matching(session):\n"
            '    match = make_venda(session, cliente_nome="Alice")\n'
            '    make_venda(session, cliente_nome="Bob")\n'
            '    result = venda.search(session, "Alice")\n'
            "    assert [v.id for v in result] == [match.id]\n"
            "```"
        ),
    },
]


def main():
    for i, issue in enumerate(issues, 1):
        sys.stdout.write(f"[{i}/{len(issues)}] Creating: {issue['title']}\n")
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "orca",
                "linear",
                "create",
                "--team",
                TEAM,
                "--title",
                issue["title"],
                "--body",
                issue["body"],
                "--assignee",
                ASSIGNEE,
                "--state",
                STATE,
                "--priority",
                issue["priority"],
                "--label",
                issue["label"],
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                sys.stdout.write(
                    f"  \u2713 Created: {data.get('url', data.get('id', 'unknown'))}\n"
                )
            except json.JSONDecodeError:
                sys.stdout.write(f"  \u2713 Response: {result.stdout.strip()}\n")
        else:
            sys.stdout.write(f"  \u2717 Error: {result.stderr.strip()}\n")
            sys.stdout.write(f"  stdout: {result.stdout.strip()}\n")


if __name__ == "__main__":
    main()
