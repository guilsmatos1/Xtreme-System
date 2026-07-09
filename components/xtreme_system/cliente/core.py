"""Cliente: enum de tipo, model, schemas e CRUD."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base


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
    cidade: Mapped[str | None]
    estado: Mapped[str | None]
    cep: Mapped[str | None]
    ativo: Mapped[bool] = mapped_column(default=True)


class ClienteCreate(BaseModel):
    nome: str
    documento: str
    tipo: TipoCliente
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    ativo: bool = True


class ClienteUpdate(BaseModel):
    nome: str | None = None
    documento: str | None = None
    tipo: TipoCliente | None = None
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    cep: str | None = None
    ativo: bool | None = None


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    documento: str
    tipo: TipoCliente
    email: str | None
    telefone: str | None
    endereco: str | None
    cidade: str | None
    estado: str | None
    cep: str | None
    ativo: bool


def list_all(session: Session) -> list[Cliente]:
    return crud.list_all(session, Cliente)


def get(session: Session, cliente_id: int) -> Cliente | None:
    return crud.get(session, Cliente, cliente_id)


def create(session: Session, data: ClienteCreate) -> Cliente:
    return crud.create(session, Cliente, data)


def update(session: Session, obj: Cliente, data: ClienteUpdate) -> Cliente:
    return crud.update(session, obj, data)


def delete(session: Session, obj: Cliente) -> None:
    crud.delete(session, obj)


def search(session: Session, term: str) -> list[Cliente]:
    pattern = f"%{term}%"
    return list(
        session.query(Cliente)
        .where(
            or_(
                Cliente.nome.ilike(pattern),
                Cliente.documento.ilike(pattern),
                Cliente.cidade.ilike(pattern),
                Cliente.estado.ilike(pattern),
            )
        )
        .all()
    )
