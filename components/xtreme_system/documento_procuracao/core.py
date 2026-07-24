"""Documento de procuração de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base


class DocumentoProcuracao(Base):
    __tablename__ = "documento_procuracao"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class DocumentoProcuracaoCreate(BaseModel):
    veiculo_id: int
    url: str


class DocumentoProcuracaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    veiculo_id: int
    url: str


list_all = attachment.make_list_all(DocumentoProcuracao)
list_by_veiculo = attachment.make_list_by_field(DocumentoProcuracao, "veiculo_id")
get = attachment.make_get(DocumentoProcuracao)
create = attachment.make_create(DocumentoProcuracao, DocumentoProcuracaoCreate)
delete = attachment.make_delete(DocumentoProcuracao)
