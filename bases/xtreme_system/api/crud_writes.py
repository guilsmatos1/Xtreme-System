from collections.abc import Callable

import structlog
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    ArgT,
    BeforeCreateHook,
    BeforeDeleteHook,
    CreateSchemaT,
    CrudModule,
    EntityT,
    ResultT,
    UpdateSchemaT,
)

logger = structlog.get_logger(__name__)


def safe_write(op: Callable[[], ResultT], *, conflict_msg: str) -> ResultT:
    try:
        return op()
    except IntegrityError as exc:
        logger.warning(
            "write_conflict",
            conflict_msg=conflict_msg,
            erro=str(exc.orig),
        )
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
    *,
    before_create: BeforeCreateHook[CreateSchemaT] | None = None,
) -> EntityT:
    run_hook(before_create, session, data)
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
