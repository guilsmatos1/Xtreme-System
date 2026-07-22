"""Configuração da empresa: logo único (singleton, id fixo)."""

from pydantic import BaseModel
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

_CONFIG_ID = 1


class EmpresaConfig(Base):
    __tablename__ = "empresa_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    logo_url: Mapped[str] = mapped_column(default="")


class EmpresaLogoCreate(BaseModel):
    id: int
    url: str


def get_config(session: Session) -> EmpresaConfig:
    config = session.get(EmpresaConfig, _CONFIG_ID)
    if config is None:
        config = EmpresaConfig(id=_CONFIG_ID)
        session.add(config)
        crud.flush(session)
        session.refresh(config)
    return config


def definir_logo(
    session: Session, data: EmpresaLogoCreate, _actor_id: int | None = None
) -> EmpresaConfig:
    config = get_config(session)
    config.logo_url = data.url
    crud.flush(session)
    session.refresh(config)
    return config


def remover_logo(session: Session) -> EmpresaConfig:
    config = get_config(session)
    config.logo_url = ""
    crud.flush(session)
    session.refresh(config)
    return config
