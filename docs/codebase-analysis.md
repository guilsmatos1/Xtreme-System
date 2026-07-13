9. ui.py é god-file de 1.737 linhas misturando 12 domínios
- Localização: bases/xtreme_system/api/routes/ui.py (clientes, vendas, login, veículos+imagens, investidores, lançamentos, usuários, perfis, configurações, dashboard, auditoria).
- Descrição: Apesar das factories em route_factories.py, tudo que foge do padrão (veículo com uploads, investidor com saldo, dashboard com KPIs) é colado aqui. Arquivo difícil de navegar; mudanças em domínios distintos_topam na mesma tela; alto risco de merge conflicts.
- Impacto: Médio — categoria Manutenibilidade / Arquitetura.
- Sugestão: partir em routes/ui_{veiculos,vendas,investidores,usuarios,perfis,auditoria,dashboard}.py, cada um importando app de setup. Manter as factories no nível de setup.py (registry).
- Esforço: Médio (movimento mecânico + ajuste de imports; testes continuam válidos porque registram por app).
10. Uploads: content-type spoofável + path-traversal latente em _uploaded_file_path
- Localização: bases/xtreme_system/api/routes/ui.py:263-291 (_validar_uploads, _uploaded_file_path); usados em 312-350 e 462-500 (unlink em deleção).
- Descrição: Dois pontos frágeis na defesa de uploads:
1. _validar_uploads confia no Content-Type enviado pelo cliente — trivial de forjar com curl -F "imagens=@mal.xhtml;type=image/jpeg". Não há checagem de magic bytes.
2. _uploaded_file_path(url) faz _ui_dir / url.lstrip("/") sem resolver ... Hoje a url é gerada pelo servidor (uuid4().hex), então a exploração exige escrita no DB — mas .. em /static/uploads/../../etc/... escapa do diretório e o path.unlink() na rota de excluir apagaria arquivos arbitrários. Defense-in-depth vale a trava.
- Impacto: Baixo-Médio — categoria Segurança.
- Sugestão:
_ROOT = (_ui_dir / "static" / "uploads").resolve()
def _uploaded_file_path(url: str) -> Path | None:
    if not url.startswith("/static/uploads/"): return None
    p = (_ui_dir / url.lstrip("/")).resolve()
    if not p.is_relative_to(_ROOT): return None   # trava traversal
    return p
E sniffar 4-8 bytes do arquivo (imghdr/filetype) ou servir PDFs via endpoint com Content-Disposition: attachment (não como StaticFiles).
- Esforço: Baixo-Médio.



1. session.commit() inside the CRUD layer breaks transactional atomicity
Location: components/xtreme_system/crud/core.py:30,48,64; also caixa/core.py:153,178, usuario/core.py:75,99,113, perfil via crud
Category: Architecture / Error handling — Impact: High — Effort: Medium
crud.create/update/delete each call session.commit() internally, and get_session (database/core.py:32) never commits. Multi-step routes therefore can't roll back as a unit. Worst case: _criar_veiculo (ui.py:707-723) does veiculo.create (commit) → cliente.create (commit) → compra.create (commit) → caixa.criar_lancamento_veiculo (commit). If compra or caixa fails after the first commit, a Veiculo row persists with no purchase and no cash lançamento — silent data corruption. Same pattern on venda.update: crud.update commits, then _sincronizar_status_veiculo (venda/core.py:132) commits again; if the second commit fails the veículo status diverges from the venda.
Fix: Remove session.commit() from crud.create/update/delete (and the manual ones in caixa/usuario). Commit once per request — either at the end of get_session on success, or explicitly in the route factory after all hooks ran:
# database/core.py
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        session.commit()   # single transactional boundary
    finally:
        session.close()
