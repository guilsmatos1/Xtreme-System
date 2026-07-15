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


def safe_write(
    session: Session, op: Callable[[], ResultT], *, conflict_msg: str
) -> ResultT:
    try:
        return op()
    except IntegrityError:
        session.rollback()
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
) -> EntityT:
    obj = module.create(session, data)
    run_hook(after_create, session, obj)
    return obj


def update_with_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    obj: EntityT,
    data: UpdateSchemaT,
    after_update: AfterWriteHook[EntityT] | None,
) -> EntityT:
    updated = module.update(session, obj, data)
    run_hook(after_update, session, updated)
    return updated


def delete_with_hook(
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    session: Session,
    obj: EntityT,
    before_delete: BeforeDeleteHook[EntityT] | None,
) -> None:
    run_hook(before_delete, session, obj)
    module.delete(session, obj)
