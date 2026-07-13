"""Factories genéricas de rotas CRUD (API JSON e UI HTMX) reutilizadas por entidade."""

import csv
import io
from collections.abc import Callable
from typing import Annotated, Any, Protocol, cast

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    AdminUser,
    CurrentUser,
    SessionDep,
    UIAdmin,
    UIUser,
    _found,
    get_ui_user,
    require_ui_admin,
)
from xtreme_system.crud import core as crud
from xtreme_system.usuario import core as usuario


class CrudModule(Protocol):
    """Shape um módulo de entidade precisa ter para usar as factories abaixo.

    Módulos (não instâncias) casam estruturalmente com este Protocol: cada
    entidade expõe list_all/get/create/update/delete como funções soltas.
    """

    def list_all(self, session: Session, /) -> list[Any]: ...
    def get(self, session: Session, item_id: int, /) -> Any | None: ...
    def create(self, session: Session, data: Any, /) -> Any: ...
    def update(self, session: Session, obj: Any, data: Any, /) -> Any: ...
    def delete(self, session: Session, obj: Any, /) -> None: ...


class SearchableCrudModule(CrudModule, Protocol):
    def search(self, session: Session, term: str, /) -> list[Any]: ...


def _safe_write(session: Session, op: Callable[[], Any], *, conflict_msg: str) -> Any:
    try:
        return op()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict_msg) from None


def _atomic_write(session: Session, op: Callable[[], Any]) -> Any:
    previous = session.info.get(crud.DEFER_COMMIT_KEY)
    session.info[crud.DEFER_COMMIT_KEY] = True
    try:
        result = op()
        session.commit()
    except Exception:
        session.rollback()
        raise
    else:
        return result
    finally:
        if previous is None:
            session.info.pop(crud.DEFER_COMMIT_KEY, None)
        else:
            session.info[crud.DEFER_COMMIT_KEY] = previous


def _create_with_hook(
    module: CrudModule,
    session: Session,
    data: Any,
    after_create: Callable[[Session, Any], Any] | None,
) -> Any:
    obj = module.create(session, data)
    _run_hook(after_create, session, obj)
    return obj


def _update_with_hook(
    module: CrudModule,
    session: Session,
    obj: Any,
    data: Any,
    after_update: Callable[[Session, Any], Any] | None,
) -> Any:
    atualizado = module.update(session, obj, data)
    _run_hook(after_update, session, atualizado)
    return atualizado


def _delete_with_hook(
    module: CrudModule,
    session: Session,
    obj: Any,
    before_delete: Callable[[Session, Any], None] | None,
) -> None:
    _run_hook(before_delete, session, obj)
    module.delete(session, obj)


