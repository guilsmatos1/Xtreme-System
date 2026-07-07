"""Usuário: enum de papel, model, schemas e CRUD."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.auth.core import hash_password
from xtreme_system.database.core import Base


class Papel(StrEnum):
    admin = "admin"
    leitor = "leitor"


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    senha_hash: Mapped[str]
    papel: Mapped[Papel] = mapped_column(default=Papel.leitor)
    ativo: Mapped[bool] = mapped_column(default=True)


class UsuarioCreate(BaseModel):
    username: str
    senha: str
    papel: Papel = Papel.leitor


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    papel: Papel
    ativo: bool


def list_all(session: Session) -> list[Usuario]:
    return list(session.query(Usuario).all())


def get_by_username(session: Session, username: str) -> Usuario | None:
    return session.query(Usuario).filter_by(username=username).one_or_none()


def create(session: Session, data: UsuarioCreate) -> Usuario:
    obj = Usuario(
        username=data.username,
        senha_hash=hash_password(data.senha),
        papel=data.papel,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
