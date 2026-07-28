from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import parse_qs, urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    BeforeCreateHook,
    BeforeDeleteHook,
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
    SearchFunc,
    SearchQueryFunc,
    SortSpec,
    UpdateSchemaT,
)
from xtreme_system.api.crud_ui.query import query_list, sorted_list
from xtreme_system.api.crud_ui.responses import (
    conflict_form_response,
    csv_response,
    delete_conflict_detail,
    error_response,
    form_response,
    list_response,
    ok_response,
    rollback_integrity_error_response,
    write_conflict_detail,
)
from xtreme_system.api.crud_writes import (
    create_with_hook,
    delete_with_hook,
    run_hook,
    safe_write,
    update_with_hook,
)
from xtreme_system.api.deps import (
    SessionDep,
    UIUser,
    _found,
    get_ui_user,
    require_ui_admin,
)
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

DepFactory = Callable[..., usuario.Usuario]
LIST_LIMIT_MAX = 200


@dataclass(frozen=True)
class ListState:
    q: str = ""
    sort: str = ""
    order: str = "asc"
    search_column: str = ""
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class CrudUIResourceConfig[CreateSchemaT: BaseModel, UpdateSchemaT: BaseModel]:
    label: str
    create_schema: type[CreateSchemaT]
    update_schema: type[UpdateSchemaT]
    list_key: str
    item_key: str


@dataclass(frozen=True)
class CrudUITemplateConfig:
    list_template: str
    list_partial_template: str
    ok_partial_template: str
    form_template: str


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class CrudUIBehaviorConfig[EntityT, CreateSchemaT: BaseModel, UpdateSchemaT: BaseModel]:
    ctx_form: CtxForm = lambda _session: {}
    ctx_list: CtxList[EntityT] = lambda _session, _lista: {}
    parse_form: ParseForm = dict
    before_create: BeforeCreateHook[CreateSchemaT] | None = None
    before_update: BeforeUpdateHook[UpdateSchemaT] | None = None
    before_delete: BeforeDeleteHook[EntityT] | None = None
    after_create: AfterWriteHook[EntityT] | None = None
    after_update: AfterWriteHook[EntityT] | None = None


@dataclass(frozen=True)
class CrudUIListConfig[EntityT]:
    sort_fields: dict[str, SortSpec[EntityT]]
    searchable: bool = False
    list_func: ListFunc[EntityT] | None = None
    search_func: SearchFunc[EntityT] | None = None
    sql_sort_fields: dict[str, object] | None = None
    query_func: QueryFunc[EntityT] | None = None
    search_query_func: SearchQueryFunc[EntityT] | None = None


@dataclass(frozen=True)
class CrudUIExportConfig[EntityT]:
    csv_filename: str
    csv_headers: list[str]
    csv_row: CsvRow[EntityT]
    csv_fields: list[str | None] | None = None
    pagina: str | None = None


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class CrudUIRouteConfig:
    register_create: bool = True
    register_update: bool = True
    register_edit: bool = True
    register_delete: bool = True
    delete_requires_admin: bool = True
    editar_dep: DepFactory | None = None
    excluir_dep: DepFactory | None = None
    cadastrar_dep: DepFactory | None = None


def _bounded_int(
    value: str | None, *, default: int, min_value: int, max_value: int
) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return min(max(parsed, min_value), max_value)


def _current_list_state(request: Request) -> ListState:
    current_url = request.headers.get("HX-Current-URL")
    if current_url:
        query_params = {
            key: values[-1]
            for key, values in parse_qs(
                urlsplit(current_url).query, keep_blank_values=True
            ).items()
        }
    else:
        query_params = dict(request.query_params)

    return ListState(
        q=query_params.get("q", ""),
        sort=query_params.get("sort", ""),
        order=query_params.get("order", "asc"),
        search_column=query_params.get("search_column", ""),
        limit=_bounded_int(
            query_params.get("limit"),
            default=50,
            min_value=1,
            max_value=LIST_LIMIT_MAX,
        ),
        offset=_bounded_int(
            query_params.get("offset"),
            default=0,
            min_value=0,
            max_value=10**9,
        ),
    )