def _csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def register_crud_routes(
    app: FastAPI,
    module: CrudModule,
    prefix: str,
    label: str,
    *,
    read_schema: type,
    create_schema: type,
    update_schema: type,
    before_create: Callable[[Session, Any], None] | None = None,
    before_update: Callable[[Session, Any, Any], None] | None = None,
    before_delete: Callable[[Session, Any], None] | None = None,
    after_create: Callable[[Session, Any], Any] | None = None,
    after_update: Callable[[Session, Any], Any] | None = None,
    handle_delete_error: bool = True,
) -> None:
    @app.get(prefix, response_model=list[read_schema])  # type: ignore[valid-type]
    def _list(session: SessionDep, _: CurrentUser) -> Any:
        return module.list_all(session)

    @app.get(f"{prefix}/{{item_id}}", response_model=read_schema)
    def _get(item_id: int, session: SessionDep, _: CurrentUser) -> Any:
        return _found(module.get(session, item_id), label)

    @app.post(prefix, response_model=read_schema, status_code=201)
    def _create(data: create_schema, session: SessionDep, user: AdminUser) -> Any:  # type: ignore[valid-type]
        session.info["usuario_id"] = user.id
        return _atomic_write(
            session,
            lambda: _create_atomic(data, session),
        )

    def _create_atomic(data: Any, session: Session) -> Any:
        if before_create:
            before_create(session, data)
        obj = _safe_write(
            session,
            lambda: module.create(session, data),
            conflict_msg=f"{label} já existe",
        )
        if after_create:
            after_create(session, obj)
        return obj

    @app.patch(f"{prefix}/{{item_id}}", response_model=read_schema)
    def _update(
        item_id: int,
        data: update_schema,  # type: ignore[valid-type]
        session: SessionDep,
        user: AdminUser,
    ) -> Any:
        session.info["usuario_id"] = user.id
        return _atomic_write(
            session,
            lambda: _update_atomic(item_id, data, session),
        )

    def _update_atomic(item_id: int, data: Any, session: Session) -> Any:
        obj = _found(module.get(session, item_id), label)
        if before_update:
            before_update(session, obj, data)
        obj = _safe_write(
            session,
            lambda: module.update(session, obj, data),
            conflict_msg=f"{label} já existe",
        )
        if after_update:
            after_update(session, obj)
        return obj

    @app.delete(f"{prefix}/{{item_id}}", status_code=204)
    def _delete(item_id: int, session: SessionDep, user: AdminUser) -> None:
        session.info["usuario_id"] = user.id
        _atomic_write(session, lambda: _delete_atomic(item_id, session))

    def _delete_atomic(item_id: int, session: Session) -> None:
        obj = _found(module.get(session, item_id), label)
        if before_delete:
            before_delete(session, obj)
        if handle_delete_error:
            try:
                module.delete(session, obj)
            except IntegrityError:
                session.rollback()
                raise HTTPException(
                    status_code=409, detail=f"{label} possui veículos vinculados"
                ) from None
        else:
            module.delete(session, obj)


# ponytail: in-memory sort; DB-level only if row counts grow large.
def _sort_key(val: Any) -> Any:
    if val is None:
        return ""  # ponytail: None sorts before all strings; DB constraint if needed.
    val = getattr(val, "value", val)  # enums compare by .value
    if hasattr(val, "nome"):
        val = val.nome
    return val.lower() if isinstance(val, str) else val


def _run_hook(
    hook: Callable[[Session, Any], None] | None, session: Session, arg: Any
) -> None:
    if hook:
        hook(session, arg)


def _conflict_form_response(
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    ctx: dict[str, Any],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        form_template,
        ctx,
        status_code=409,
    )


def _write_conflict_detail(label: str) -> str:
    return f"{label} já existe"


def _delete_conflict_detail(label: str) -> str:
    return f"{label} possui registros vinculados"


