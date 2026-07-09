"""Imagem de comprovante de compra: model (FK compra), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class ImagemComprovanteCompra(Base):
    __tablename__ = "imagem_comprovante_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    compra_id: Mapped[int] = mapped_column(
        ForeignKey("compra.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class ImagemComprovanteCompraCreate(BaseModel):
    compra_id: int
    url: str


class ImagemComprovanteCompraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    compra_id: int
    url: str


def list_all(session: Session) -> list[ImagemComprovanteCompra]:
    return crud.list_all(session, ImagemComprovanteCompra)


def list_by_compra(session: Session, compra_id: int) -> list[ImagemComprovanteCompra]:
    return list(
        session.query(ImagemComprovanteCompra).filter_by(compra_id=compra_id).all()
    )


def get(session: Session, imagem_id: int) -> ImagemComprovanteCompra | None:
    return crud.get(session, ImagemComprovanteCompra, imagem_id)


def create(
    session: Session, data: ImagemComprovanteCompraCreate
) -> ImagemComprovanteCompra:
    return crud.create(session, ImagemComprovanteCompra, data)


def delete(session: Session, obj: ImagemComprovanteCompra) -> None:
    crud.delete(session, obj)
