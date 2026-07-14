"""Documento de procuração de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class DocumentoProcuracao(Base):
    __tablename__ = "documento_procuracao"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class DocumentoProcuracaoCreate(BaseModel):
    veiculo_id: int
    url: str


class DocumentoProcuracaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    veiculo_id: int
    url: str


def list_all(session: Session) -> list[DocumentoProcuracao]:
    return crud.list_all(session, DocumentoProcuracao)


def list_by_veiculo(session: Session, veiculo_id: int) -> list[DocumentoProcuracao]:
    return list(
        session.query(DocumentoProcuracao).filter_by(veiculo_id=veiculo_id).all()
    )


def get(session: Session, documento_id: int) -> DocumentoProcuracao | None:
    return crud.get(session, DocumentoProcuracao, documento_id)


def create(session: Session, data: DocumentoProcuracaoCreate) -> DocumentoProcuracao:
    return crud.create(session, DocumentoProcuracao, data)


def delete(session: Session, obj: DocumentoProcuracao) -> None:
    crud.delete(session, obj)