# pylint: disable=too-many-branches
def register_crud_ui_routes(  # noqa: PLR0912
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *legacy_args: str,
    resource: CrudUIResourceConfig[Any, Any] | None = None,
    templates_config: CrudUITemplateConfig | None = None,
    behavior: CrudUIBehaviorConfig[Any, Any, Any] | None = None,
    listing: CrudUIListConfig[Any] | None = None,
    export: CrudUIExportConfig[Any] | None = None,
    routes: CrudUIRouteConfig | None = None,
    **legacy: Any,
) -> None:
    if legacy_args:
        if len(legacy_args) != 1 or "label" in legacy:
            raise TypeError
        legacy["label"] = legacy_args[0]
    if resource is None:
        resource = CrudUIResourceConfig(
            label=legacy.pop("label"),
            create_schema=legacy.pop("create_schema"),
            update_schema=legacy.pop("update_schema"),
            list_key=legacy.pop("list_key"),
            item_key=legacy.pop("item_key"),
        )
    if templates_config is None:
        templates_config = CrudUITemplateConfig(
            list_template=legacy.pop("list_template"),
            list_partial_template=legacy.pop("list_partial_template"),
            ok_partial_template=legacy.pop("ok_partial_template"),
            form_template=legacy.pop("form_template"),
        )
    if behavior is None:
        behavior = CrudUIBehaviorConfig(
            ctx_form=legacy.pop("ctx_form", lambda _session: {}),
            ctx_list=legacy.pop("ctx_list", lambda _session, _lista: {}),
            parse_form=legacy.pop("parse_form", dict),
            before_create=legacy.pop("before_create", None),
            before_update=legacy.pop("before_update", None),
            before_delete=legacy.pop("before_delete", None),
            after_create=legacy.pop("after_create", None),
            after_update=legacy.pop("after_update", None),
        )
    if listing is None:
        listing = CrudUIListConfig(
            sort_fields=legacy.pop("sort_fields"),
            searchable=legacy.pop("searchable", False),
            list_func=legacy.pop("list_func", None),
            search_func=legacy.pop("search_func", None),
            sql_sort_fields=legacy.pop("sql_sort_fields", None),
            query_func=legacy.pop("query_func", None),
            search_query_func=legacy.pop("search_query_func", None),
        )
    if export is None:
        export = CrudUIExportConfig(
            csv_filename=legacy.pop("csv_filename"),
            csv_headers=legacy.pop("csv_headers"),
            csv_row=legacy.pop("csv_row"),
            csv_fields=legacy.pop("csv_fields", None),
            pagina=legacy.pop("pagina", None),
        )
    if routes is None:
        routes = CrudUIRouteConfig(
            register_create=legacy.pop("register_create", True),
            register_update=legacy.pop("register_update", True),
            register_edit=legacy.pop("register_edit", True),
            register_delete=legacy.pop("register_delete", True),
            delete_requires_admin=legacy.pop("delete_requires_admin", True),
            editar_dep=legacy.pop("editar_dep", None),
            excluir_dep=legacy.pop("excluir_dep", None),
            cadastrar_dep=legacy.pop("cadastrar_dep", None),
        )
    if legacy:
        raise TypeError
    register_list_route(
        app,
        templates,
        module,
        prefix,
        list_key=resource.list_key,
        list_template=templates_config.list_template,
        list_partial_template=templates_config.list_partial_template,
        sort_fields=listing.sort_fields,
        ctx_list=behavior.ctx_list,
        searchable=listing.searchable,
        list_func=listing.list_func,
        search_func=listing.search_func,
        sql_sort_fields=listing.sql_sort_fields,
        query_func=listing.query_func,
        search_query_func=listing.search_query_func,
    )
    register_export_route(
        app,
        module,
        prefix,
        searchable=listing.searchable,
        list_func=listing.list_func,
        search_func=listing.search_func,
        query_func=listing.query_func,
        search_query_func=listing.search_query_func,
        csv_filename=export.csv_filename,
        csv_headers=export.csv_headers,
        csv_row=export.csv_row,
        csv_fields=export.csv_fields,
        pagina=export.pagina,
    )
    register_new_route(
        app,
        templates,
        prefix,
        form_template=templates_config.form_template,
        ctx_form=behavior.ctx_form,
        item_key=resource.item_key,
        cadastrar_dep=routes.cadastrar_dep,
    )
    if routes.register_edit:
        register_edit_route(
            app,
            templates,
            module,
            prefix,
            resource.label,
            form_template=templates_config.form_template,
            ctx_form=behavior.ctx_form,
            item_key=resource.item_key,
            editar_dep=routes.editar_dep,
        )
    if routes.register_create:
        register_create_route(
            app,
            templates,
            module,
            prefix,
            resource.label,
            create_schema=resource.create_schema,
            list_key=resource.list_key,
            item_key=resource.item_key,
            form_template=templates_config.form_template,
            ok_partial_template=templates_config.ok_partial_template,
            ctx_form=behavior.ctx_form,
            ctx_list=behavior.ctx_list,
            parse_form=behavior.parse_form,
            before_create=behavior.before_create,
            after_create=behavior.after_create,
            searchable=listing.searchable,
            list_func=listing.list_func,
            search_func=listing.search_func,
            sort_fields=listing.sort_fields,
            sql_sort_fields=listing.sql_sort_fields,
            query_func=listing.query_func,
            search_query_func=listing.search_query_func,
            cadastrar_dep=routes.cadastrar_dep,
        )
    if routes.register_update:
        register_update_route(
            app,
            templates,
            module,
            prefix,
            resource.label,
            update_schema=resource.update_schema,
            list_key=resource.list_key,
            item_key=resource.item_key,
            form_template=templates_config.form_template,
            ok_partial_template=templates_config.ok_partial_template,
            ctx_form=behavior.ctx_form,
            ctx_list=behavior.ctx_list,
            parse_form=behavior.parse_form,
            before_update=behavior.before_update,
            after_update=behavior.after_update,
            searchable=listing.searchable,
            list_func=listing.list_func,
            search_func=listing.search_func,
            sort_fields=listing.sort_fields,
            sql_sort_fields=listing.sql_sort_fields,
            query_func=listing.query_func,
            search_query_func=listing.search_query_func,
            editar_dep=routes.editar_dep,
            pagina=export.pagina,
        )
    if routes.register_delete:
        register_delete_route(
            app,
            templates,
            module,
            prefix,
            resource.label,
            list_key=resource.list_key,
            list_partial_template=templates_config.list_partial_template,
            ctx_list=behavior.ctx_list,
            before_delete=behavior.before_delete,
            delete_requires_admin=routes.delete_requires_admin,
            searchable=listing.searchable,
            list_func=listing.list_func,
            search_func=listing.search_func,
            sort_fields=listing.sort_fields,
            sql_sort_fields=listing.sql_sort_fields,
            query_func=listing.query_func,
            search_query_func=listing.search_query_func,
            excluir_dep=routes.excluir_dep,
        )


