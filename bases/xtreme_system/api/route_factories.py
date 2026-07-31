"""Factories genéricas de rotas CRUD JSON reutilizadas por entidade."""

from typing import Annotated, Any, cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    BeforeCreateHook,
    BeforeDeleteHook,
    BeforeUpdateEntityHook,
    CreateSchemaT,
    CrudModule,
    EntityT,
    ReadSchemaT,
    UpdateSchemaT,
)
from xtreme_system.api.crud_ui.responses import (
    delete_conflict_detail,
    write_conflict_detail,
)
from xtreme_system.api.crud_writes import create_with_hook, update_with_hook
from xtreme_system.api.crud_writes import safe_write as _safe_write
from xtreme_system.api.deps import CurrentUser, SessionDep, found
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

JSON_LIST_LIMIT_MAX = 200


def _require_json_page(user: usuario.Usuario, pagina: str) -> None:
    if not perfil.pode_acessar(user, pagina):
        raise HTTPException(status_code=403, detail="Página não permitida")


def _json_visible(
    obj: Any,
    user: usuario.Usuario,
    pagina: str | None,
    campos: tuple[str, ...],
    read_schema: type[Any],
    campos_permissao: dict[str, tuple[str, ...]] | None = None,
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
    for campo_permissao, campos_json in (campos_permissao or {}).items():
        if not perfil.pode_ver_campo(user, pagina, campo_permissao):
            for campo_json in campos_json:
                data.pop(campo_json, None)
    return data


def json_visible(
    obj: Any,
    user: usuario.Usuario,
    pagina: str,
    read_schema: type[Any] | None = None,
    *,
    campos_protegidos: tuple[str, ...] = (),
    campos_permissao: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _json_visible(
            obj,
            user,
            pagina,
            campos_protegidos,
            read_schema or type(obj),
            campos_permissao,
        ),
    )


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
    def _list(
        session: SessionDep,
        user: CurrentUser,
        limit: Annotated[int, Query(ge=1, le=JSON_LIST_LIMIT_MAX)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[EntityT] | list[Any]:
        if pagina is not None:
            _require_json_page(user, pagina)
        return [
            _json_visible(obj, user, pagina, campos_protegidos, read_schema)
            for obj in module.list_all(session, limit=limit, offset=offset)
        ]

    @app.get(f"{prefix}/{{item_id}}", response_model=None if pagina else read_schema)
    def _get(item_id: int, session: SessionDep, user: CurrentUser) -> EntityT | Any:
        obj = found(module.get(session, item_id), label)
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
        return _safe_write(
            lambda: create_with_hook(
                module,
                session,
                data,
                after_create,
                actor_id,
                before_create=before_create,
            ),
            conflict_msg=write_conflict_detail(label),
        )

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
        obj = found(module.get(session, item_id), label)
        return _safe_write(
            lambda: _update_with_hooks(obj, data, session, actor_id),
            conflict_msg=write_conflict_detail(label),
        )

    def _update_with_hooks(
        obj: EntityT, data: UpdateSchemaT, session: Session, actor_id: int | None
    ) -> EntityT:
        if before_update:
            before_update(session, obj, data)
        return update_with_hook(module, session, obj, data, after_update, actor_id)

    @app.delete(f"{prefix}/{{item_id}}", status_code=204)
    def _delete(item_id: int, session: SessionDep, user: CurrentUser) -> None:
        if pagina is not None:
            _require_json_operacao(user, pagina, "excluir")
        _delete_atomic(item_id, session, user.id)

    def _delete_atomic(item_id: int, session: Session, actor_id: int | None) -> None:
        obj = found(module.get(session, item_id), label)
        if before_delete:
            before_delete(session, obj, actor_id)
        if handle_delete_error:
            try:
                module.delete(session, obj, actor_id)
            except IntegrityError:
                raise HTTPException(
                    status_code=409, detail=delete_conflict_detail(label)
                ) from None
        else:
            module.delete(session, obj, actor_id)
