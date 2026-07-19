"""Investidor: model, schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class Investidor(Base):
    __tablename__ = "investidor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)


class InvestidorCreate(BaseModel):
    nome: str


class InvestidorUpdate(BaseModel):
    nome: str | None = None


class InvestidorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


def list_all(session: Session) -> list[Investidor]:
    return crud.list_all(session, Investidor)


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