def register_list_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    list_key: str,
    list_template: str,
    list_partial_template: str,
    sort_fields: dict[str, SortSpec[EntityT]],
    ctx_list: CtxList[EntityT],
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    sql_sort_fields: dict[str, object] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
) -> None:
    @app.get(prefix)
    def _list(
        request: Request,
        session: SessionDep,
        user: UIUser,
        q: str = "",
        sort: str = "",
        order: str = "asc",
        search_column: str = "",
        limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> HTMLResponse:
        lista = sorted_list(
            query_list(
                session,
                module,
                q=q,
                searchable=searchable,
                list_func=list_func,
                search_func=search_func,
                search_column=search_column or None,
                limit=limit,
                offset=offset,
                sort=sort,
                order=order,
                sort_fields=sort_fields,
                sql_sort_fields=sql_sort_fields,
                query_func=query_func,
                search_query_func=search_query_func,
            ),
            sort,
            order,
            {} if sql_sort_fields is not None else sort_fields,
        )
        template = (
            list_partial_template
            if request.headers.get("HX-Request")
            else list_template
        )
        return list_response(
            templates,
            request,
            template,
            user=user,
            list_key=list_key,
            lista=lista,
            ctx_list=ctx_list(session, lista),
            sort=sort,
            order=order,
            q=q if searchable else None,
            search_column=search_column,
            limit=limit,
            offset=offset,
        )


def register_export_route(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
    csv_filename: str,
    csv_headers: list[str],
    csv_row: CsvRow[EntityT],
    csv_fields: list[str | None] | None = None,
    pagina: str | None = None,
) -> None:
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, user: UIUser, q: str = "") -> Response:
        lista = query_list(
            session,
            module,
            q=q,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
            query_func=query_func,
            search_query_func=search_query_func,
        )
        headers = csv_headers
        rows = [csv_row(obj) for obj in lista]
        if pagina and csv_fields:
            indices = [
                idx
                for idx, campo in enumerate(csv_fields)
                if campo is None or perfil.pode_ver_campo(user, pagina, campo)
            ]
            headers = [headers[idx] for idx in indices]
            rows = [[row[idx] for idx in indices] for row in rows]
        return csv_response(csv_filename, headers, rows)