Then delete every session.commit() inside crud/*, caixa.criar_lancamento_veiculo, sincronizar_lancamento_veiculo, usuario.create/change_password/set_perfil, whatsapp.get_config, and _sincronizar_status_veiculo. The audit auditar() only adds/flushes — perfect, it now rides the same transaction.
2. UI CRUD factory lets IntegrityError become a 500 instead of a friendly 409
Location: bases/xtreme_system/api/route_factories.py:288 (_criar) and :306 (_atualizar)
Category: Error handling — Impact: High — Effort: Low
register_crud_ui_routes._criar wraps only validation in try/except, then calls obj = module.create(session, data) raw. Any unique-constraint violation (e.g. duplicate placa) propagates as IntegrityError, hits the global handler, and renders the generic "Erro interno. Contate suporte." page. The JSON factory (route_factories.py:95) wraps the same call in _safe_write, and register_ui_simples._criar (route_factories.py:421-430) explicitly catches IntegrityError → re-renders the form with "já existe". The full register_crud_ui_routes path is the only one missing the guard.
Fix: Wrap both calls and re-render the form on conflict:
try:
    obj = module.create(session, data)
    _run_hook(after_create, session, obj)
except IntegrityError:
    session.rollback()
    return _erro(request, session, HTTPException(409, f"{label} já existe"), None)
return _ok(request, session, user)
Apply the same to _atualizar.
3. WhatsApp notification blocks venda creation synchronously (10s timeout)
Location: whatsapp/core.py:105 (urllib.urlopen(..., timeout=10)); notificar_venda called as after_create hook at json.py:210 and ui.py:133
Category: Performance / Error handling — Impact: Medium — Effort: Medium
notificar_venda is best-effort (it swallows URLError/OSError/TimeoutError/ValueError — good), but it runs inline in the request with a 10s socket timeout. If the Evolution API is slow, every POST /vendas (JSON) and every venda create via UI blocks the worker for up to 10 seconds, and any other exception type (e.g. http.client.HTTPException, malformed-JSON JSONDecodeError from the upstream) is not swallowed → venda create fails after the venda and veiculo-status commits already happened (see #1).
Fix: Two cheap options:
- Broaden the catch to Exception in notificar_venda so a malformed upstream response never fails the venda; and/or
- Move the send to a background task: fastapi.BackgroundTasks for JSON, or threading.Thread(...).start()/a small queue for the UI path, so the request returns immediately.
except Exception as exc:  # noqa: BLE001 -- best-effort notify must never break venda
    logger.warning("whatsapp_notify_failed", error=str(exc))
4. agregados_investidores loads every veículo and every caixa lançamento into Python on each render
Location: caixa/core.py:193-209 (marked ponytail:);called by _ctx_investidores (ui.py:798), /exportar (ui.py:866), and per-row sort
Category: Performance — Impact: Medium — Effort: Low
veiculos = crud.list_all(session, Veiculo)   # SELECT * FROM veiculo
for v in veiculos: ...                        # aggregate in Python
for lanc in list_all(session): ...            # SELECT * FROM lancamento_investimento
This runs on every GET /ui/investidores, every HX-Request partial reload, every sort toggle, and every export. The existing saldos() next to it already proves the one-query pattern (GROUP BY investidor_id).
Fix: Replace both loops with two grouped queries (mirrors saldos):
def agregados_investidores(session):
    num_val = (
        session.query(Veiculo.investidor_id, func.count(), func.sum(Veiculo.preco))
        .group_by(Veiculo.investidor_id).all()
    )
    num = {iid: c for iid, c, _ in num_val}
    valor = {iid: (t or Decimal("0")) for iid, _, t in num_val}
    aportes = dict(saldos(session))  # already sums aporte - custo per investidor
    return num, valor, aportes
Keeps the dict[int, ...] contract used by _ctx_investidores.
5. Rate limiter leaks memory: per-IP deques are never removed
Location: bases/xtreme_system/api/setup.py:87-101 (_RateLimiter._hits)
Category: Maintainability / Performance — Impact: Medium — Effort: Low
_hits = defaultdict(deque) and allow(key) only pops stale entries from the deque it looked up — the key itself stays in the dict forever. A long-lived process hit by many distinct client IPs (proxies, scanners, NAT'd clients) accumulates one entry per IP indefinitely. The ponytail: ceiling here is real and worth naming.
Fix: Drop empty deques during the prune, and/or periodically reap stale keys:
def allow(self, key: str) -> bool:
    now = time.monotonic()
    hits = self._hits[key]
    cutoff = now - self._window
    while hits and hits[0] < cutoff:
        hits.popleft()
    if not hits:
        del self._hits[key]          # reclaim the slot
    if len(hits) >= self._limit:
        return False
    hits.append(now)
    return True
(Note: deleting before the >= limit check is fine — an empty deque is below the limit.) Also document the single-process caveat: this limiter does not work behind multiple uvicorn workers.
6. File uploads are written to disk before the DB row commits; orphans on failure, and content-type is trusted from the client
Location: ui.py:341-349 (_criar_veiculo imagens write → imagem_veiculo.create), ui.py:373-392 (_salvar_documentos_cliente), ui.py:263-285 (_validar_uploads)
Category: Error handling — Impact: Medium — Effort: Medium
Flow today: path.open("wb"); f.write(imagem.file.read()) then imagem_veiculo.create(...) which commits. If the commit fails (or the request is interrupted between writes), the file is orphaned on disk with no DB record; conversely, combined with #1, a later-step failure can leave the veículo committed while uploaded files have no referencing row. Separately, _validar_uploads trusts arq.content_type (set by the client) and only checks the extension matches the declared content-type — no magic-byte sniff, so a malware.exe renamed foo.jpg is stored and later served from /static/uploads/.
Fix (orphans): write to a temp path, insert the DB row, then os.replace to the final path; or insert the row first (with the planned URL) and only read()/write() after flush succeeds. Combined with #1, the whole write becomes atomic per request.
Fix (content sniffing): read the first few bytes and compare to known magic numbers (JPEG FFD8FF, PNG 89 50 4E 47, PDF 25 50 44 46, WEBP RIFF...WEBP) before persisting. Cheap and removes the trust-on-client gap.
7. No double-sell guard: a venda can be created for an already-vendido/reservado veículo
Location: json.py:114-120 (_validate_cliente_veiculo_fks); venda status sync in venda/core.py:101-134
Category: Correctness (business rule) — Impact: Medium — Effort: Low
_validate_cliente_veiculo_fks only checks that the FK rows exist — never that veiculo.status == StatusVeiculo.disponivel. Nothing else blocks a second venda against a veículo already in vendido or reservado. _status_veiculo_para_venda only flips the veículo status when the venda goes to concluido/cancelado, so a venda created directly in pendente against an already-vendido veículo silently leaves two sales referencing one car. The UI filters the dropdown (ui.py:95, veiculos_disponiveis) but the JSON POST /vendas endpoint is unguarded.
Fix: Extend the validator:
if veiculo_id is not None:
    v = veiculo.get(session, veiculo_id)
    if v is None:
        raise HTTPException(400, "veiculo_id inexistente")
    if v.status != veiculo.StatusVeiculo.disponivel:
        raise HTTPException(409, f"veículo indisponível (status={v.status.value})")
Add a test creating a second venda for the same veículo and assert it 409s.
8. Test suite runs on SQLite in-memory while production runs PostgreSQL — divergent semantics hide the bugs above
Location: tests/conftest.py:21 (create_engine("sqlite://", ...))
Category: Testing — Impact: Medium — Effort: Medium
SQLite differs from Postgres in ways that matter for this codebase: JSON column typing, Numeric precision, String case sensitivity on unique, ON DELETE CASCADE enforcement quirks, SELECT FOR UPDATE/row-locking semantics, and func.now() timezones. The commit-per-operation pattern (#1) and the orphaned-upload behavior (#6) both don't surface under SQLite + per-test schema creation. The README explicitly states Postgres is the prod DB. There's a _reset_rate_limiters autouse fixture (good), but no PG-backed suite.
Fix: Add a db_session_postgres fixture driven by DATABASE_URL or a testcontainers/postgres:16 service in CI; gate the genuinely Postgres-dependent tests (cascades, unique case sensitivity, JSON, concurrency) behind it. Keep the fast SQLite path for unit-style component tests of pure logic. At minimum, run make ci once against a real PG (the docker-compose.yml already has postgres:16) so #1/#6/#7 regression tests exist somewhere.
9. Image/document modals stat every file on every open
Location: ui.py:294-303 (_imagem_modal), ui.py:436-449 (_documentos_modal)
Category: Performance — Impact: Low — Effort: Low
Each modal open iterates item.imagens / item.documentos and calls path.exists() per row, deleting the DB row if the file is missing. For a veículo with N images, that's N synchronous stat syscalls per click → on a network FS or large catalog this is noticeably laggy, and the modal is UIAdmin-only and frequently opened. The cleanup also runs inside a GET that mutates state (deletes rows + commits via imagem_veiculo.delete), which is a side-effecting GET.
Fix: Either lazy-check on demand (the template <img> shows a broken link anyway; let a separate cleanup job reap orphaned files), or batch the existence check with a single directory listing:
existing = {p.name for p in upload_dir.iterdir()} if upload_dir.is_dir() else set()
for img in list(item.imagens):
    name = _uploaded_file_path(img.url or "")
    if name is not None and name.name not in existing:
        imagem_veiculo.delete(session, img)
And move the cleanup out of the GET handler into a periodic task / a POST endpoint.
10. CORS policy is fully open (*) for origins, methods, and headers
Location: bases/xtreme_system/api/setup.py:40-45
Category: Security — Impact: Low–Medium — Effort: Low
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
The JSON API uses Bearer tokens (not cookies), so * is less catastrophic than for a credentialed UI — but the app also exposes the HTMX UI under /ui/* with an httpOnly cookie. Browsers block credentialed requests to * origins, but the permissive methods/headers still widen the attack surface for any browser-reachable endpoint, and the intent ("internal tool") isn't encoded. ARCHITECTURE.md even documents the cookie UI — allow_origins=["*"] is the wrong default for that.
Fix: Pin the allowed origins to the actual UI host(s) (configurable via Settings), keep methods/headers to what's used, and leave allow_credentials explicit:
allow_origins=settings.cors_origins,        # ["http://localhost:8000", prod URL]
allow_methods=["GET", "POST", "PATCH", "DELETE"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
allow_credentials=True,



1. Move transaction control out of CRUD helpers
     Location: components/xtreme_system/crud/core.py:18, bases/xtreme_system/api/route_factories.py:90, components/xtreme_system/venda/core.py:137, bases/xtreme_system/
     api/routes/ui.py:668, components/xtreme_system/caixa/core.py:132
     Description: crud.create/update/delete() commit internally, and callers then run more side effects afterward. That breaks atomicity. The worst case is vehicle
     creation: the vehicle can be committed before the seller, uploaded docs, purchase row, and investor cash entry are all finished. If step 4 fails, steps 1-3 stay
     persisted. This hurts correctness, architecture, maintainability, and makes error handling brittle.
     Impact: High · Category: Architecture and design
     Concrete fix suggestion:

  def create(...):
      obj = model_cls(**data.model_dump())
      session.add(obj)
      session.flush()
      auditar(...)
      return obj

  with session.begin():
      obj = veiculo.create(session, data)
      seller = cliente.create(session, novo_cliente_data)
      compra.create(session, ...)
      caixa.criar_lancamento_veiculo(session, obj)

  Also add tests that force compra.create() or caixa.criar_lancamento_veiculo() to fail and assert that no partial rows remain.
  Estimated effort: High

  2. Sale lifecycle does not preserve vehicle-state invariants
     Location: components/xtreme_system/venda/core.py:109, components/xtreme_system/venda/core.py:154, bases/xtreme_system/api/routes/json.py:114, tests/
     test_api_vendas.py:138, tests/test_ui.py:405
     Description: The backend only validates FK existence for sales. It does not prevent creating multiple concluded sales for the same vehicle, and venda.delete()
     never restores the vehicle status. I verified locally that two concluded sales can be created for one vehicle, and deleting a concluded sale leaves the vehicle as
     vendido. This is a correctness bug first, with missing tests around delete and duplicate-sale cases.
     Impact: High · Category: Architecture and design
     Concrete fix suggestion:

  def _assert_venda_permitida(session: Session, data: VendaCreate | VendaUpdate, obj: Venda | None = None) -> None:
      veic = session.get(Veiculo, data.veiculo_id)
      if veic is None:
          raise HTTPException(400, "veiculo_id inexistente")
      if veic.status == StatusVeiculo.vendido and (obj is None or obj.veiculo_id != veic.id):
          raise HTTPException(409, "Veículo já vendido")

  And on delete, recompute the vehicle status from remaining sales before commit.
  Estimated effort: Medium

  3. Generic HTMX CRUD routes turn recoverable DB errors into 500s
     Location: bases/xtreme_system/api/route_factories.py:277, bases/xtreme_system/api/route_factories.py:294, bases/xtreme_system/api/setup.py:48, tests/
     test_route_factories_ui.py:23
     Description: JSON CRUD routes use _safe_write(), but HTMX CRUD routes call module.create/update/delete() directly. A duplicate client document or plate becomes an
     uncaught IntegrityError, a 500, and duplicated error logs. I confirmed this locally with /ui/clientes. The current tests for UI route factories only cover template
     wiring and _sort_key, not failure paths.
     Impact: High · Category: Error handling and logging
     Concrete fix suggestion:

  try:
      obj = module.create(session, data)
  except IntegrityError:
      session.rollback()
      return templates.TemplateResponse(
          request, form_template,
          {**ctx_form(session), item_key: None, "erro": f"{label} já existe"},
          status_code=409,
      )

  Add regression tests for duplicate create/update and delete FK conflicts through the generic UI routes.
  Estimated effort: Medium

  4. Tests bypass Alembic/Postgres and are already hiding schema drift
     Location: tests/conftest.py:18, components/xtreme_system/venda/core.py:34, alembic/versions/d9babf49fd9b_add_vendedor_and_reservado.py:28
     Description: Tests build the schema with Base.metadata.create_all() on SQLite instead of running migrations on Postgres. That already diverged: the migration makes
     venda.data_venda nullable, but the ORM model still declares it non-nullable. This weakens correctness, testing confidence, and maintainability because the tested
     schema is not the deployed schema.
     Impact: High · Category: Testing
     Concrete fix suggestion:

  # test bootstrap
  engine = create_engine(TEST_DATABASE_URL)
  alembic.command.upgrade(cfg, "head")

  At minimum, add one CI job that runs API tests against migrated Postgres. Then remove model/migration drift like Venda.data_venda.
  Estimated effort: High

  5. ui.py is a god module with route-to-route coupling
     Location: bases/xtreme_system/api/routes/ui.py:22, bases/xtreme_system/api/routes/ui.py:626, bases/xtreme_system/api/routes/ui.py:668
     Description: The HTMX route file is 1.7k lines and mixes login, vehicles, uploads, investors, users, profiles, config, dashboard, and audit. It also imports
     validation helpers from the JSON route module, so one presentation layer depends on another. Xenon flags _resolver_vendedor() as rank D and _criar_veiculo() as
     rank C. This is mostly an architecture and maintainability problem, but it also makes tests harder to target.
     Impact: Medium · Category: Architecture and design
     Concrete fix suggestion: Split by area, for example routes/ui/veiculos.py, routes/ui/investidores.py, routes/ui/admin.py, and move shared validation/workflow code
     into a service module rather than importing from routes/json.py.
     Estimated effort: Medium

  6. List/search/export paths load whole tables and sort in Python
     Location: bases/xtreme_system/api/route_factories.py:193, bases/xtreme_system/api/route_factories.py:204, bases/xtreme_system/api/route_factories.py:255, bases/
     xtreme_system/api/routes/ui.py:92, bases/xtreme_system/api/routes/ui.py:221, bases/xtreme_system/api/routes/ui.py:793
     Description: Generic UI CRUD does list_all(), then sorts and filters in memory, and exports all rows with no pagination. The vehicle and sales forms also load full
     client/vehicle lists up front. This is readable today, but performance will degrade linearly with data size and the route layer owns too much query behavior.
     Impact: Medium · Category: Performance
     Concrete fix suggestion: Push sorting, filtering, and pagination into query functions in each component. Have the factory accept list_query(session, q, sort,
     order, limit, offset) instead of always calling list_all().
     Estimated effort: Medium

  7. Investor aggregates and “latest purchase” lookups do extra scans in Python
     Location: components/xtreme_system/caixa/core.py:193, components/xtreme_system/compra/core.py:78, bases/xtreme_system/api/routes/ui.py:228, bases/xtreme_system/
     api/routes/ui.py:798
     Description: agregados_investidores() pulls all vehicles and all cash entries, then loops in Python. latest_by_veiculo_ids() loads all matching purchases and
     deduplicates with setdefault(). These aren’t catastrophic yet, but they are preventable hotspots and they make the UI do more work than necessary on every render/
     export.
     Impact: Medium · Category: Performance
     Concrete fix suggestion: Replace Python aggregation with grouped SQL, and replace latest_by_veiculo_ids() with a window function or subquery that selects only the
     newest purchase per vehicle.
     Estimated effort: Medium

  8. File upload persistence is not atomic and cleanup is opportunistic
     Location: bases/xtreme_system/api/routes/ui.py:373, bases/xtreme_system/api/routes/ui.py:395, bases/xtreme_system/api/routes/ui.py:442, bases/xtreme_system/api/
     routes/ui.py:707
     Description: Files are written first, then DB rows are created, and each DB create commits independently. If a later insert fails, orphan files remain. The reverse
     case is also handled lazily: missing files are only cleaned up when someone opens the modal. This affects correctness, maintainability, and recovery behavior, and
     there are no failure-path tests around it.
     Impact: Medium · Category: Maintainability
     Concrete fix suggestion: Write to a temp path, stage DB rows in one transaction, then rename files after commit. On exception, delete temp files immediately.
     Estimated effort: Medium

  9. Sale creation blocks on a synchronous external WhatsApp call
     Location: bases/xtreme_system/api/routes/json.py:198, bases/xtreme_system/api/routes/ui.py:115, components/xtreme_system/whatsapp/core.py:90
     Description: Both JSON and UI sale creation call whatsapp.notificar_venda() inline after create, and _enviar() can block for up to 10 seconds. That couples user-
     facing latency to an external service. Existing tests mock _enviar(), so the suite never exercises timeout or slow-path behavior.
     Impact: Medium · Category: Performance
     Concrete fix suggestion:

  # minimal
  background_tasks.add_task(whatsapp.notificar_venda, session, venda_obj)

  Better: persist an outbox row and deliver notifications asynchronously.
  Estimated effort: Medium

  10. Operational failures are handled inconsistently: some are double-logged, others are silently swallowed
     Location: bases/xtreme_system/api/setup.py:61, bases/xtreme_system/api/setup.py:177, bases/xtreme_system/api/routes/ui.py:923
     Description: Unhandled exceptions are logged once in _request_context() and again in the global exception handler, which creates noisy duplicate logs. On the other
     side, ui_investidor_criar() catches broad Exception around the initial aporte and returns success even when that part fails. That’s the worst of both worlds for
     ops: too much noise on one path, too little signal on another.
     Impact: Medium · Category: Error handling and logging
     Concrete fix suggestion: Log unhandled exceptions in one place only, and narrow the investor aporte handler to parsing/validation exceptions. For persistence
     failures, either fail the request or make the whole flow transactional.
     Estimated effort: Low
