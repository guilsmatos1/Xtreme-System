"""Investidor: model, schemas e CRUD."""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Boolean, false
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class Investidor(Base):
    __tablename__ = "investidor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)
    notificar_telegram: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )


class InvestidorCreate(BaseModel):
    nome: str
    notificar_telegram: bool = False

    @field_validator("nome", mode="before")
    @classmethod
    def _validar_nome(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto_obrigatorio(value)


class InvestidorUpdate(BaseModel):
    nome: str | None = None
    notificar_telegram: bool | None = None

    @field_validator("nome", mode="before")
    @classmethod
    def _validar_nome(cls, value: Any) -> Any:
        _ = cls
        if value is None:
            return None
        return crud.trim_texto_obrigatorio(value)


class InvestidorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    notificar_telegram: bool = False


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Investidor]:
    return crud.list_all(session, Investidor, limit=limit, offset=offset)


def get(session: Session, investidor_id: int) -> Investidor | None:
    return crud.get(session, Investidor, investidor_id)


def create(
    session: Session, data: InvestidorCreate, actor_id: int | None = None
) -> Investidor:
    return crud.create(session, Investidor, data, actor_id)


def update(
    session: Session,
    obj: Investidor,
    data: InvestidorUpdate,
    actor_id: int | None = None,
) -> Investidor:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Investidor, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)
