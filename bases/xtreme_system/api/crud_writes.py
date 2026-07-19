from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    ArgT,
    BeforeDeleteHook,
    CreateSchemaT,
    CrudModule,
    EntityT,
    ResultT,
    UpdateSchemaT,
)


def safe_write(op: Callable[[], ResultT], *, conflict_msg: str) -> ResultT:
    try:
        return op()
    except IntegrityError:
        raise HTTPException(status_code=409, detail=conflict_msg) from None


def run_hook(
    hook: Callable[[Session, ArgT], object] | None,
    session: Session,
    arg: ArgT,
) -> None:
    if hook:
        hook(session, arg)


def create_with_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    data: CreateSchemaT,
    after_create: AfterWriteHook[EntityT] | None,
    actor_id: int | None,
) -> EntityT:
    obj = module.create(session, data, actor_id)
    if after_create:
        after_create(session, obj, actor_id)
    return obj


def update_with_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    obj: EntityT,
    data: UpdateSchemaT,
    after_update: AfterWriteHook[EntityT] | None,
    actor_id: int | None,
) -> EntityT:
    updated = module.update(session, obj, data, actor_id)
    if after_update:
        after_update(session, updated, actor_id)
    return updated


def delete_with_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    obj: EntityT,
    before_delete: BeforeDeleteHook[EntityT] | None,
    actor_id: int | None,
) -> None:
    if before_delete:
        before_delete(session, obj, actor_id)
    module.delete(session, obj, actor_id)
