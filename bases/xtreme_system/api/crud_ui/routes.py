from collections.abc import Callable, Sequence
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
    FormSpec,
    ListingSpec,
    ListState,
    ParseForm,
    UpdateSchemaT,
)
from xtreme_system.api.crud_ui.query import query_list
from xtreme_system.api.crud_ui.responses import (
    conflict_form_response,
    csv_response,
    delete_conflict_detail,
    error_response,
    form_response,
    list_response,
    ok_response,
    rollback_integrity_error_response,
    validation_error_detail,
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
_MISSING_EXPORT_CONFIG = "A exportação exige columns ou csv_headers/csv_row"


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


CrudUIListConfig = ListingSpec


@dataclass(frozen=True)
class ColumnSpec[EntityT]:
    key: str
    label: str
    field: str | None = None
    table: bool = True
    html: Callable[[EntityT], Any] | None = None
    export: Callable[[EntityT], Any] | None = None


@dataclass(frozen=True)
class CrudUIExportConfig[EntityT]:
    csv_filename: str
    columns: Sequence[ColumnSpec[EntityT]] | None = None
    csv_headers: list[str] | None = None
    csv_row: CsvRow[EntityT] | None = None
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


_DEFAULT_CRUD_UI_ROUTES = CrudUIRouteConfig()


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
def register_crud_ui_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    resource: CrudUIResourceConfig[CreateSchemaT, UpdateSchemaT],
    templates_config: CrudUITemplateConfig,
    listing: CrudUIListConfig[EntityT],
    export: CrudUIExportConfig[EntityT],
    behavior: CrudUIBehaviorConfig[EntityT, CreateSchemaT, UpdateSchemaT] | None = None,
    routes: CrudUIRouteConfig = _DEFAULT_CRUD_UI_ROUTES,
) -> None:
    if behavior is None:
        behavior = CrudUIBehaviorConfig()
    ctx_list = behavior.ctx_list
    if export.columns is not None:
        base_ctx_list = ctx_list

        def column_ctx_list(session: Any, lista: list[EntityT]) -> dict[str, Any]:
            return {
                **base_ctx_list(session, lista),
                "columns": [column for column in export.columns or () if column.table],
            }

        ctx_list = column_ctx_list

    form = FormSpec(
        templates=templates,
        form_template=templates_config.form_template,
        ctx_form=behavior.ctx_form,
        item_key=resource.item_key,
    )
    register_list_route(
        app,
        templates,
        module,
        prefix,
        list_key=resource.list_key,
        list_template=templates_config.list_template,
        list_partial_template=templates_config.list_partial_template,
        listing=listing,
        ctx_list=ctx_list,
        columns=export.columns,
        pagina=export.pagina,
    )
    register_export_route(
        app,
        module,
        prefix,
        listing=listing,
        csv_filename=export.csv_filename,
        columns=export.columns,
        csv_headers=export.csv_headers,
        csv_row=export.csv_row,
        csv_fields=export.csv_fields,
        pagina=export.pagina,
    )
    register_new_route(
        app,
        form,
        prefix,
        cadastrar_dep=routes.cadastrar_dep,
    )
    if routes.register_edit:
        register_edit_route(
            app,
            form,
            module,
            prefix,
            resource.label,
            editar_dep=routes.editar_dep,
        )
    if routes.register_create:
        register_create_route(
            app,
            form,
            module,
            prefix,
            resource.label,
            create_schema=resource.create_schema,
            list_key=resource.list_key,
            ok_partial_template=templates_config.ok_partial_template,
            ctx_list=ctx_list,
            parse_form=behavior.parse_form,
            pagina=export.pagina,
            before_create=behavior.before_create,
            after_create=behavior.after_create,
            listing=listing,
            cadastrar_dep=routes.cadastrar_dep,
        )
    if routes.register_update:
        register_update_route(
            app,
            form,
            module,
            prefix,
            resource.label,
            update_schema=resource.update_schema,
            list_key=resource.list_key,
            ok_partial_template=templates_config.ok_partial_template,
            ctx_list=ctx_list,
            parse_form=behavior.parse_form,
            before_update=behavior.before_update,
            after_update=behavior.after_update,
            listing=listing,
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
            ctx_list=ctx_list,
            before_delete=behavior.before_delete,
            delete_requires_admin=routes.delete_requires_admin,
            listing=listing,
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
    listing: ListingSpec[EntityT],
    ctx_list: CtxList[EntityT],
    columns: Sequence[ColumnSpec[EntityT]] | None = None,
    pagina: str | None = None,
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
        state = ListState(
            q=q,
            sort=sort,
            order=order,
            search_column=search_column,
            limit=limit,
            offset=offset,
        )
        lista = query_list(session, module, listing=listing, state=state)
        template = (
            list_partial_template
            if request.headers.get("HX-Request")
            else list_template
        )
        context = ctx_list(session, lista)
        if columns is not None:
            context["columns"] = [
                column
                for column in columns
                if column.table
                and (
                    pagina is None
                    or column.field is None
                    or perfil.pode_ver_campo(user, pagina, column.field)
                )
            ]
        return list_response(
            templates,
            request,
            template,
            user=user,
            list_key=list_key,
            lista=lista,
            ctx_list=context,
            sort=sort or listing.default_sort,
            order=order if sort else listing.default_order,
            q=q if listing.searchable else None,
            search_column=search_column,
            limit=limit,
            offset=offset,
        )


def register_export_route(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    listing: ListingSpec[EntityT],
    csv_filename: str,
    columns: Sequence[ColumnSpec[EntityT]] | None = None,
    csv_headers: list[str] | None = None,
    csv_row: CsvRow[EntityT] | None = None,
    csv_fields: list[str | None] | None = None,
    pagina: str | None = None,
) -> None:
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, user: UIUser, q: str = "") -> Response:
        lista = query_list(session, module, listing=listing, state=ListState(q=q))
        if columns is not None:
            export_columns: list[
                tuple[ColumnSpec[EntityT], Callable[[EntityT], Any]]
            ] = []
            for column in columns:
                export_value = column.export
                if export_value is None or (
                    pagina is not None
                    and column.field is not None
                    and not perfil.pode_ver_campo(user, pagina, column.field)
                ):
                    continue
                export_columns.append((column, export_value))
            headers = [column.label for column, _ in export_columns]
            rows = [
                [export_value(obj) for _, export_value in export_columns]
                for obj in lista
            ]
        elif csv_headers is not None and csv_row is not None:
            headers = csv_headers
            rows = [csv_row(obj) for obj in lista]
        else:
            raise RuntimeError(_MISSING_EXPORT_CONFIG)
        if columns is None and pagina and csv_fields:
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
    form: FormSpec,
    prefix: str,
    *,
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
            form.templates,
            request,
            form.form_template,
            ctx_form=form.ctx_form(session),
            item_key=form.item_key,
            item=None,
            user=user,
        )


