"""Imagem de documento de cliente: model (FK cliente), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import schedule_uploaded_file_delete


class ImagemDocumentoCliente(Base):
    __tablename__ = "imagem_documento_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


@event.listens_for(ImagemDocumentoCliente, "after_delete")
def _delete_upload_file(
    _mapper: object, _connection: object, target: ImagemDocumentoCliente
) -> None:
    schedule_uploaded_file_delete(target)


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


list_all = attachment.make_list_all(ImagemDocumentoCliente)
list_by_cliente = attachment.make_list_by_field(ImagemDocumentoCliente, "cliente_id")
get = attachment.make_get(ImagemDocumentoCliente)
create = attachment.make_create(ImagemDocumentoCliente, ImagemDocumentoClienteCreate)
update = attachment.make_update(ImagemDocumentoCliente, ImagemDocumentoClienteUpdate)
delete = attachment.make_delete(ImagemDocumentoCliente)
