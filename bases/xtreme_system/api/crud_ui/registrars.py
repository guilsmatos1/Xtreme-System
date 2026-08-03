from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    CreateSchemaT,
    CrudModule,
    EntityT,
    FormSpec,
    ListState,
    UpdateSchemaT,
)
from xtreme_system.api.crud_ui.config import (
    DEFAULT_CRUD_UI_ROUTES,
    ColumnSpec,
    CrudUIBehaviorConfig,
    CrudUICreateRouteConfig,
    CrudUIDeleteRouteConfig,
    CrudUIEditRouteConfig,
    CrudUIExportConfig,
    CrudUIExportRouteConfig,
    CrudUIListConfig,
    CrudUIListRouteConfig,
    CrudUINewRouteConfig,
    CrudUIReferenceConfig,
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    CrudUIUpdateRouteConfig,
)
from xtreme_system.api.crud_ui.helpers import (
    LIST_LIMIT_MAX,
    delete_list_response,
    write_conflict_response,
    write_ok_response,
)
from xtreme_system.api.crud_ui.query import query_list
from xtreme_system.api.crud_ui.responses import (
    csv_response,
    delete_conflict_detail,
    error_response,
    form_response,
    list_response,
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
    found,
    get_ui_user,
    require_ui_admin,
)
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

_MISSING_EXPORT_CONFIG = "A exportação exige columns ou csv_headers/csv_row"


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
    routes: CrudUIRouteConfig = DEFAULT_CRUD_UI_ROUTES,
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
        config=CrudUIListRouteConfig(
            list_key=resource.list_key,
            list_template=templates_config.list_template,
            list_partial_template=templates_config.list_partial_template,
            listing=listing,
            ctx_list=ctx_list,
            columns=export.columns,
            pagina=export.pagina,
        ),
    )
    register_export_route(
        app,
        module,
        prefix,
        config=CrudUIExportRouteConfig(
            listing=listing,
            csv_filename=export.csv_filename,
            columns=export.columns,
            csv_headers=export.csv_headers,
            csv_row=export.csv_row,
            csv_fields=export.csv_fields,
            pagina=export.pagina,
        ),
    )
    register_new_route(
        app,
        form,
        prefix,
        config=CrudUINewRouteConfig(cadastrar_dep=routes.cadastrar_dep),
    )
    if routes.register_edit:
        register_edit_route(
            app,
            form,
            module,
            prefix,
            config=CrudUIEditRouteConfig(
                label=resource.label, editar_dep=routes.editar_dep
            ),
        )
    if routes.register_create:
        register_create_route(
            app,
            form,
            module,
            prefix,
            config=CrudUICreateRouteConfig(
                label=resource.label,
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
            ),
        )
    if routes.register_update:
        register_update_route(
            app,
            form,
            module,
            prefix,
            config=CrudUIUpdateRouteConfig(
                label=resource.label,
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
            ),
        )
    if routes.register_delete:
        register_delete_route(
            app,
            templates,
            module,
            prefix,
            config=CrudUIDeleteRouteConfig(
                label=resource.label,
                list_key=resource.list_key,
                list_partial_template=templates_config.list_partial_template,
                ctx_list=ctx_list,
                before_delete=behavior.before_delete,
                after_delete=behavior.after_delete,
                delete_requires_admin=routes.delete_requires_admin,
                listing=listing,
                excluir_dep=routes.excluir_dep,
            ),
        )


def register_reference_lookup_routes(
    app: FastAPI,
    prefix: str,
    *,
    pagina: str,
    references: Mapping[str, CrudUIReferenceConfig],
) -> None:
    """Register bounded, server-side lookups used by foreign-key form fields."""

    @app.get(prefix + "/{reference}")
    def _lookup(
        reference: str,
        session: SessionDep,
        user: UIUser,
        q: str = "",
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        ids: Annotated[list[int] | None, Query()] = None,
    ) -> dict[str, Any]:
        config = references.get(reference)
        if config is None:
            raise HTTPException(status_code=404, detail="Referência não encontrada")
        if not perfil.pode_ver_campo(user, pagina, config.campo):
            raise HTTPException(status_code=403, detail="Campo não permitido")

        query = (
            config.search_query(session, q.strip())
            if q.strip() and not ids
            else config.query(session)
        )
        entity = query.column_descriptions[0].get("entity")
        id_column = getattr(entity, "id", None)
        if id_column is None:
            raise HTTPException(status_code=500, detail="Referência sem identificador")
        if ids:
            query = query.filter(id_column.in_(ids))

        page = list(
            query.order_by(id_column.asc()).offset(offset).limit(limit + 1).all()
        )
        return {
            "items": [
                {"id": item.id, "label": config.label(item)} for item in page[:limit]
            ],
            "has_more": len(page) > limit,
            "limit": limit,
            "offset": offset,
        }


def register_list_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    config: CrudUIListRouteConfig[EntityT],
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
        lista = query_list(session, module, listing=config.listing, state=state)
        template = (
            config.list_partial_template
            if request.headers.get("HX-Request")
            else config.list_template
        )
        context = config.ctx_list(session, lista)
        if config.columns is not None:
            context["columns"] = [
                column
                for column in config.columns
                if column.table
                and (
                    config.pagina is None
                    or column.field is None
                    or perfil.pode_ver_campo(user, config.pagina, column.field)
                )
            ]
        return list_response(
            templates,
            request,
            template,
            user=user,
            list_key=config.list_key,
            lista=lista,
            ctx_list=context,
            sort=sort or config.listing.default_sort,
            order=order if sort else config.listing.default_order,
            q=q if config.listing.searchable else None,
            search_column=search_column,
            limit=limit,
            offset=offset,
        )


