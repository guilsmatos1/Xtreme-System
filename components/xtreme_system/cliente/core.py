"""Cliente: enum de tipo, model, schemas e CRUD."""

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy.orm import Mapped, Query, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.crud.search import apply_text_search
from xtreme_system.database.core import Base

if TYPE_CHECKING:
    from xtreme_system.imagem_documento_cliente.core import ImagemDocumentoCliente


class TipoCliente(StrEnum):
    pessoa_fisica = "pessoa_fisica"
    pessoa_juridica = "pessoa_juridica"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UF_RE = re.compile(r"^[A-Z]{2}$")
_CEP_LENGTH = 8


class DocumentoClienteInvalidoError(ValueError):
    def __init__(self) -> None:
        super().__init__("Documento do cliente inválido")


class EmailClienteInvalidoError(ValueError):
    def __init__(self) -> None:
        super().__init__("E-mail do cliente inválido")


class EstadoClienteInvalidoError(ValueError):
    def __init__(self) -> None:
        super().__init__("Estado do cliente inválido")


class CepClienteInvalidoError(ValueError):
    def __init__(self) -> None:
        super().__init__("CEP do cliente inválido")


class CampoClienteObrigatorioError(ValueError):
    def __init__(self) -> None:
        super().__init__("Campo obrigatório")


class TipoClienteInvalidoError(ValueError):
    def __init__(self) -> None:
        super().__init__("Tipo do cliente inválido")


