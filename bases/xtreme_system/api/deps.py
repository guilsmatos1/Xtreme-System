"""Dependências compartilhadas: sessão, autenticação (Bearer/cookie) e templates."""

from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from xtreme_system.auth import core as auth
from xtreme_system.database.core import get_session
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["pode_acessar"] = perfil.pode_acessar
templates.env.globals["paginas_labels"] = dict(perfil.PAGINAS)

SessionDep = Annotated[Session, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def _found[T](obj: T | None, nome: str) -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nome} não encontrado")
    return obj


# ---- Autenticação API (Bearer token) ----


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep
) -> usuario.Usuario:
    credenciais_invalidas = HTTPException(
        status_code=401,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        dados = auth.decode_token(token)
    except InvalidTokenError:
        raise credenciais_invalidas from None
    user = usuario.get_by_username(session, dados.username)
    if user is None or not user.ativo:
        raise credenciais_invalidas
    return user


CurrentUser = Annotated[usuario.Usuario, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> usuario.Usuario:
    if user.papel != usuario.Papel.admin:
        raise HTTPException(status_code=403, detail="Requer papel admin")
    return user


AdminUser = Annotated[usuario.Usuario, Depends(require_admin)]


# ---- Autenticação UI (cookie httpOnly) ----


class _NaoAutenticadoError(Exception):
    pass


class _NaoAdminError(Exception):
    pass


class _NaoAutorizadoError(Exception):
    pass


def get_ui_user(
    request: Request,
    session: SessionDep,
    access_token: Annotated[str | None, Cookie()] = None,
) -> usuario.Usuario:
    if not access_token:
        raise _NaoAutenticadoError
    try:
        dados = auth.decode_token(access_token)
    except InvalidTokenError:
        raise _NaoAutenticadoError from None
    user = usuario.get_by_username(session, dados.username)
    if user is None or not user.ativo:
        raise _NaoAutenticadoError
    pagina = perfil._pagina_da_rota(request.url.path)
    if pagina and not perfil.pode_acessar(user, pagina):
        raise _NaoAutorizadoError
    return user


UIUser = Annotated[usuario.Usuario, Depends(get_ui_user)]


def require_ui_admin(user: UIUser) -> usuario.Usuario:
    if user.papel != usuario.Papel.admin:
        raise _NaoAdminError
    return user


UIAdmin = Annotated[usuario.Usuario, Depends(require_ui_admin)]
