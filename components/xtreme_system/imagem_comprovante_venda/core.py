"""Imagem de comprovante de venda: model (FK venda), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


class ImagemComprovanteVenda(Base):
    __tablename__ = "imagem_comprovante_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class ImagemComprovanteVendaCreate(BaseModel):
    venda_id: int
    url: str


class ImagemComprovanteVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda_id: int
    url: str


def list_all(session: Session) -> list[ImagemComprovanteVenda]:
    return crud.list_all(session, ImagemComprovanteVenda)


def list_by_venda(session: Session, venda_id: int) -> list[ImagemComprovanteVenda]:
    return list(
        session.query(ImagemComprovanteVenda).filter_by(venda_id=venda_id).all()
    )


def get(session: Session, imagem_id: int) -> ImagemComprovanteVenda | None:
    return crud.get(session, ImagemComprovanteVenda, imagem_id)


def create(
    session: Session,
    data: ImagemComprovanteVendaCreate,
    actor_id: int | None = None,
) -> ImagemComprovanteVenda:
    return crud.create(session, ImagemComprovanteVenda, data, actor_id)


def delete(
    session: Session, obj: ImagemComprovanteVenda, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)