def _trim_texto(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _trim_str(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _trim_texto_obrigatorio(value: Any) -> Any:
    value = _trim_texto(value)
    if value is None:
        raise CampoClienteObrigatorioError
    return value


def _trim_texto_uppercase(value: Any) -> Any:
    value = _trim_texto(value)
    if isinstance(value, str):
        return value.upper()
    return value


def _trim_texto_obrigatorio_uppercase(value: Any) -> Any:
    value = _trim_texto_obrigatorio(value)
    if isinstance(value, str):
        return value.upper()
    return value


def _digits(value: str | None) -> str | None:
    if value is None:
        return None
    normalizado = re.sub(r"\D", "", value)
    return normalizado or None


def normalizar_documento(value: str | None) -> str | None:
    return _digits(value)


def normalizar_telefone(value: str | None) -> str | None:
    return _digits(value)


_CPF_LEN = 11
_CNPJ_LEN = 14


def formatar_documento(value: str | None) -> str:
    """CPF (11 dígitos) -> 000.000.000-00; CNPJ (14 dígitos) -> 00.000.000/0000-00."""
    digitos = _digits(value)
    if digitos is None:
        return "-"
    if len(digitos) == _CPF_LEN:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == _CNPJ_LEN:
        return (
            f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}"
            f"/{digitos[8:12]}-{digitos[12:]}"
        )
    return value or "-"


_TELEFONE_FIXO_LEN = 10
_TELEFONE_CELULAR_LEN = 11


def formatar_telefone(value: str | None) -> str:
    """(DDD) XXXXX-XXXX para celular (11 dígitos) ou (DDD) XXXX-XXXX para fixo (10)."""
    digitos = _digits(value)
    if digitos is None:
        return "-"
    if len(digitos) == _TELEFONE_CELULAR_LEN:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == _TELEFONE_FIXO_LEN:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return value or "-"


def normalizar_cep(value: str | None) -> str | None:
    cep = _digits(value)
    if cep is not None and len(cep) != _CEP_LENGTH:
        raise CepClienteInvalidoError
    return cep


def formatar_cep(value: str | None) -> str:
    """00000-000."""
    digitos = _digits(value)
    if digitos is None:
        return "-"
    if len(digitos) == _CEP_LENGTH:
        return f"{digitos[:5]}-{digitos[5:]}"
    return value or "-"


def normalizar_estado(value: str | None) -> str | None:
    estado = _trim_str(value)
    if estado is None:
        return None
    estado = estado.upper()
    if not _UF_RE.fullmatch(estado):
        raise EstadoClienteInvalidoError
    return estado


def normalizar_email(value: str | None) -> str | None:
    email = _trim_str(value)
    if email is None:
        return None
    email = email.upper()
    if not _EMAIL_RE.fullmatch(email.lower()):
        raise EmailClienteInvalidoError
    return email


def _validar_documento_por_tipo(
    documento: str | None, tipo: TipoCliente | None
) -> None:
    if documento is None:
        return
    tamanhos_validos = (
        {11, 14} if tipo is None else {11 if tipo is TipoCliente.pessoa_fisica else 14}
    )
    if len(documento) not in tamanhos_validos:
        raise DocumentoClienteInvalidoError


class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(index=True)
    documento: Mapped[str] = mapped_column(unique=True, index=True)
    tipo: Mapped[TipoCliente]
    email: Mapped[str | None]
    telefone: Mapped[str | None]
    telefone2: Mapped[str | None]
    endereco: Mapped[str | None]
    complemento: Mapped[str | None]
    bairro: Mapped[str | None]
    cidade: Mapped[str | None]
    estado: Mapped[str | None]
    cep: Mapped[str | None]
    profissao: Mapped[str | None]

    documentos: Mapped[list["ImagemDocumentoCliente"]] = relationship(
        cascade="all, delete-orphan"
    )


class ClienteCreate(BaseModel):
    nome: str
    documento: str
    tipo: TipoCliente
    email: str | None = None
    telefone: str | None = None
    telefone2: str | None = None
    endereco: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    profissao: str | None = None

    @field_validator("nome", mode="before")
    @classmethod
    def _normalizar_nome(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto_obrigatorio_uppercase(value)

    @field_validator("documento", mode="before")
    @classmethod
    def _normalizar_documento(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_documento(value)

    @field_validator("email", mode="before")
    @classmethod
    def _normalizar_email(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_email(value)

    @field_validator("telefone", mode="before")
    @classmethod
    def _normalizar_telefone(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_telefone(value)

    @field_validator("telefone2", mode="before")
    @classmethod
    def _normalizar_telefone2(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_telefone(value)

    @field_validator("endereco", "complemento", "bairro", "cidade", mode="before")
    @classmethod
    def _normalizar_endereco(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto_uppercase(value)

    @field_validator("profissao", mode="before")
    @classmethod
    def _normalizar_texto_opcional(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto(value)

    @field_validator("estado", mode="before")
    @classmethod
    def _normalizar_estado(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_estado(value)

    @field_validator("cep", mode="before")
    @classmethod
    def _normalizar_cep(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_cep(value)

    @model_validator(mode="after")
    def _validar_documento(self) -> "ClienteCreate":
        _validar_documento_por_tipo(self.documento, self.tipo)
        return self


class ClienteUpdate(BaseModel):
    nome: str | None = None
    documento: str | None = None
    tipo: TipoCliente | None = None
    email: str | None = None
    telefone: str | None = None
    telefone2: str | None = None
    endereco: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    profissao: str | None = None

    @field_validator("nome", mode="before")
    @classmethod
    def _normalizar_nome(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto_obrigatorio_uppercase(value)

    @field_validator("documento", mode="before")
    @classmethod
    def _normalizar_documento(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_documento(value)

    @field_validator("email", mode="before")
    @classmethod
    def _normalizar_email(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_email(value)

    @field_validator("telefone", mode="before")
    @classmethod
    def _normalizar_telefone(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_telefone(value)

    @field_validator("telefone2", mode="before")
    @classmethod
    def _normalizar_telefone2(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_telefone(value)

    @field_validator("endereco", "complemento", "bairro", "cidade", mode="before")
    @classmethod
    def _normalizar_endereco(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto_uppercase(value)

    @field_validator("profissao", mode="before")
    @classmethod
    def _normalizar_texto_opcional(cls, value: Any) -> Any:
        _ = cls
        return _trim_texto(value)

    @field_validator("estado", mode="before")
    @classmethod
    def _normalizar_estado(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_estado(value)

    @field_validator("cep", mode="before")
    @classmethod
    def _normalizar_cep(cls, value: str | None) -> str | None:
        _ = cls
        return normalizar_cep(value)

    @model_validator(mode="after")
    def _validar_documento(self) -> "ClienteUpdate":
        if "documento" in self.model_fields_set and self.documento is None:
            raise DocumentoClienteInvalidoError
        if "tipo" in self.model_fields_set and self.tipo is None:
            raise TipoClienteInvalidoError
        _validar_documento_por_tipo(self.documento, self.tipo)
        return self


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    documento: str
    tipo: TipoCliente
    email: str | None
    telefone: str | None
    telefone2: str | None
    endereco: str | None
    bairro: str | None
    cidade: str | None
    estado: str | None
    cep: str | None
    profissao: str | None


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Cliente]:
    q = session.query(Cliente).order_by(Cliente.nome)
    if limit is not None:
        q = q.limit(limit)
    if offset:
        q = q.offset(offset)
    return list(q.all())


def query(session: Session) -> Query[Cliente]:
    return session.query(Cliente)


def get(session: Session, cliente_id: int) -> Cliente | None:
    return crud.get(session, Cliente, cliente_id)


def get_by_documento(session: Session, documento: str) -> Cliente | None:
    return session.query(Cliente).filter_by(documento=documento).one_or_none()


def create(
    session: Session, data: ClienteCreate, actor_id: int | None = None
) -> Cliente:
    return crud.create(session, Cliente, data, actor_id)


def update(
    session: Session, obj: Cliente, data: ClienteUpdate, actor_id: int | None = None
) -> Cliente:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Cliente, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


_COLUNAS_BUSCA = {
    "nome": Cliente.nome,
    "documento": Cliente.documento,
    "telefone": Cliente.telefone,
    "tipo": Cliente.tipo,
    "cidade": Cliente.cidade,
    "estado": Cliente.estado,
}


def search(session: Session, term: str, column: str | None = None) -> list[Cliente]:
    return list(search_query(session, term, column).all())


def search_query(
    session: Session, term: str, column: str | None = None
) -> Query[Cliente]:
    return _search_com_vinculo(session, term, column)


def _search_com_vinculo(
    session: Session, term: str, column: str | None = None
) -> Query[Cliente]:
    return apply_text_search(
        session.query(Cliente),
        term,
        columns_map=_COLUNAS_BUSCA,
        default_columns=(
            Cliente.nome,
            Cliente.documento,
            Cliente.cidade,
            Cliente.estado,
        ),
        column=column,
    )
