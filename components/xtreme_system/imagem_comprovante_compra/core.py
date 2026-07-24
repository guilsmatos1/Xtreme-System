"""Imagem de comprovante de compra: model (FK compra), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
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


list_all = attachment.make_list_all(ImagemComprovanteCompra)
list_by_compra = attachment.make_list_by_field(ImagemComprovanteCompra, "compra_id")
list_by_compra_ids = attachment.make_list_by_field_ids(
    ImagemComprovanteCompra, "compra_id"
)
get = attachment.make_get(ImagemComprovanteCompra)
create = attachment.make_create(ImagemComprovanteCompra, ImagemComprovanteCompraCreate)
delete = attachment.make_delete(ImagemComprovanteCompra)
