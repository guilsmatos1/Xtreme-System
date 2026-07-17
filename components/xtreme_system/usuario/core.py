"""Usuário: enum de papel, model, schemas e CRUD."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.auth.core import hash_password
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.perfil.core import Perfil


class Papel(StrEnum):
    admin = "admin"
    funcionario = "funcionario"


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    senha_hash: Mapped[str]
    papel: Mapped[Papel] = mapped_column(default=Papel.funcionario)
    ativo: Mapped[bool] = mapped_column(default=True)
    perfil_id: Mapped[int | None] = mapped_column(ForeignKey("perfil.id"), index=True)
    perfil: Mapped[Perfil | None] = relationship()


def is_admin(user: Usuario) -> bool:
    return user.papel == Papel.admin


class UsuarioCreate(BaseModel):
    username: str
    senha: str
    papel: Papel = Papel.funcionario
    perfil_id: int | None = None


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    papel: Papel
    ativo: bool
    perfil_id: int | None


def list_all(session: Session) -> list[Usuario]:
    return list(session.query(Usuario).all())


def get_by_username(session: Session, username: str) -> Usuario | None:
    return session.query(Usuario).filter_by(username=username).one_or_none()


def create(session: Session, data: UsuarioCreate) -> Usuario:
    obj = Usuario(
        username=data.username,
        senha_hash=hash_password(data.senha),
        papel=data.papel,
        perfil_id=data.perfil_id,
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        tabela="usuario",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)
    return obj


def get(session: Session, usuario_id: int) -> Usuario | None:
    return crud.get(session, Usuario, usuario_id)


def delete(session: Session, obj: Usuario) -> None:
    crud.delete(session, obj)


def change_password(session: Session, obj: Usuario, nova_senha: str) -> None:
    antes = snapshot(obj)
    obj.senha_hash = hash_password(nova_senha)
    session.flush()
    auditar(
        session,
        tabela="usuario",
        tipo_acao="UPDATE",
        registro_id=obj.id,
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)


def set_perfil(session: Session, obj: Usuario, perfil_id: int | None) -> None:
    antes = snapshot(obj)
    obj.perfil_id = perfil_id
    session.flush()
    auditar(
        session,
        tabela="usuario",
        tipo_acao="UPDATE",
        registro_id=obj.id,
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)
