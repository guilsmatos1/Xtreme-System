"""Factories genéricas de rotas CRUD (API JSON e UI HTMX) reutilizadas por entidade."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    BeforeCreateHook,
    BeforeDeleteHook,
    BeforeUpdateEntityHook,
    BeforeUpdateHook,
    CreateSchemaT,
    CrudModule,
    CsvRow,
    CtxForm,
    CtxList,
    EntityT,
    ListFunc,
    ParseForm,
    QueryFunc,
    ReadSchemaT,
    SearchFunc,
    SearchQueryFunc,
    SortSpec,
    UpdateSchemaT,
)
from xtreme_system.api.crud_ui.query import sort_key
from xtreme_system.api.crud_ui.responses import csv_response
from xtreme_system.api.crud_ui.routes import (
    register_crud_ui_routes as _register_crud_ui_routes_impl,
)
from xtreme_system.api.crud_ui.simple import (
    register_ui_simples as _register_ui_simples_impl,
)
from xtreme_system.api.crud_writes import safe_write as _safe_write
from xtreme_system.api.deps import CurrentUser, SessionDep, _found
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

_sort_key = sort_key
_csv_response = csv_response
DepFactory = Callable[..., usuario.Usuario]


def _require_json_page(user: usuario.Usuario, pagina: str) -> None:
    if not perfil.pode_acessar(user, pagina):
        raise HTTPException(status_code=403, detail="Página não permitida")


def _json_visible(
    obj: Any,
    user: usuario.Usuario,
    pagina: str | None,
    campos: tuple[str, ...],
    read_schema: type[Any],
) -> Any:
    if pagina is None:
        return obj
    _require_json_page(user, pagina)
    data: dict[str, Any] = jsonable_encoder(read_schema.model_validate(obj))
    campos_ocultaveis = {
        campo for campo, _label in perfil.CAMPOS_PROTEGIDOS.get(pagina, [])
    }
    campos_ocultaveis.update(campos)
    for campo in campos_ocultaveis:
        if not perfil.pode_ver_campo(user, pagina, campo):
            data.pop(campo, None)
    return data


def _require_json_operacao(user: usuario.Usuario, pagina: str, operacao: str) -> None:
    if usuario.is_admin(user):
        return
    operacoes = {op for op, _label in perfil.OPERACOES.get(pagina, [])}
    if operacao in operacoes and perfil.pode_operacao(user, pagina, operacao):
        return
    raise HTTPException(status_code=403, detail="Operação não permitida")


def register_crud_routes(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    read_schema: type[ReadSchemaT],
    create_schema: type[CreateSchemaT],
    update_schema: type[UpdateSchemaT],
    before_create: BeforeCreateHook[CreateSchemaT] | None = None,
    before_update: BeforeUpdateEntityHook[EntityT, UpdateSchemaT] | None = None,
    before_delete: BeforeDeleteHook[EntityT] | None = None,
    after_create: AfterWriteHook[EntityT] | None = None,
    after_update: AfterWriteHook[EntityT] | None = None,
    handle_delete_error: bool = True,
    pagina: str | None = None,
    campos_protegidos: tuple[str, ...] = (),
    actor_field: str | None = None,
) -> None:
    response_model = None if pagina else list[read_schema]  # type: ignore[valid-type]

    @app.get(prefix, response_model=response_model)
    def _list(session: SessionDep, user: CurrentUser) -> list[EntityT] | list[Any]:
        if pagina is not None:
            _require_json_page(user, pagina)
        return [
            _json_visible(obj, user, pagina, campos_protegidos, read_schema)
            for obj in module.list_all(session)
        ]

    @app.get(f"{prefix}/{{item_id}}", response_model=None if pagina else read_schema)
    def _get(item_id: int, session: SessionDep, user: CurrentUser) -> EntityT | Any:
        obj = _found(module.get(session, item_id), label)
        return _json_visible(obj, user, pagina, campos_protegidos, read_schema)

    @app.post(
        prefix,
        response_model=None if pagina else read_schema,
        status_code=201,
    )
    def _create(
        data: create_schema,  # type: ignore[valid-type]
        session: SessionDep,
        user: CurrentUser,
    ) -> EntityT | Any:
        if pagina is not None:
            _require_json_operacao(user, pagina, "cadastrar")
        if actor_field:
            setattr(data, actor_field, user.id)
        obj = _create_atomic(data, session, user.id)
        return _json_visible(obj, user, pagina, campos_protegidos, read_schema)

    def _create_atomic(
        data: CreateSchemaT, session: Session, actor_id: int | None
    ) -> EntityT:
        if before_create:
            before_create(session, data)
        obj = _safe_write(
            lambda: module.create(session, data, actor_id),
            conflict_msg=f"{label} já existe",
        )
        if after_create:
            after_create(session, obj, actor_id)
        return obj

    @app.patch(
        f"{prefix}/{{item_id}}",
        response_model=None if pagina else read_schema,
    )
    def _update(
        item_id: int,
        data: update_schema,  # type: ignore[valid-type]
        session: SessionDep,
        user: CurrentUser,
    ) -> EntityT | Any:
        if pagina is not None:
            _require_json_operacao(user, pagina, "editar")
        obj = _update_atomic(item_id, data, session, user.id)
        return _json_visible(obj, user, pagina, campos_protegidos, read_schema)

    def _update_atomic(
        item_id: int, data: UpdateSchemaT, session: Session, actor_id: int | None
    ) -> EntityT:
        obj = _found(module.get(session, item_id), label)
        if before_update:
            before_update(session, obj, data)
        obj = _safe_write(
            lambda: module.update(session, obj, data, actor_id),
            conflict_msg=f"{label} já existe",
        )
        if after_update:
            after_update(session, obj, actor_id)
        return obj

    @app.delete(f"{prefix}/{{item_id}}", status_code=204)
    def _delete(item_id: int, session: SessionDep, user: CurrentUser) -> None:
        if pagina is not None:
            _require_json_operacao(user, pagina, "excluir")
        _delete_atomic(item_id, session, user.id)

    def _delete_atomic(item_id: int, session: Session, actor_id: int | None) -> None:
        obj = _found(module.get(session, item_id), label)
        if before_delete:
            before_delete(session, obj, actor_id)
        if handle_delete_error:
            try:
                module.delete(session, obj, actor_id)
            except IntegrityError:
                raise HTTPException(
                    status_code=409, detail=f"{label} possui veículos vinculados"
                ) from None
        else:
            module.delete(session, obj, actor_id)


def register_ui_simples(
    app: FastAPI,
    templates: Jinja2Templates,
    ui_prefix: str,
    titulo: str,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    create_schema: type[CreateSchemaT],
    update_schema: type[UpdateSchemaT],
    export_filename: str,
) -> None:
    _register_ui_simples_impl(
        app,
        templates,
        ui_prefix,
        titulo,
        module,
        create_schema,
        update_schema,
        export_filename,
    )


def register_crud_ui_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    create_schema: type[CreateSchemaT],
    update_schema: type[UpdateSchemaT],
    list_key: str,
    item_key: str,
    list_template: str,
    list_partial_template: str,
    ok_partial_template: str,
    form_template: str,
    sort_fields: dict[str, SortSpec[EntityT]],
    ctx_form: CtxForm = lambda _session: {},
    ctx_list: CtxList[EntityT] = lambda _session, _lista: {},
    searchable: bool = False,
    parse_form: ParseForm = dict,
    before_create: BeforeCreateHook[CreateSchemaT] | None = None,
    before_update: BeforeUpdateHook[UpdateSchemaT] | None = None,
    before_delete: BeforeDeleteHook[EntityT] | None = None,
    after_create: AfterWriteHook[EntityT] | None = None,
    after_update: AfterWriteHook[EntityT] | None = None,
    csv_filename: str,
    csv_headers: list[str],
    csv_row: CsvRow[EntityT],
    csv_fields: list[str | None] | None = None,
    delete_requires_admin: bool = True,
    register_create: bool = True,
    register_update: bool = True,
    register_edit: bool = True,
    register_delete: bool = True,
    editar_dep: DepFactory | None = None,
    excluir_dep: DepFactory | None = None,
    cadastrar_dep: DepFactory | None = None,
    pagina: str | None = None,
    campos_form_map: dict[str, str] | None = None,
    list_func: ListFunc[EntityT] | None = None,
    search_func: SearchFunc[EntityT] | None = None,
    sql_sort_fields: dict[str, object] | None = None,
    query_func: QueryFunc[EntityT] | None = None,
    search_query_func: SearchQueryFunc[EntityT] | None = None,
) -> None:
    _register_crud_ui_routes_impl(
        app,
        templates,
        module,
        prefix,
        label,
        create_schema=create_schema,
        update_schema=update_schema,
        list_key=list_key,
        item_key=item_key,
        list_template=list_template,
        list_partial_template=list_partial_template,
        ok_partial_template=ok_partial_template,
        form_template=form_template,
        sort_fields=sort_fields,
        ctx_form=ctx_form,
        ctx_list=ctx_list,
        searchable=searchable,
        parse_form=parse_form,
        before_create=before_create,
        before_update=before_update,
        before_delete=before_delete,
        after_create=after_create,
        after_update=after_update,
        csv_filename=csv_filename,
        csv_headers=csv_headers,
        csv_row=csv_row,
        csv_fields=csv_fields,
        delete_requires_admin=delete_requires_admin,
        register_create=register_create,
        register_update=register_update,
        register_edit=register_edit,
        register_delete=register_delete,
        editar_dep=editar_dep,
        excluir_dep=excluir_dep,
        cadastrar_dep=cadastrar_dep,
        pagina=pagina,
        campos_form_map=campos_form_map,
        list_func=list_func,
        search_func=search_func,
        sql_sort_fields=sql_sort_fields,
        query_func=query_func,
        search_query_func=search_query_func,
    )
