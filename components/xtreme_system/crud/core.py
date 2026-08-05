"""CRUD genérico: list_all, get, create, update, delete para qualquer model."""

from decimal import Decimal, InvalidOperation
from typing import Any, cast

from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import auditar, snapshot


def flush(session: Session) -> None:
    session.flush()


def parse_decimal_br(value: Any) -> Any:
    """Normaliza valores monetários digitados em formulários (pt-BR ou US).

    Aceita "1.234,56" (BR), "1234.56" (US/inputmode=decimal) e tipos não-str
    (int, float, Decimal, None) sem alteração — a validação de tipo/faixa
    fica a cargo do Field do schema chamador.
    """
    if not isinstance(value, str):
        return value
    texto = value.strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        Decimal(texto)
    except InvalidOperation:
        return value
    return texto


def trim_texto_obrigatorio(value: Any) -> Any:
    """Remove espaços e rejeita string vazia/whitespace-only em campo obrigatório."""
    if isinstance(value, str):
        value = value.strip()
    if not value:
        raise ValueError("Campo obrigatório")
    return value


def trim_texto(value: Any) -> Any:
    """Remove espaços de um campo string opcional, sem rejeitar vazio."""
    if isinstance(value, str):
        return value.strip()
    return value


def list_all[M](
    session: Session,
    model_cls: type[M],
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[M]:
    query = session.query(model_cls).order_by(cast(Any, model_cls).id)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    return list(query.all())


def get[M](session: Session, model_cls: type[M], id_: int) -> M | None:
    return session.get(model_cls, id_)


def create[M](
    session: Session, model_cls: type[M], data: Any, actor_id: int | None = None
) -> M:
    obj = model_cls(**data.model_dump())
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela=model_cls.__tablename__,  # type: ignore[attr-defined]
        tipo_acao="CREATE",
        registro_id=obj.id,  # type: ignore[attr-defined]
        dados_depois=snapshot(obj),
    )
    flush(session)
    return obj


def update[M](session: Session, obj: M, data: Any, actor_id: int | None = None) -> M:
    antes = snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela=obj.__tablename__,  # type: ignore[attr-defined]
        tipo_acao="UPDATE",
        registro_id=obj.id,  # type: ignore[attr-defined]
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    flush(session)
    return obj


def delete(session: Session, obj: Any, actor_id: int | None = None) -> None:
    tabela = obj.__tablename__
    obj_id = obj.id
    antes = snapshot(obj)
    session.delete(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela=tabela,
        tipo_acao="DELETE",
        registro_id=obj_id,
        dados_antes=antes,
    )
    flush(session)