def register_new_route(
    app: FastAPI,
    templates: Jinja2Templates,
    prefix: str,
    *,
    form_template: str,
    ctx_form: CtxForm,
    item_key: str,
    cadastrar_dep: DepFactory | None = None,
) -> None:
    dep = cadastrar_dep or require_ui_admin

    @app.get(f"{prefix}/novo")
    def _novo(
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        return form_response(
            templates,
            request,
            form_template,
            ctx_form=ctx_form(session),
            item_key=item_key,
            item=None,
            user=user,
        )


def register_edit_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    form_template: str,
    ctx_form: CtxForm,
    item_key: str,
    editar_dep: DepFactory | None = None,
) -> None:
    dep = editar_dep or require_ui_admin

    @app.get(f"{prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        return form_response(
            templates,
            request,
            form_template,
            ctx_form=ctx_form(session),
            item_key=item_key,
            item=obj,
            user=user,
        )


def write_conflict_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    *,
    ctx_form: CtxForm,
    item_key: str,
    item: object,
    user: usuario.Usuario,
    erro: str,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return rollback_integrity_error_response(
        session,
        lambda: conflict_form_response(
            templates,
            request,
            form_template,
            ctx_form=ctx_form(session),
            item_key=item_key,
            item=item,
            user=user,
            erro=erro,
            dados=dados,
        ),
    )


def write_ok_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    ok_partial_template: str,
    *,
    user: usuario.Usuario,
    list_key: str,
    ctx_list: CtxList[EntityT],
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    sort_fields: dict[str, SortSpec[EntityT]],
    sql_sort_fields: dict[str, object] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
) -> HTMLResponse:
    state = _current_list_state(request)
    lista = sorted_list(
        query_list(
            session,
            module,
            q=state.q,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
            search_column=state.search_column or None,
            limit=state.limit,
            offset=state.offset,
            sort=state.sort,
            order=state.order,
            sort_fields=sort_fields,
            sql_sort_fields=sql_sort_fields,
            query_func=query_func,
            search_query_func=search_query_func,
        ),
        state.sort,
        state.order,
        {} if sql_sort_fields is not None else sort_fields,
    )
    return ok_response(
        templates,
        request,
        ok_partial_template,
        user=user,
        list_key=list_key,
        lista=lista,
        ctx_list=ctx_list(session, lista),
    )


def register_create_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    create_schema: type[CreateSchemaT],
    list_key: str,
    item_key: str,
    form_template: str,
    ok_partial_template: str,
    ctx_form: CtxForm,
    ctx_list: CtxList[EntityT],
    parse_form: ParseForm,
    before_create: BeforeCreateHook[CreateSchemaT] | None,
    after_create: AfterWriteHook[EntityT] | None,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    sort_fields: dict[str, SortSpec[EntityT]],
    sql_sort_fields: dict[str, object] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
    cadastrar_dep: DepFactory | None = None,
) -> None:
    dep = cadastrar_dep or require_ui_admin

    @app.post(prefix)
    async def _criar(
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        form = await request.form()
        dados_form = parse_form(form)
        try:
            data = create_schema.model_validate(dados_form)
        except ValidationError:
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=None,
                user=user,
                erro="Dados inválidos",
                status_code=400,
                dados=dados_form,
            )
        try:
            safe_write(
                lambda: create_with_hook(
                    module,
                    session,
                    data,
                    after_create,
                    user.id,
                    before_create=before_create,
                ),
                conflict_msg=write_conflict_detail(label),
            )
        except HTTPException as exc:
            erro = str(exc.detail)
            if exc.status_code == status.HTTP_409_CONFLICT:
                return write_conflict_response(
                    session,
                    templates,
                    request,
                    form_template,
                    ctx_form=ctx_form,
                    item_key=item_key,
                    item=data,
                    user=user,
                    erro=erro,
                    dados=dados_form,
                )
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=None,
                user=user,
                erro=erro,
                status_code=400,
                dados=dados_form,
            )
        return write_ok_response(
            session,
            templates,
            request,
            module,
            ok_partial_template,
            user=user,
            list_key=list_key,
            ctx_list=ctx_list,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
            sort_fields=sort_fields,
            sql_sort_fields=sql_sort_fields,
            query_func=query_func,
            search_query_func=search_query_func,
        )


