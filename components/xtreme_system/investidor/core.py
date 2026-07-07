"""Investidor: model, schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, Session, mapped_column

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
    return list(session.query(Investidor).all())


def get(session: Session, investidor_id: int) -> Investidor | None:
    return session.get(Investidor, investidor_id)


def create(session: Session, data: InvestidorCreate) -> Investidor:
    obj = Investidor(**data.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update(session: Session, obj: Investidor, data: InvestidorUpdate) -> Investidor:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: Investidor) -> None:
    session.delete(obj)
    session.commit()
