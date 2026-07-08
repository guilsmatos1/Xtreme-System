"""Meio de captação da venda: model, schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
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
    return crud.list_all(session, MeioCaptacao)


def get(session: Session, meio_id: int) -> MeioCaptacao | None:
    return crud.get(session, MeioCaptacao, meio_id)


def create(session: Session, data: MeioCaptacaoCreate) -> MeioCaptacao:
    return crud.create(session, MeioCaptacao, data)


def update(
    session: Session, obj: MeioCaptacao, data: MeioCaptacaoUpdate
) -> MeioCaptacao:
    return crud.update(session, obj, data)


def delete(session: Session, obj: MeioCaptacao) -> None:
    crud.delete(session, obj)
