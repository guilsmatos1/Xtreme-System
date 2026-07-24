"""Imagem de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base


class ImagemVeiculo(Base):
    __tablename__ = "imagem_veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class ImagemVeiculoCreate(BaseModel):
    veiculo_id: int
    url: str


class ImagemVeiculoUpdate(BaseModel):
    url: str | None = None


class ImagemVeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    veiculo_id: int
    url: str


list_all = attachment.make_list_all(ImagemVeiculo)
list_by_veiculo = attachment.make_list_by_field(ImagemVeiculo, "veiculo_id")
get = attachment.make_get(ImagemVeiculo)
create = attachment.make_create(ImagemVeiculo, ImagemVeiculoCreate)
update = attachment.make_update(ImagemVeiculo, ImagemVeiculoUpdate)
delete = attachment.make_delete(ImagemVeiculo)
