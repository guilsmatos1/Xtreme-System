"""Documento de contrato de venda: model (FK venda), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class DocumentoContratoVenda(Base):
    __tablename__ = "documento_contrato_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class DocumentoContratoVendaCreate(BaseModel):
    venda_id: int
    url: str


class DocumentoContratoVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda_id: int
    url: str


def list_all(session: Session) -> list[DocumentoContratoVenda]:
    return crud.list_all(session, DocumentoContratoVenda)


def list_by_venda(session: Session, venda_id: int) -> list[DocumentoContratoVenda]:
    return list(
        session.query(DocumentoContratoVenda).filter_by(venda_id=venda_id).all()
    )


def get(session: Session, documento_id: int) -> DocumentoContratoVenda | None:
    return crud.get(session, DocumentoContratoVenda, documento_id)


def create(
    session: Session, data: DocumentoContratoVendaCreate
) -> DocumentoContratoVenda:
    return crud.create(session, DocumentoContratoVenda, data)


def delete(session: Session, obj: DocumentoContratoVenda) -> None:
    crud.delete(session, obj)
