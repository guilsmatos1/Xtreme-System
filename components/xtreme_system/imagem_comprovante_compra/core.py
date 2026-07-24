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


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[ImagemComprovanteCompra]:
    return crud.list_all(session, ImagemComprovanteCompra, limit=limit, offset=offset)


def list_by_compra(session: Session, compra_id: int) -> list[ImagemComprovanteCompra]:
    return list(
        session.query(ImagemComprovanteCompra).filter_by(compra_id=compra_id).all()
    )


def list_by_compra_ids(
    session: Session, compra_ids: list[int]
) -> list[ImagemComprovanteCompra]:
    if not compra_ids:
        return []
    return list(
        session.query(ImagemComprovanteCompra)
        .filter(ImagemComprovanteCompra.compra_id.in_(compra_ids))
        .order_by(ImagemComprovanteCompra.compra_id, ImagemComprovanteCompra.id)
        .all()
    )


def get(session: Session, imagem_id: int) -> ImagemComprovanteCompra | None:
    return crud.get(session, ImagemComprovanteCompra, imagem_id)


def create(
    session: Session,
    data: ImagemComprovanteCompraCreate,
    actor_id: int | None = None,
) -> ImagemComprovanteCompra:
    return crud.create(session, ImagemComprovanteCompra, data, actor_id)


def delete(
    session: Session, obj: ImagemComprovanteCompra, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)
