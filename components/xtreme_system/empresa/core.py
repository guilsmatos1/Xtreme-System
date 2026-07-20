"""Dados cadastrais da empresa (configurações)."""

from pydantic import BaseModel
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

_CONFIG_ID = 1


class EmpresaConfig(Base):
    __tablename__ = "empresa_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(default="")
    endereco: Mapped[str] = mapped_column(default="")
    bairro: Mapped[str] = mapped_column(default="")
    cidade: Mapped[str] = mapped_column(default="")
    uf: Mapped[str] = mapped_column(default="")
    cnpj: Mapped[str] = mapped_column(default="")
    signatario: Mapped[str] = mapped_column(default="")


class EmpresaConfigUpdate(BaseModel):
    nome: str = ""
    endereco: str = ""
    bairro: str = ""
    cidade: str = ""
    uf: str = ""
    cnpj: str = ""
    signatario: str = ""


def get_config(session: Session) -> EmpresaConfig:
    config = session.get(EmpresaConfig, _CONFIG_ID)
    if config is None:
        config = EmpresaConfig(id=_CONFIG_ID)
        session.add(config)
        crud.flush(session)
        session.refresh(config)
    return config


def atualizar_config(session: Session, data: EmpresaConfigUpdate) -> EmpresaConfig:
    config = get_config(session)
    config.nome = data.nome
    config.endereco = data.endereco
    config.bairro = data.bairro
    config.cidade = data.cidade
    config.uf = data.uf
    config.cnpj = data.cnpj
    config.signatario = data.signatario
    crud.flush(session)
    session.refresh(config)
    return config