def register_crud_ui_routes(  # noqa: PLR0915
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule,
    prefix: str,
    label: str,
    *,
    create_schema: type,
    update_schema: type,
    list_key: str,
    item_key: str,
    list_template: str,
    list_partial_template: str,
    ok_partial_template: str,
    form_template: str,
    sort_fields: dict[str, str | Callable[[Any], Any]],
    ctx_form: Callable[[Session], dict[str, Any]] = lambda _session: {},
    ctx_list: Callable[[Session, list[Any]], dict[str, Any]] = (
        lambda _session, _lista: {}
    ),
    searchable: bool = False,
    parse_form: Callable[[Any], dict[str, Any]] = dict,
    before_create: Callable[[Session, Any], None] | None = None,
    before_update: Callable[[Session, Any], None] | None = None,
    before_delete: Callable[[Session, Any], None] | None = None,
    after_create: Callable[[Session, Any], Any] | None = None,
    after_update: Callable[[Session, Any], Any] | None = None,
    csv_filename: str,
    csv_headers: list[str],
    csv_row: Callable[[Any], list[Any]],
    delete_requires_admin: bool = True,
    register_create: bool = True,
    register_update: bool = True,
) -> None:
    def _query(session: Session, q: str) -> list[Any]:
        if searchable and q:
            # searchable=True is the caller's promise that module has search.
            return list(cast(SearchableCrudModule, module).search(session, q))
        return list(module.list_all(session))

    def _sort_key_fn(spec: str | Callable[[Any], Any]) -> Callable[[Any], Any]:
        if callable(spec):
            return spec
        return lambda obj: _sort_key(getattr(obj, spec))

    def _sorted(lista: list[Any], sort: str, order: str) -> list[Any]:
        spec = sort_fields.get(sort)
        if spec is None:
            return lista
        return sorted(lista, key=_sort_key_fn(spec), reverse=order == "desc")

    def _ok(request: Request, session: Session, user: usuario.Usuario) -> HTMLResponse:
        lista = module.list_all(session)
        return templates.TemplateResponse(
            request,
            ok_partial_template,
            {"user": user, list_key: lista, **ctx_list(session, lista)},
        )

    def _erro(
        request: Request,
        session: Session,
        exc: ValidationError | HTTPException,
        obj: Any | None,
        status_code: int = 400,
    ) -> HTMLResponse:
        erro = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return templates.TemplateResponse(
            request,
            form_template,
            {**ctx_form(session), item_key: obj, "erro": erro},
            status_code=status_code,
        )

    @app.get(prefix)
    def _list(
        request: Request,
        session: SessionDep,
        user: UIUser,
        q: str = "",
        sort: str = "",
        order: str = "asc",
    ) -> HTMLResponse:
        lista = _sorted(_query(session, q), sort, order)
        ctx: dict[str, Any] = {
            "user": user,
            list_key: lista,
            "sort": sort,
            "order": order,
            **ctx_list(session, lista),
        }
        if searchable:
            ctx["q"] = q
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(request, list_partial_template, ctx)
        return templates.TemplateResponse(request, list_template, ctx)

    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, _: UIUser, q: str = "") -> Response:
        lista = _query(session, q)
        return _csv_response(csv_filename, csv_headers, [csv_row(obj) for obj in lista])

    @app.get(f"{prefix}/novo")
    def _novo(request: Request, session: SessionDep, _: UIAdmin) -> HTMLResponse:
        return templates.TemplateResponse(
            request, form_template, {**ctx_form(session), item_key: None}
        )

    @app.get(f"{prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int, request: Request, session: SessionDep, _: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        return templates.TemplateResponse(
            request, form_template, {**ctx_form(session), item_key: obj}
        )

    if register_create:

        @app.post(prefix)
        async def _criar(
            request: Request, session: SessionDep, user: UIAdmin
        ) -> HTMLResponse:
            session.info["usuario_id"] = user.id
            form = await request.form()
            try:
                data = create_schema.model_validate(parse_form(form))  # type: ignore[attr-defined]
                _run_hook(before_create, session, data)
            except (ValidationError, HTTPException) as exc:
                return _erro(request, session, exc, None)
            try:
                _atomic_write(
                    session,
                    lambda: _create_with_hook(module, session, data, after_create),
                )
            except IntegrityError:
                return _conflict_form_response(
                    templates,
                    request,
                    form_template,
                    {
                        **ctx_form(session),
                        item_key: None,
                        "erro": _write_conflict_detail(label),
                    },
                )
            return _ok(request, session, user)

    if register_update:

        @app.post(f"{prefix}/{{item_id}}")
        async def _atualizar(
            item_id: int, request: Request, session: SessionDep, user: UIAdmin
        ) -> HTMLResponse:
            session.info["usuario_id"] = user.id
            obj = _found(module.get(session, item_id), label)
            form = await request.form()
            try:
                data = update_schema.model_validate(parse_form(form))  # type: ignore[attr-defined]
                _run_hook(before_update, session, data)
            except (ValidationError, HTTPException) as exc:
                return _erro(request, session, exc, obj)
            try:
                _atomic_write(
                    session,
                    lambda: _update_with_hook(module, session, obj, data, after_update),
                )
            except IntegrityError:
                return _conflict_form_response(
                    templates,
                    request,
                    form_template,
                    {
                        **ctx_form(session),
                        item_key: obj,
                        "erro": _write_conflict_detail(label),
                    },
                )
            return _ok(request, session, user)

    excluir_dep = require_ui_admin if delete_requires_admin else get_ui_user

    @app.post(f"{prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(excluir_dep)],
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        obj = _found(module.get(session, item_id), label)
        erro = None
        status_code = 200
        try:
            _atomic_write(
                session,
                lambda: _delete_with_hook(module, session, obj, before_delete),
            )
        except IntegrityError:
            erro = _delete_conflict_detail(label)
            status_code = 409
        lista = module.list_all(session)
        return templates.TemplateResponse(
            request,
            list_partial_template,
            {
                "user": user,
                list_key: lista,
                "erro": erro,
                **ctx_list(session, lista),
            },
            status_code=status_code,
        )


def register_ui_simples(
    app: FastAPI,
    templates: Jinja2Templates,
    ui_prefix: str,
    titulo: str,
    module: CrudModule,
    create_schema: type,
    update_schema: type,
    export_filename: str,
) -> None:
    def _ctx(
        user: usuario.Usuario,
        session: Session,
        sort: str = "",
        order: str = "asc",
        **extra: Any,
    ) -> dict[str, Any]:
        itens = module.list_all(session)
        if sort == "nome":
            itens = sorted(
                itens, key=lambda i: _sort_key(i.nome), reverse=order == "desc"
            )
        return {
            "user": user,
            "titulo": titulo,
            "prefixo": ui_prefix,
            "itens": itens,
            "sort": sort,
            "order": order,
            **extra,
        }

    def _form_ctx(item: Any, erro: str | None = None) -> dict[str, Any]:
        return {"titulo": titulo, "prefixo": ui_prefix, "item": item, "erro": erro}

    async def _nome(request: Request) -> str:
        return str((await request.form()).get("nome") or "").strip()

    @app.get(ui_prefix)
    def _lista(
        request: Request,
        session: SessionDep,
        user: UIUser,
        sort: str = "",
        order: str = "asc",
    ) -> HTMLResponse:
        ctx = _ctx(user, session, sort, order)
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(request, "_linhas_simples.html", ctx)
        return templates.TemplateResponse(request, "simples.html", ctx)

    @app.get(f"{ui_prefix}/exportar")
    def _exportar(session: SessionDep, _: UIUser) -> Response:
        itens = module.list_all(session)
        return _csv_response(
            export_filename,
            ["ID", "Nome"],
            [[item.id, item.nome] for item in itens],
        )

    @app.get(f"{ui_prefix}/novo")
    def _novo(request: Request, _: UIAdmin) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "_form_simples.html", _form_ctx(None)
        )

    @app.get(f"{ui_prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int, request: Request, session: SessionDep, _: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        return templates.TemplateResponse(request, "_form_simples.html", _form_ctx(obj))

    @app.post(ui_prefix)
    async def _criar(
        request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(None, "Nome obrigatório"),
                status_code=400,
            )
        try:
            module.create(session, create_schema(nome=nome))
        except IntegrityError:
            session.rollback()
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(None, f"{titulo} já existe"),
                status_code=409,
            )
        return templates.TemplateResponse(
            request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        obj = _found(module.get(session, item_id), titulo)
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(obj, "Nome obrigatório"),
                status_code=400,
            )
        try:
            module.update(session, obj, update_schema(nome=nome))
        except IntegrityError:
            session.rollback()
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(obj, f"{titulo} já existe"),
                status_code=409,
            )
        return templates.TemplateResponse(
            request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        obj = _found(module.get(session, item_id), titulo)
        msg = None
        try:
            module.delete(session, obj)
        except IntegrityError:
            session.rollback()
            msg = f"{titulo} possui veículos vinculados"
        return templates.TemplateResponse(
            request, "_linhas_simples.html", _ctx(user, session, msg=msg)
        )
