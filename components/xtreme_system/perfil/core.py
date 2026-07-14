"""Perfil de permissões: quais páginas da UI um perfil de usuário pode acessar."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

# Única fonte da verdade: chave usada na URL (/ui/{chave}) e no menu.
PAGINAS: list[tuple[str, str]] = [
    ("veiculos", "Veículos"),
    ("investidores", "Investidores"),
    ("clientes", "Clientes"),
    ("compras", "Compras"),
    ("custos-veiculos", "Custos"),
    ("vendas", "Vendas"),
]
PAGINAS_VALIDAS = {chave for chave, _ in PAGINAS}


class Perfil(Base):
    __tablename__ = "perfil"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)
    paginas: Mapped[list[str]] = mapped_column(JSON, default=list)


class PerfilCreate(BaseModel):
    nome: str
    paginas: list[str] = []


class PerfilUpdate(BaseModel):
    nome: str | None = None
    paginas: list[str] | None = None


class PerfilRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    paginas: list[str]


def list_all(session: Session) -> list[Perfil]:
    return crud.list_all(session, Perfil)


def get(session: Session, perfil_id: int) -> Perfil | None:
    return crud.get(session, Perfil, perfil_id)


def create(session: Session, data: PerfilCreate) -> Perfil:
    return crud.create(session, Perfil, data)


def update(session: Session, obj: Perfil, data: PerfilUpdate) -> Perfil:
    return crud.update(session, obj, data)


def delete(session: Session, obj: Perfil) -> None:
    from xtreme_system.usuario.core import Usuario  # noqa: PLC0415 (import circular)

    for user in session.query(Usuario).filter_by(perfil_id=obj.id):
        user.perfil_id = None
    session.flush()
    crud.delete(session, obj)


def pagina_da_rota(path: str) -> str | None:
    if not path.startswith("/ui/"):
        return None
    segmento = path.removeprefix("/ui/").split("/", 1)[0]
    return segmento if segmento in PAGINAS_VALIDAS else None


def pode_acessar(user: Any, pagina: str) -> bool:
    if user.papel.value == "admin":
        return True
    return bool(user.perfil and pagina in user.perfil.paginas)
