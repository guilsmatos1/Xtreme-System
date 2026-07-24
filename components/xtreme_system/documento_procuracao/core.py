"""Documento de procuração de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import schedule_uploaded_file_delete


class DocumentoProcuracao(Base):
    __tablename__ = "documento_procuracao"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


@event.listens_for(DocumentoProcuracao, "after_delete")
def _delete_upload_file(
    _mapper: object, _connection: object, target: DocumentoProcuracao
) -> None:
    schedule_uploaded_file_delete(target)


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


def create(
    session: Session, data: DocumentoProcuracaoCreate, actor_id: int | None = None
) -> DocumentoProcuracao:
    return crud.create(session, DocumentoProcuracao, data, actor_id)


def delete(
    session: Session, obj: DocumentoProcuracao, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)
