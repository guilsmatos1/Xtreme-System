"""CRUD genérico: list_all, get, create, update, delete para qualquer model."""

from typing import Any

from sqlalchemy.orm import Session


def list_all[M](session: Session, model_cls: type[M]) -> list[M]:
    return list(session.query(model_cls).all())


def get[M](session: Session, model_cls: type[M], id_: int) -> M | None:
    return session.get(model_cls, id_)


def create[M](session: Session, model_cls: type[M], data: Any) -> M:
    obj = model_cls(**data.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update[M](session: Session, obj: M, data: Any) -> M:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: Any) -> None:
    session.delete(obj)
    session.commit()