def register_update_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    update_schema: type[UpdateSchemaT],
    list_key: str,
    item_key: str,
    form_template: str,
    ok_partial_template: str,
    ctx_form: CtxForm,
    ctx_list: CtxList[EntityT],
    parse_form: ParseForm,
    before_update: BeforeUpdateHook[UpdateSchemaT] | None,
    after_update: AfterWriteHook[EntityT] | None,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    sort_fields: dict[str, SortSpec[EntityT]],
    sql_sort_fields: dict[str, object] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
    editar_dep: DepFactory | None = None,
    pagina: str | None = None,
) -> None:
    dep = editar_dep or require_ui_admin

    @app.post(f"{prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        form = await request.form()
        dados_form = parse_form(form)
        perfil.filtrar_campos_form_ocultos(user, pagina, dados_form)
        try:
            data = update_schema.model_validate(dados_form)
            run_hook(before_update, session, data)
        except ValidationError:
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=obj,
                user=user,
                erro="Dados inválidos",
                status_code=400,
            )
        except HTTPException as exc:
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=obj,
                user=user,
                erro=str(exc.detail),
                status_code=400,
            )
        try:
            safe_write(
                lambda: update_with_hook(
                    module, session, obj, data, after_update, user.id
                ),
                conflict_msg=write_conflict_detail(label),
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_409_CONFLICT:
                raise
            erro = str(exc.detail)
            return write_conflict_response(
                session,
                templates,
                request,
                form_template,
                ctx_form=ctx_form,
                item_key=item_key,
                item=obj,
                user=user,
                erro=erro,
            )
        return write_ok_response(
            session,
            templates,
            request,
            module,
            ok_partial_template,
            user=user,
            list_key=list_key,
            ctx_list=ctx_list,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
            sort_fields=sort_fields,
            sql_sort_fields=sql_sort_fields,
            query_func=query_func,
            search_query_func=search_query_func,
        )


def register_delete_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    list_key: str,
    list_partial_template: str,
    ctx_list: CtxList[EntityT],
    before_delete: BeforeDeleteHook[EntityT] | None,
    delete_requires_admin: bool,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    sort_fields: dict[str, SortSpec[EntityT]],
    sql_sort_fields: dict[str, object] | None,
    query_func: QueryFunc[EntityT] | None,
    search_query_func: SearchQueryFunc[EntityT] | None,
    excluir_dep: DepFactory | None = None,
) -> None:
    dep = excluir_dep or (require_ui_admin if delete_requires_admin else get_ui_user)

    @app.post(f"{prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        try:
            delete_with_hook(module, session, obj, before_delete, user.id)
        except IntegrityError:

            def build_conflict_response() -> HTMLResponse:
                state = _current_list_state(request)
                lista = sorted_list(
                    query_list(
                        session,
                        module,
                        q=state.q,
                        searchable=searchable,
                        list_func=list_func,
                        search_func=search_func,
                        search_column=state.search_column or None,
                        limit=state.limit,
                        offset=state.offset,
                        sort=state.sort,
                        order=state.order,
                        sort_fields=sort_fields,
                        sql_sort_fields=sql_sort_fields,
                        query_func=query_func,
                        search_query_func=search_query_func,
                    ),
                    state.sort,
                    state.order,
                    {} if sql_sort_fields is not None else sort_fields,
                )
                return list_response(
                    templates,
                    request,
                    list_partial_template,
                    user=user,
                    list_key=list_key,
                    lista=lista,
                    ctx_list=ctx_list(session, lista),
                    sort=state.sort,
                    order=state.order,
                    q=state.q if searchable else None,
                    search_column=state.search_column,
                    limit=state.limit,
                    offset=state.offset,
                    erro=delete_conflict_detail(label),
                    status_code=409,
                )

            return rollback_integrity_error_response(
                session,
                build_conflict_response,
            )
        state = _current_list_state(request)
        lista = sorted_list(
            query_list(
                session,
                module,
                q=state.q,
                searchable=searchable,
                list_func=list_func,
                search_func=search_func,
                search_column=state.search_column or None,
                limit=state.limit,
                offset=state.offset,
                sort=state.sort,
                order=state.order,
                sort_fields=sort_fields,
                sql_sort_fields=sql_sort_fields,
                query_func=query_func,
                search_query_func=search_query_func,
            ),
            state.sort,
            state.order,
            {} if sql_sort_fields is not None else sort_fields,
        )
        return list_response(
            templates,
            request,
            list_partial_template,
            user=user,
            list_key=list_key,
            lista=lista,
            ctx_list=ctx_list(session, lista),
            sort=state.sort,
            order=state.order,
            q=state.q if searchable else None,
            search_column=state.search_column,
            limit=state.limit,
            offset=state.offset,
        )
