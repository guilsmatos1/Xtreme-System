"""Factories for simple URL attachment CRUD modules."""

from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud


class CreateFn[M, S](Protocol):
    def __call__(self, session: Session, data: S, actor_id: int | None = None) -> M: ...


class UpdateFn[M, S](Protocol):
    def __call__(
        self, session: Session, obj: M, data: S, actor_id: int | None = None
    ) -> M: ...


class DeleteFn[M](Protocol):
    def __call__(
        self, session: Session, obj: M, actor_id: int | None = None
    ) -> None: ...


class ListAllFn[M](Protocol):
    def __call__(
        self, session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[M]: ...


class UrlAttachmentMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]


def make_list_all[M](model_cls: type[M]) -> ListAllFn[M]:
    def list_all(
        session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[M]:
        return crud.list_all(session, model_cls, limit=limit, offset=offset)

    return list_all


def make_list_by_field[M](
    model_cls: type[M], field_name: str
) -> Callable[[Session, int], list[M]]:
    def list_by_field(session: Session, field_value: int) -> list[M]:
        return list(
            session.query(model_cls).filter_by(**{field_name: field_value}).all()
        )

    return list_by_field


def make_list_by_field_ids[M](
    model_cls: type[M], field_name: str
) -> Callable[[Session, list[int]], list[M]]:
    def list_by_field_ids(session: Session, field_values: list[int]) -> list[M]:
        if not field_values:
            return []
        id_field_name = "id"
        field = getattr(model_cls, field_name)
        return list(
            session.query(model_cls)
            .filter(field.in_(field_values))
            .order_by(field, getattr(model_cls, id_field_name))
            .all()
        )

    return list_by_field_ids


def make_get[M](model_cls: type[M]) -> Callable[[Session, int], M | None]:
    def get(session: Session, obj_id: int) -> M | None:
        return crud.get(session, model_cls, obj_id)

    return get


def make_create[M, S](model_cls: type[M], _schema_cls: type[S]) -> CreateFn[M, S]:
    def create(session: Session, data: S, actor_id: int | None = None) -> M:
        return crud.create(session, model_cls, data, actor_id)

    return create


def make_update[M, S](_model_cls: type[M], _schema_cls: type[S]) -> UpdateFn[M, S]:
    def update(session: Session, obj: M, data: S, actor_id: int | None = None) -> M:
        return crud.update(session, obj, data, actor_id)

    return update


def make_delete[M](_model_cls: type[M]) -> DeleteFn[M]:
    def delete(session: Session, obj: M, actor_id: int | None = None) -> None:
        crud.delete(session, obj, actor_id)

    return delete
