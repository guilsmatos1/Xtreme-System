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
