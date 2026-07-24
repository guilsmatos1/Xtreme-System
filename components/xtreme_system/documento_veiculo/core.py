"""Documento de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import schedule_uploaded_file_delete


class DocumentoVeiculo(Base):
    __tablename__ = "documento_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


@event.listens_for(DocumentoVeiculo, "after_delete")
def _delete_upload_file(
    _mapper: object, _connection: object, target: DocumentoVeiculo
) -> None:
    schedule_uploaded_file_delete(target)


class DocumentoVeiculoCreate(BaseModel):
    veiculo_id: int
    url: str


class DocumentoVeiculoUpdate(BaseModel):
    url: str | None = None


class DocumentoVeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    veiculo_id: int
    url: str


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[DocumentoVeiculo]:
    return crud.list_all(session, DocumentoVeiculo, limit=limit, offset=offset)


def list_by_veiculo(session: Session, veiculo_id: int) -> list[DocumentoVeiculo]:
    return list(session.query(DocumentoVeiculo).filter_by(veiculo_id=veiculo_id).all())


def get(session: Session, documento_id: int) -> DocumentoVeiculo | None:
    return crud.get(session, DocumentoVeiculo, documento_id)


def create(
    session: Session, data: DocumentoVeiculoCreate, actor_id: int | None = None
) -> DocumentoVeiculo:
    return crud.create(session, DocumentoVeiculo, data, actor_id)


def update(
    session: Session,
    obj: DocumentoVeiculo,
    data: DocumentoVeiculoUpdate,
    actor_id: int | None = None,
) -> DocumentoVeiculo:
    return crud.update(session, obj, data, actor_id)


def delete(
    session: Session, obj: DocumentoVeiculo, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)
