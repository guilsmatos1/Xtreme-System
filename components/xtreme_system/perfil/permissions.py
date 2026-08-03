"""Pure permission predicates shared by the Perfil component and its callers."""

from typing import Any, Protocol


class PerfilLike(Protocol):
    """Structural view of a profile needed by permission checks."""

    @property
    def paginas(self) -> list[str]: ...

    @property
    def restricoes(self) -> dict[str, Any]: ...


class UsuarioLike(Protocol):
    """Structural view of a user needed by permission checks."""

    @property
    def is_admin(self) -> bool: ...

    @property
    def perfil(self) -> PerfilLike | None: ...


def pode_acessar(user: UsuarioLike, pagina: str) -> bool:
    if user.is_admin:
        return True
    return bool(user.perfil and pagina in user.perfil.paginas)


def pode_ver_campo(user: UsuarioLike, pagina: str, campo: str) -> bool:
    if user.is_admin:
        return True
    if not user.perfil:
        return False
    if pagina not in user.perfil.paginas:
        return False
    ocultos = (user.perfil.restricoes or {}).get(pagina, {}).get("campos_ocultos", [])
    return campo not in ocultos


def pode_operacao(user: UsuarioLike, pagina: str, operacao: str) -> bool:
    if user.is_admin:
        return True
    if not user.perfil:
        return False
    if pagina not in user.perfil.paginas:
        return False
    permitidas = (user.perfil.restricoes or {}).get(pagina, {}).get("operacoes", [])
    return operacao in permitidas
