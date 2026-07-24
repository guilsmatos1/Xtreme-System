"""Cliente: enum de tipo, model, schemas e CRUD."""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

if TYPE_CHECKING:
    from xtreme_system.imagem_documento_cliente.core import ImagemDocumentoCliente


class TipoCliente(StrEnum):
    pessoa_fisica = "pessoa_fisica"
    pessoa_juridica = "pessoa_juridica"


class Cliente(Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(index=True)
    documento: Mapped[str] = mapped_column(unique=True, index=True)
    tipo: Mapped[TipoCliente]
    email: Mapped[str | None]
    telefone: Mapped[str | None]
    endereco: Mapped[str | None]
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
    endereco: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    profissao: str | None = None


class ClienteUpdate(BaseModel):
    nome: str | None = None
    documento: str | None = None
    tipo: TipoCliente | None = None
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    profissao: str | None = None


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    documento: str
    tipo: TipoCliente
    email: str | None
    telefone: str | None
    endereco: str | None
    bairro: str | None
    cidade: str | None
    estado: str | None
    cep: str | None
    profissao: str | None


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Cliente]:
    return crud.list_all(session, Cliente, limit=limit, offset=offset)


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
    return list(_search_com_vinculo(session, term, column).all())


def list_compradores(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Cliente]:
    from xtreme_system.venda.core import Venda  # noqa: PLC0415

    query = session.query(Cliente).join(Venda).distinct().order_by(Cliente.id)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    return list(query.all())


def search_compradores(
    session: Session, term: str, column: str | None = None
) -> list[Cliente]:
    from xtreme_system.venda.core import Venda  # noqa: PLC0415

    return list(_search_com_vinculo(session, term, column).join(Venda).distinct().all())


def list_vendedores(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Cliente]:
    from xtreme_system.compra.core import Compra  # noqa: PLC0415

    query = session.query(Cliente).join(Compra).distinct().order_by(Cliente.id)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    return list(query.all())


def search_vendedores(
    session: Session, term: str, column: str | None = None
) -> list[Cliente]:
    from xtreme_system.compra.core import Compra  # noqa: PLC0415

    return list(
        _search_com_vinculo(session, term, column).join(Compra).distinct().all()
    )


def _search_com_vinculo(session: Session, term: str, column: str | None = None) -> Any:
    pattern = f"%{term}%"

    if column and column in _COLUNAS_BUSCA:
        col = _COLUNAS_BUSCA[column]
        return session.query(Cliente).where(cast(col, String).ilike(pattern))

    return session.query(Cliente).where(
        or_(
            Cliente.nome.ilike(pattern),
            Cliente.documento.ilike(pattern),
            Cliente.cidade.ilike(pattern),
            Cliente.estado.ilike(pattern),
        )
    )
