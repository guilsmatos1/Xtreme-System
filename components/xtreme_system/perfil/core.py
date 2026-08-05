"""Perfil de permissões: quais páginas da UI um perfil de usuário pode acessar."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base
from xtreme_system.perfil import permissions as _permissions
from xtreme_system.perfil import policy as _policy
from xtreme_system.perfil.permissions import PerfilLike, UsuarioLike
from xtreme_system.usuario import core as usuario

CAMPOS_FORM_PROTEGIDOS = _policy.CAMPOS_FORM_PROTEGIDOS
CAMPOS_PROTEGIDOS = _policy.CAMPOS_PROTEGIDOS
OPERACOES = _policy.OPERACOES
PAGINAS = _policy.PAGINAS
PAGINAS_VALIDAS = _policy.PAGINAS_VALIDAS
ROTAS_DERIVADAS = _policy.ROTAS_DERIVADAS

__all__ = [
    "CAMPOS_FORM_PROTEGIDOS",
    "CAMPOS_PROTEGIDOS",
    "OPERACOES",
    "PAGINAS",
    "PAGINAS_VALIDAS",
    "ROTAS_DERIVADAS",
    "Perfil",
    "PerfilCreate",
    "PerfilRead",
    "PerfilUpdate",
    "campos_form_visiveis",
    "campos_ocultados",
    "create",
    "delete",
    "get",
    "list_all",
    "pagina_da_rota",
    "pode_acessar",
    "pode_operacao",
    "pode_ver_campo",
    "update",
]


@dataclass(frozen=True)
class _PermissionUser:
    is_admin: bool
    perfil: PerfilLike | None


def _permission_user(user: usuario.Usuario) -> UsuarioLike:
    return _PermissionUser(is_admin=usuario.is_admin(user), perfil=user.perfil)


def campos_form_visiveis(
    user: usuario.Usuario, pagina: str | None, data: Mapping[str, Any]
) -> dict[str, Any]:
    filtered_data = dict(data)
    if pagina is None:
        return filtered_data
    for campo, campo_form in CAMPOS_FORM_PROTEGIDOS.get(pagina, {}).items():
        if not pode_ver_campo(user, pagina, campo):
            filtered_data.pop(campo_form, None)
    return filtered_data


def campos_ocultados(user: usuario.Usuario, pagina: str | None) -> set[str]:
    """Nomes de campo (schema) ocultados do form deste usuário nesta página."""
    if pagina is None:
        return set()
    return {
        campo_form
        for campo, campo_form in CAMPOS_FORM_PROTEGIDOS.get(pagina, {}).items()
        if not pode_ver_campo(user, pagina, campo)
    }


class Perfil(Base):
    __tablename__ = "perfil"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True, index=True)
    paginas: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Por página: campos_ocultos (denylist) e operacoes (allowlist) permitidas.
    restricoes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PerfilCreate(BaseModel):
    nome: str
    paginas: list[str] = []
    restricoes: dict[str, Any] = {}

    @field_validator("nome", mode="before")
    @classmethod
    def _validar_nome(cls, value: Any) -> Any:
        _ = cls
        return crud.trim_texto_obrigatorio(value)


class PerfilUpdate(BaseModel):
    nome: str | None = None
    paginas: list[str] | None = None
    restricoes: dict[str, Any] | None = None

    @field_validator("nome", mode="before")
    @classmethod
    def _validar_nome(cls, value: Any) -> Any:
        _ = cls
        if value is None:
            return None
        return crud.trim_texto_obrigatorio(value)


class PerfilRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    paginas: list[str]
    restricoes: dict[str, Any]


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Perfil]:
    return crud.list_all(session, Perfil, limit=limit, offset=offset)


def get(session: Session, perfil_id: int) -> Perfil | None:
    return crud.get(session, Perfil, perfil_id)


def create(session: Session, data: PerfilCreate, actor_id: int | None = None) -> Perfil:
    return crud.create(session, Perfil, data, actor_id)


def update(
    session: Session, obj: Perfil, data: PerfilUpdate, actor_id: int | None = None
) -> Perfil:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Perfil, actor_id: int | None = None) -> None:
    for user in session.query(usuario.Usuario).filter_by(perfil_id=obj.id):
        usuario.set_perfil(session, user, None, actor_id)
    crud.delete(session, obj, actor_id)


def pagina_da_rota(path: str) -> str | None:
    if path == "/consultas" or path.startswith("/consultas/"):
        return "veiculos"
    if not path.startswith("/ui/"):
        return None
    segmento = path.removeprefix("/ui/").split("/", 1)[0]
    segmento = ROTAS_DERIVADAS.get(segmento, segmento)
    return segmento if segmento in PAGINAS_VALIDAS else None


def pode_acessar(user: usuario.Usuario, pagina: str) -> bool:
    return _permissions.pode_acessar(_permission_user(user), pagina)


def pode_ver_campo(user: usuario.Usuario, pagina: str, campo: str) -> bool:
    return _permissions.pode_ver_campo(_permission_user(user), pagina, campo)


def pode_operacao(user: usuario.Usuario, pagina: str, operacao: str) -> bool:
    return _permissions.pode_operacao(_permission_user(user), pagina, operacao)
