"""CRUD genérico: list_all, get, create, update, delete para qualquer model."""

from typing import Any

from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import _snapshot, auditar


def list_all[M](session: Session, model_cls: type[M]) -> list[M]:
    return list(session.query(model_cls).all())


def get[M](session: Session, model_cls: type[M], id_: int) -> M | None:
    return session.get(model_cls, id_)


def create[M](session: Session, model_cls: type[M], data: Any) -> M:
    obj = model_cls(**data.model_dump())
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        tabela=model_cls.__tablename__,  # type: ignore[attr-defined]
        tipo_acao="CREATE",
        registro_id=obj.id,  # type: ignore[attr-defined]
        dados_depois=_snapshot(obj),
    )
    session.commit()
    return obj


def update[M](session: Session, obj: M, data: Any) -> M:
    antes = _snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        tabela=obj.__tablename__,  # type: ignore[attr-defined]
        tipo_acao="UPDATE",
        registro_id=obj.id,  # type: ignore[attr-defined]
        dados_antes=antes,
        dados_depois=_snapshot(obj),
    )
    session.commit()
    return obj


def delete(session: Session, obj: Any) -> None:
    tabela = obj.__tablename__
    obj_id = obj.id
    antes = _snapshot(obj)
    session.delete(obj)
    auditar(
        session,
        tabela=tabela,
        tipo_acao="DELETE",
        registro_id=obj_id,
        dados_antes=antes,
    )
    session.commit()
