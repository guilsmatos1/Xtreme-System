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
    nome: Mapped[str | None] = mapped_column(default=None)
    senha_hash: Mapped[str]
    papel: Mapped[Papel] = mapped_column(default=Papel.funcionario)
    ativo: Mapped[bool] = mapped_column(default=True)
    perfil_id: Mapped[int | None] = mapped_column(ForeignKey("perfil.id"), index=True)
    perfil: Mapped[Perfil | None] = relationship()


def is_admin(user: Usuario) -> bool:
    return user.papel == Papel.admin


class UsuarioCreate(BaseModel):
    username: str
    nome: str | None = None
    senha: str
    papel: Papel = Papel.funcionario
    perfil_id: int | None = None


class UsuarioUpdate(BaseModel):
    username: str
    nome: str | None = None
    papel: Papel = Papel.funcionario
    ativo: bool = True
    perfil_id: int | None = None


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nome: str | None
    papel: Papel
    ativo: bool
    perfil_id: int | None


def list_all(session: Session) -> list[Usuario]:
    return list(session.query(Usuario).all())


def get_by_username(session: Session, username: str) -> Usuario | None:
    return session.query(Usuario).filter_by(username=username).one_or_none()


def create(
    session: Session, data: UsuarioCreate, actor_id: int | None = None
) -> Usuario:
    obj = Usuario(
        username=data.username,
        nome=data.nome,
        senha_hash=hash_password(data.senha),
        papel=data.papel,
        perfil_id=data.perfil_id,
    )
    session.add(obj)
    session.flush()
    session.refresh(obj)
    auditar(
        session,
        actor_id=actor_id,
        tabela="usuario",
        tipo_acao="CREATE",
        registro_id=obj.id,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)
    return obj


def update(
    session: Session, obj: Usuario, data: UsuarioUpdate, actor_id: int | None = None
) -> None:
    antes = snapshot(obj)
    obj.username = data.username
    obj.nome = data.nome
    obj.papel = data.papel
    obj.ativo = data.ativo
    obj.perfil_id = data.perfil_id
    session.flush()
    auditar(
        session,
        actor_id=actor_id,
        tabela="usuario",
        tipo_acao="UPDATE",
        registro_id=obj.id,
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)


def get(session: Session, usuario_id: int) -> Usuario | None:
    return crud.get(session, Usuario, usuario_id)


def delete(session: Session, obj: Usuario, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def change_password(
    session: Session, obj: Usuario, nova_senha: str, actor_id: int | None = None
) -> None:
    antes = snapshot(obj)
    obj.senha_hash = hash_password(nova_senha)
    session.flush()
    auditar(
        session,
        actor_id=actor_id,
        tabela="usuario",
        tipo_acao="UPDATE",
        registro_id=obj.id,
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)


def set_perfil(
    session: Session,
    obj: Usuario,
    perfil_id: int | None,
    actor_id: int | None = None,
) -> None:
    antes = snapshot(obj)
    obj.perfil_id = perfil_id
    session.flush()
    auditar(
        session,
        actor_id=actor_id,
        tabela="usuario",
        tipo_acao="UPDATE",
        registro_id=obj.id,
        dados_antes=antes,
        dados_depois=snapshot(obj),
    )
    crud.flush(session)
