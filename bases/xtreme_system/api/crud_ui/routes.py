from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
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
    SearchFunc,
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
    write_conflict_detail,
)
from xtreme_system.api.crud_writes import (
    create_with_hook,
    delete_with_hook,
    run_hook,
    update_with_hook,
)
from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    UIUser,
    _found,
    get_ui_user,
    require_ui_admin,
)
from xtreme_system.usuario import core as usuario


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
    delete_requires_admin: bool = True,
    register_create: bool = True,
    register_update: bool = True,
    list_func: ListFunc[EntityT] | None = None,
    search_func: SearchFunc[EntityT] | None = None,
) -> None:
    register_list_route(
        app,
        templates,
        module,
        prefix,
        list_key=list_key,
        list_template=list_template,
        list_partial_template=list_partial_template,
        sort_fields=sort_fields,
        ctx_list=ctx_list,
        searchable=searchable,
        list_func=list_func,
        search_func=search_func,
    )
    register_export_route(
        app,
        module,
        prefix,
        searchable=searchable,
        list_func=list_func,
        search_func=search_func,
        csv_filename=csv_filename,
        csv_headers=csv_headers,
        csv_row=csv_row,
    )
    register_new_route(
        app,
        templates,
        prefix,
        form_template=form_template,
        ctx_form=ctx_form,
        item_key=item_key,
    )
    register_edit_route(
        app,
        templates,
        module,
        prefix,
        label,
        form_template=form_template,
        ctx_form=ctx_form,
        item_key=item_key,
    )
    if register_create:
        register_create_route(
            app,
            templates,
            module,
            prefix,
            label,
            create_schema=create_schema,
            list_key=list_key,
            item_key=item_key,
            form_template=form_template,
            ok_partial_template=ok_partial_template,
            ctx_form=ctx_form,
            ctx_list=ctx_list,
            parse_form=parse_form,
            before_create=before_create,
            after_create=after_create,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
        )
    if register_update:
        register_update_route(
            app,
            templates,
            module,
            prefix,
            label,
            update_schema=update_schema,
            list_key=list_key,
            item_key=item_key,
            form_template=form_template,
            ok_partial_template=ok_partial_template,
            ctx_form=ctx_form,
            ctx_list=ctx_list,
            parse_form=parse_form,
            before_update=before_update,
            after_update=after_update,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
        )
    register_delete_route(
        app,
        templates,
        module,
        prefix,
        label,
        list_key=list_key,
        list_partial_template=list_partial_template,
        ctx_list=ctx_list,
        before_delete=before_delete,
        delete_requires_admin=delete_requires_admin,
        searchable=searchable,
        list_func=list_func,
        search_func=search_func,
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
) -> None:
    @app.get(prefix)
    def _list(
        request: Request,
        session: SessionDep,
        user: UIUser,
        q: str = "",
        sort: str = "",
        order: str = "asc",
    ) -> HTMLResponse:
        lista = sorted_list(
            query_list(
                session,
                module,
                q=q,
                searchable=searchable,
                list_func=list_func,
                search_func=search_func,
            ),
            sort,
            order,
            sort_fields,
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
        )


def register_export_route(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    csv_filename: str,
    csv_headers: list[str],
    csv_row: CsvRow[EntityT],
) -> None:
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, _: UIUser, q: str = "") -> Response:
        lista = query_list(
            session,
            module,
            q=q,
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
        )
        return csv_response(csv_filename, csv_headers, [csv_row(obj) for obj in lista])


def register_new_route(
    app: FastAPI,
    templates: Jinja2Templates,
    prefix: str,
    *,
    form_template: str,
    ctx_form: CtxForm,
    item_key: str,
) -> None:
    @app.get(f"{prefix}/novo")
    def _novo(request: Request, session: SessionDep, _: UIAdmin) -> HTMLResponse:
        return form_response(
            templates,
            request,
            form_template,
            ctx_form=ctx_form(session),
            item_key=item_key,
            item=None,
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
) -> None:
    @app.get(f"{prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int, request: Request, session: SessionDep, _: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), label)
        return form_response(
            templates,
            request,
            form_template,
            ctx_form=ctx_form(session),
            item_key=item_key,
            item=obj,
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
) -> None:
    @app.post(prefix)
    async def _criar(
        request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        form = await request.form()
        try:
            data = create_schema.model_validate(parse_form(form))
            run_hook(before_create, session, data)
        except ValidationError:
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=None,
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
                item=None,
                erro=str(exc.detail),
                status_code=400,
            )
        except IntegrityError:
            session.rollback()
            return conflict_form_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=None,
                erro=write_conflict_detail(label),
            )
        try:
            create_with_hook(module, session, data, after_create)
        except IntegrityError:
            session.rollback()
            return conflict_form_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=None,
                erro=write_conflict_detail(label),
            )
        lista = query_list(
            session,
            module,
            q="",
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
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
) -> None:
    @app.post(f"{prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        session.info["usuario_id"] = user.id
        obj = _found(module.get(session, item_id), label)
        form = await request.form()
        try:
            data = update_schema.model_validate(parse_form(form))
            run_hook(before_update, session, data)
        except ValidationError:
            return error_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=obj,
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
                erro=str(exc.detail),
                status_code=400,
            )
        try:
            update_with_hook(module, session, obj, data, after_update)
        except IntegrityError:
            session.rollback()
            return conflict_form_response(
                templates,
                request,
                form_template,
                ctx_form=ctx_form(session),
                item_key=item_key,
                item=obj,
                erro=write_conflict_detail(label),
            )
        lista = query_list(
            session,
            module,
            q="",
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
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
) -> None:
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
            delete_with_hook(module, session, obj, before_delete)
        except IntegrityError:
            session.rollback()
            erro = delete_conflict_detail(label)
            status_code = 409
        lista = query_list(
            session,
            module,
            q="",
            searchable=searchable,
            list_func=list_func,
            search_func=search_func,
        )
        return list_response(
            templates,
            request,
            list_partial_template,
            user=user,
            list_key=list_key,
            lista=lista,
            ctx_list=ctx_list(session, lista),
            erro=erro,
            status_code=status_code,
        )
