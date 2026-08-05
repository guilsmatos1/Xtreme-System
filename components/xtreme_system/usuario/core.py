"""Usuário: enum de papel, model, schemas e CRUD."""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.auth.core import hash_password
from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

if TYPE_CHECKING:
    from xtreme_system.perfil.core import Perfil

MIN_SENHA_LENGTH = 3


class Papel(StrEnum):
    admin = "admin"
    funcionario = "funcionario"


class SenhaFracaError(ValueError):
    def __init__(self) -> None:
        super().__init__("senha deve ter pelo menos 3 caracteres")


class UsuarioValidationError(ValueError):
    """Raised when user data violates an application-level constraint."""


class UsernameJaExisteError(UsuarioValidationError):
    def __init__(self) -> None:
        super().__init__("username já existe")


class PerfilNaoEncontradoError(UsuarioValidationError):
    def __init__(self) -> None:
        super().__init__("perfil não encontrado")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    nome: Mapped[str | None] = mapped_column(default=None)
    senha_hash: Mapped[str]
    papel: Mapped[Papel] = mapped_column(default=Papel.funcionario)
    ativo: Mapped[bool] = mapped_column(default=True)
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    perfil_id: Mapped[int | None] = mapped_column(ForeignKey("perfil.id"), index=True)
    perfil: Mapped["Perfil | None"] = relationship()


def is_admin(user: Usuario) -> bool:
    return user.papel == Papel.admin


class UsuarioCreate(BaseModel):
    username: str
    nome: str | None = None
    senha: str
    papel: Papel = Papel.funcionario
    perfil_id: int | None = None

    @field_validator("username", mode="before")
    @classmethod
    def _validar_username(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto_obrigatorio(value)

    @field_validator("nome", mode="before")
    @classmethod
    def _normalizar_nome(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto(value)


class UsuarioUpdate(BaseModel):
    username: str
    nome: str | None = None
    papel: Papel = Papel.funcionario
    ativo: bool = True
    perfil_id: int | None = None

    @field_validator("username", mode="before")
    @classmethod
    def _validar_username(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto_obrigatorio(value)

    @field_validator("nome", mode="before")
    @classmethod
    def _normalizar_nome(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto(value)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nome: str | None
    papel: Papel
    ativo: bool
    perfil_id: int | None


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Usuario]:
    return crud.list_all(session, Usuario, limit=limit, offset=offset)


def get_by_username(session: Session, username: str) -> Usuario | None:
    return session.query(Usuario).filter_by(username=username).one_or_none()


def validate_senha(senha: str) -> str:
    senha = senha.strip()
    if len(senha) < MIN_SENHA_LENGTH:
        raise SenhaFracaError()
    return senha


def _validate_perfil(session: Session, perfil_id: int | None) -> None:
    if perfil_id is None:
        return
    from xtreme_system.perfil import core as perfil  # noqa: PLC0415

    if perfil.get(session, perfil_id) is None:
        raise PerfilNaoEncontradoError()


def validate_create(session: Session, data: UsuarioCreate) -> None:
    if get_by_username(session, data.username) is not None:
        raise UsernameJaExisteError()
    _validate_perfil(session, data.perfil_id)
    validate_senha(data.senha)


def validate_update(session: Session, obj: Usuario, data: UsuarioUpdate) -> None:
    existing = get_by_username(session, data.username)
    if existing is not None and existing.id != obj.id:
        raise UsernameJaExisteError()
    _validate_perfil(session, data.perfil_id)


def create(
    session: Session, data: UsuarioCreate, actor_id: int | None = None
) -> Usuario:
    validate_create(session, data)
    obj = Usuario(
        username=data.username,
        nome=data.nome,
        senha_hash=hash_password(data.senha.strip()),
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
    validate_update(session, obj, data)
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
    nova_senha = validate_senha(nova_senha)
    antes = snapshot(obj)
    obj.senha_hash = hash_password(nova_senha)
    obj.token_version = Usuario.token_version + 1
    session.flush()
    session.refresh(obj)
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


def invalidate_tokens(session: Session, obj: Usuario) -> None:
    obj.token_version = Usuario.token_version + 1
    crud.flush(session)
    session.refresh(obj)


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
