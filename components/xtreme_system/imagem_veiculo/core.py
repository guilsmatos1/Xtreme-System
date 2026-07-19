"""Imagem de veículo: model (FK veiculo), schemas e CRUD."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
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


def list_all(session: Session) -> list[ImagemVeiculo]:
    return crud.list_all(session, ImagemVeiculo)


def list_by_veiculo(session: Session, veiculo_id: int) -> list[ImagemVeiculo]:
    return list(session.query(ImagemVeiculo).filter_by(veiculo_id=veiculo_id).all())


def get(session: Session, imagem_id: int) -> ImagemVeiculo | None:
    return crud.get(session, ImagemVeiculo, imagem_id)


def create(
    session: Session, data: ImagemVeiculoCreate, actor_id: int | None = None
) -> ImagemVeiculo:
    return crud.create(session, ImagemVeiculo, data, actor_id)


def update(
    session: Session,
    obj: ImagemVeiculo,
    data: ImagemVeiculoUpdate,
    actor_id: int | None = None,
) -> ImagemVeiculo:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: ImagemVeiculo, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)
