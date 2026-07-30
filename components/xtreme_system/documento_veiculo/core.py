"""Documento de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import register_upload_file_delete


class DocumentoVeiculo(attachment.UrlAttachmentMixin, Base):
    __tablename__ = "documento_veiculo"

    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )


register_upload_file_delete(DocumentoVeiculo)


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


list_all = attachment.make_list_all(DocumentoVeiculo)
list_by_veiculo = attachment.make_list_by_field(DocumentoVeiculo, "veiculo_id")
get = attachment.make_get(DocumentoVeiculo)
create = attachment.make_create(DocumentoVeiculo, DocumentoVeiculoCreate)
update = attachment.make_update(DocumentoVeiculo, DocumentoVeiculoUpdate)
delete = attachment.make_delete(DocumentoVeiculo)
