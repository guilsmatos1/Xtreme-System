"""Imagem de documento de cliente: model (FK cliente), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class ImagemDocumentoCliente(Base):
    __tablename__ = "imagem_documento_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class ImagemDocumentoClienteCreate(BaseModel):
    cliente_id: int
    url: str


class ImagemDocumentoClienteUpdate(BaseModel):
    url: str | None = None


class ImagemDocumentoClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    url: str


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[ImagemDocumentoCliente]:
    return crud.list_all(session, ImagemDocumentoCliente, limit=limit, offset=offset)


def list_by_cliente(session: Session, cliente_id: int) -> list[ImagemDocumentoCliente]:
    return list(
        session.query(ImagemDocumentoCliente).filter_by(cliente_id=cliente_id).all()
    )


def get(session: Session, imagem_id: int) -> ImagemDocumentoCliente | None:
    return crud.get(session, ImagemDocumentoCliente, imagem_id)


def create(
    session: Session,
    data: ImagemDocumentoClienteCreate,
    actor_id: int | None = None,
) -> ImagemDocumentoCliente:
    return crud.create(session, ImagemDocumentoCliente, data, actor_id)


def update(
    session: Session,
    obj: ImagemDocumentoCliente,
    data: ImagemDocumentoClienteUpdate,
    actor_id: int | None = None,
) -> ImagemDocumentoCliente:
    return crud.update(session, obj, data, actor_id)


def delete(
    session: Session, obj: ImagemDocumentoCliente, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)