def register_export_route(
    app: FastAPI,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    config: CrudUIExportRouteConfig[EntityT],
) -> None:
    @app.get(f"{prefix}/exportar")
    def _exportar(session: SessionDep, user: UIUser, q: str = "") -> Response:
        lista = query_list(
            session, module, listing=config.listing, state=ListState(q=q)
        )
        if config.columns is not None:
            export_columns: list[tuple[ColumnSpec[EntityT], Any]] = []
            for column in config.columns:
                export_value = column.export
                if export_value is None or (
                    config.pagina is not None
                    and column.field is not None
                    and not perfil.pode_ver_campo(user, config.pagina, column.field)
                ):
                    continue
                export_columns.append((column, export_value))
            headers = [column.label for column, _ in export_columns]
            rows = [
                [export_value(obj) for _, export_value in export_columns]
                for obj in lista
            ]
        elif config.csv_headers is not None and config.csv_row is not None:
            headers = config.csv_headers
            rows = [config.csv_row(obj) for obj in lista]
        else:
            raise RuntimeError(_MISSING_EXPORT_CONFIG)
        if config.columns is None and config.pagina and config.csv_fields:
            indices = [
                idx
                for idx, campo in enumerate(config.csv_fields)
                if campo is None or perfil.pode_ver_campo(user, config.pagina, campo)
            ]
            headers = [headers[idx] for idx in indices]
            rows = [[row[idx] for idx in indices] for row in rows]
        return csv_response(config.csv_filename, headers, rows)


def register_new_route(
    app: FastAPI,
    form: FormSpec,
    prefix: str,
    *,
    config: CrudUINewRouteConfig,
) -> None:
    dep = config.cadastrar_dep or require_ui_admin

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
    *,
    config: CrudUIEditRouteConfig,
) -> None:
    dep = config.editar_dep or require_ui_admin

    @app.get(f"{prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = found(module.get(session, item_id), config.label)
        return form_response(
            form.templates,
            request,
            form.form_template,
            ctx_form=form.ctx_form(session),
            item_key=form.item_key,
            item=obj,
            user=user,
        )


def register_create_route(
    app: FastAPI,
    form: FormSpec,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    config: CrudUICreateRouteConfig[EntityT, CreateSchemaT],
) -> None:
    dep = config.cadastrar_dep or require_ui_admin

    @app.post(prefix)
    async def _criar(
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        form_data = await request.form()
        dados_form = config.parse_form(form_data)
        dados_form = perfil.campos_form_visiveis(user, config.pagina, dados_form)
        try:
            data = config.create_schema.model_validate(dados_form)
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
                    config.after_create,
                    user.id,
                    before_create=config.before_create,
                ),
                conflict_msg=write_conflict_detail(config.label),
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
            config.ok_partial_template,
            user=user,
            list_key=config.list_key,
            ctx_list=config.ctx_list,
            listing=config.listing,
        )


def register_update_route(
    app: FastAPI,
    form: FormSpec,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    config: CrudUIUpdateRouteConfig[EntityT, UpdateSchemaT],
) -> None:
    dep = config.editar_dep or require_ui_admin

    @app.post(f"{prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = found(module.get(session, item_id), config.label)
        form_data = await request.form()
        dados_form = config.parse_form(form_data)
        dados_form = perfil.campos_form_visiveis(user, config.pagina, dados_form)
        try:
            data = config.update_schema.model_validate(dados_form)
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
                lambda: _update_with_before_hook(
                    module,
                    session,
                    obj,
                    data,
                    config.before_update,
                    config.after_update,
                    user.id,
                ),
                conflict_msg=write_conflict_detail(config.label),
            )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_409_CONFLICT:
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
                    dados=dados_form,
                )
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
            config.ok_partial_template,
            user=user,
            list_key=config.list_key,
            ctx_list=config.ctx_list,
            listing=config.listing,
        )


def _update_with_before_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    obj: EntityT,
    data: UpdateSchemaT,
    before_update: Any,
    after_update: Any,
    actor_id: int | None,
) -> EntityT:
    run_hook(before_update, session, data)
    return update_with_hook(module, session, obj, data, after_update, actor_id)


def register_delete_route(
    app: FastAPI,
    templates: Jinja2Templates,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    prefix: str,
    *,
    config: CrudUIDeleteRouteConfig[EntityT],
) -> None:
    dep = config.excluir_dep or (
        require_ui_admin if config.delete_requires_admin else get_ui_user
    )

    @app.post(f"{prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int,
        request: Request,
        session: SessionDep,
        user: Annotated[usuario.Usuario, Depends(dep)],
    ) -> HTMLResponse:
        obj = found(module.get(session, item_id), config.label)
        try:
            delete_with_hook(module, session, obj, config.before_delete, user.id)
            if config.after_delete:
                config.after_delete(session, obj, user.id)
        except IntegrityError:

            def build_conflict_response() -> HTMLResponse:
                return delete_list_response(
                    session,
                    templates,
                    request,
                    module,
                    config.list_partial_template,
                    user=user,
                    list_key=config.list_key,
                    ctx_list=config.ctx_list,
                    listing=config.listing,
                    erro=delete_conflict_detail(config.label),
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
            config.list_partial_template,
            user=user,
            list_key=config.list_key,
            ctx_list=config.ctx_list,
            listing=config.listing,
        )


__all__ = [
    "register_create_route",
    "register_crud_ui_routes",
    "register_delete_route",
    "register_edit_route",
    "register_export_route",
    "register_list_route",
    "register_new_route",
    "register_reference_lookup_routes",
    "register_update_route",
]
