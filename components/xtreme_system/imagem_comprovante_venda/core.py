"""Imagem de comprovante de venda: model (FK venda), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import schedule_uploaded_file_delete


class ImagemComprovanteVenda(Base):
    __tablename__ = "imagem_comprovante_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


@event.listens_for(ImagemComprovanteVenda, "after_delete")
def _delete_upload_file(
    _mapper: object, _connection: object, target: ImagemComprovanteVenda
) -> None:
    schedule_uploaded_file_delete(target)


class ImagemComprovanteVendaCreate(BaseModel):
    venda_id: int
    url: str


class ImagemComprovanteVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda_id: int
    url: str


list_all = attachment.make_list_all(ImagemComprovanteVenda)
list_by_venda = attachment.make_list_by_field(ImagemComprovanteVenda, "venda_id")
get = attachment.make_get(ImagemComprovanteVenda)
create = attachment.make_create(ImagemComprovanteVenda, ImagemComprovanteVendaCreate)
delete = attachment.make_delete(ImagemComprovanteVenda)
