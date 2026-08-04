"""Imagem de contrato de consignação: model (FK consignacao), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import register_upload_file_delete


class ImagemContratoConsignacao(attachment.UrlAttachmentMixin, Base):
    __tablename__ = "imagem_contrato_consignacao"

    consignacao_id: Mapped[int] = mapped_column(
        ForeignKey("consignacao.id", ondelete="CASCADE"), index=True
    )


register_upload_file_delete(ImagemContratoConsignacao)


class ImagemContratoConsignacaoCreate(BaseModel):
    consignacao_id: int
    url: str


class ImagemContratoConsignacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consignacao_id: int
    url: str


list_all = attachment.make_list_all(ImagemContratoConsignacao)
list_by_consignacao = attachment.make_list_by_field(
    ImagemContratoConsignacao, "consignacao_id"
)
list_by_consignacao_ids = attachment.make_list_by_field_ids(
    ImagemContratoConsignacao, "consignacao_id"
)
get = attachment.make_get(ImagemContratoConsignacao)
create = attachment.make_create(
    ImagemContratoConsignacao, ImagemContratoConsignacaoCreate
)
delete = attachment.make_delete(ImagemContratoConsignacao)
