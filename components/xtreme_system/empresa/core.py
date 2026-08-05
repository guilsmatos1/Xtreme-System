"""Dados cadastrais da empresa (configurações)."""

from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

_CAMPOS_TEXTO = (
    "nome",
    "endereco",
    "bairro",
    "cidade",
    "uf",
    "cep",
    "telefone",
    "cnpj",
    "signatario",
)

_CONFIG_ID = 1


class EmpresaConfig(Base):  # pylint: disable=too-many-instance-attributes
    __tablename__ = "empresa_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(default="", server_default="")
    endereco: Mapped[str] = mapped_column(default="", server_default="")
    bairro: Mapped[str] = mapped_column(default="", server_default="")
    cidade: Mapped[str] = mapped_column(default="", server_default="")
    uf: Mapped[str] = mapped_column(default="", server_default="")
    cep: Mapped[str] = mapped_column(default="", server_default="")
    telefone: Mapped[str] = mapped_column(default="", server_default="")
    cnpj: Mapped[str] = mapped_column(default="", server_default="")
    signatario: Mapped[str] = mapped_column(default="", server_default="")
    # Fora de EmpresaConfigUpdate: o form de texto não envia o logo e apagaria a URL.
    logo_url: Mapped[str] = mapped_column(default="", server_default="")


class EmpresaConfigUpdate(BaseModel):
    nome: str = ""
    endereco: str = ""
    bairro: str = ""
    cidade: str = ""
    uf: str = ""
    cep: str = ""
    telefone: str = ""
    cnpj: str = ""
    signatario: str = ""

    @field_validator(*_CAMPOS_TEXTO, mode="before")
    @classmethod
    def _normalizar_texto(cls, value: object) -> object:
        _ = cls
        return crud.trim_texto(value)

    @field_validator("uf", mode="before")
    @classmethod
    def _normalizar_uf(cls, value: object) -> object:
        _ = cls
        return value.strip().upper() if isinstance(value, str) else value


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
    config.cep = data.cep
    config.telefone = data.telefone
    config.cnpj = data.cnpj
    config.signatario = data.signatario
    crud.flush(session)
    session.refresh(config)
    return config


def definir_logo(session: Session, url: str) -> EmpresaConfig:
    config = get_config(session)
    config.logo_url = url
    crud.flush(session)
    session.refresh(config)
    return config


def remover_logo(session: Session) -> EmpresaConfig:
    return definir_logo(session, "")
