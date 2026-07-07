"""Meio de captação da venda: model, schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.database.core import Base


class MeioCaptacao(Base):
    __tablename__ = "meio_captacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)


class MeioCaptacaoCreate(BaseModel):
    nome: str


class MeioCaptacaoUpdate(BaseModel):
    nome: str | None = None


class MeioCaptacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


def list_all(session: Session) -> list[MeioCaptacao]:
    return list(session.query(MeioCaptacao).all())


def get(session: Session, meio_id: int) -> MeioCaptacao | None:
    return session.get(MeioCaptacao, meio_id)


def create(session: Session, data: MeioCaptacaoCreate) -> MeioCaptacao:
    obj = MeioCaptacao(**data.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def update(
    session: Session, obj: MeioCaptacao, data: MeioCaptacaoUpdate
) -> MeioCaptacao:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: MeioCaptacao) -> None:
    session.delete(obj)
    session.commit()