def register_edit_route(
    app: FastAPI,
    form: FormSpec,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
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
            form.templates,
            request,
            form.form_template,
            ctx_form=form.ctx_form(session),
            item_key=form.item_key,
            item=obj,
            user=user,
        )


def write_conflict_response(
    session: SessionDep,
    request: Request,
    form: FormSpec,
    *,
    item: object,
    user: usuario.Usuario,
    erro: str,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return rollback_integrity_error_response(
        session,
        lambda: conflict_form_response(
            form.templates,
            request,
            form.form_template,
            ctx_form=form.ctx_form(session),
            item_key=form.item_key,
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
    listing: ListingSpec[EntityT],
) -> HTMLResponse:
    state = _current_list_state(request)
    lista = query_list(session, module, listing=listing, state=state)
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
    form: FormSpec,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    create_schema: type[CreateSchemaT],
    list_key: str,
    ok_partial_template: str,
    ctx_list: CtxList[EntityT],
    parse_form: ParseForm,
    pagina: str | None,
    before_create: BeforeCreateHook[CreateSchemaT] | None,
    after_create: AfterWriteHook[EntityT] | None,
    listing: ListingSpec[EntityT],
    cadastrar_dep: DepFactory | None = None,
) -> None:
    dep = cadastrar_dep or require_ui_admin

    @app.post(prefix)
    async def _criar(
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        form_data = await request.form()
        dados_form = parse_form(form_data)
        perfil.filtrar_campos_form_ocultos(user, pagina, dados_form)
        try:
            data = create_schema.model_validate(dados_form)
        except ValidationError as exc:
            return error_response(
                form.templates,
                request,
                form.form_template,
                ctx_form=form.ctx_form(session),
                item_key=form.item_key,
                item=None,
                user=user,
                erro=validation_error_detail(exc),
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
                    request,
                    form=form,
                    item=data,
                    user=user,
                    erro=erro,
                    dados=dados_form,
                )
            return error_response(
                form.templates,
                request,
                form.form_template,
                ctx_form=form.ctx_form(session),
                item_key=form.item_key,
                item=None,
                user=user,
                erro=erro,
                status_code=400,
                dados=dados_form,
            )
        return write_ok_response(
            session,
            form.templates,
            request,
            module,
            ok_partial_template,
            user=user,
            list_key=list_key,
            ctx_list=ctx_list,
            listing=listing,
        )


def register_update_route(
    app: FastAPI,
    form: FormSpec,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    label: str,
    *,
    update_schema: type[UpdateSchemaT],
    list_key: str,
    ok_partial_template: str,
    ctx_list: CtxList[EntityT],
    parse_form: ParseForm,
    before_update: BeforeUpdateHook[UpdateSchemaT] | None,
    after_update: AfterWriteHook[EntityT] | None,
    listing: ListingSpec[EntityT],
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
        form_data = await request.form()
        dados_form = parse_form(form_data)
        perfil.filtrar_campos_form_ocultos(user, pagina, dados_form)
        try:
            data = update_schema.model_validate(dados_form)
            run_hook(before_update, session, data)
        except ValidationError as exc:
            return error_response(
                form.templates,
                request,
                form.form_template,
                ctx_form=form.ctx_form(session),
                item_key=form.item_key,
                item=obj,
                user=user,
                erro=validation_error_detail(exc),
                status_code=400,
            )
        except HTTPException as exc:
            return error_response(
                form.templates,
                request,
                form.form_template,
                ctx_form=form.ctx_form(session),
                item_key=form.item_key,
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
                request,
                form=form,
                item=obj,
                user=user,
                erro=erro,
            )
        return write_ok_response(
            session,
            form.templates,
            request,
            module,
            ok_partial_template,
            user=user,
            list_key=list_key,
            ctx_list=ctx_list,
            listing=listing,
        )


def delete_list_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    list_partial_template: str,
    *,
    user: usuario.Usuario,
    list_key: str,
    ctx_list: CtxList[EntityT],
    listing: ListingSpec[EntityT],
    erro: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    state = _current_list_state(request)
    lista = query_list(session, module, listing=listing, state=state)
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
        q=state.q if listing.searchable else None,
        search_column=state.search_column,
        limit=state.limit if state.limit is not None else 50,
        offset=state.offset,
        erro=erro,
        status_code=status_code,
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
    listing: ListingSpec[EntityT],
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
                return delete_list_response(
                    session,
                    templates,
                    request,
                    module,
                    list_partial_template,
                    user=user,
                    list_key=list_key,
                    ctx_list=ctx_list,
                    listing=listing,
                    erro=delete_conflict_detail(label),
                    status_code=409,
                )

            return rollback_integrity_error_response(
                session,
                build_conflict_response,
            )
        return delete_list_response(
            session,
            templates,
            request,
            module,
            list_partial_template,
            user=user,
            list_key=list_key,
            ctx_list=ctx_list,
            listing=listing,
        )
