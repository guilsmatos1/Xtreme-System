"""API FastAPI: CRUD de investidores, meios de captação e veículos."""

import logging
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Annotated, Any

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jwt import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.auth import core as auth
from xtreme_system.database.core import get_session
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

logger = logging.getLogger(__name__)

app = FastAPI(title="Xtreme Estoque")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_errors(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Any:
    try:
        return await call_next(request)
    except Exception:
        logger.exception("unhandled error request=%s", request.url)
        raise


_ui_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_ui_dir / "static"), name="static")
templates = Jinja2Templates(directory=_ui_dir / "templates")


@app.get("/")
def raiz() -> RedirectResponse:
    return RedirectResponse("/docs")


SessionDep = Annotated[Session, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def _found[T](obj: T | None, nome: str) -> T:
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nome} não encontrado")
    return obj


# ---- Autenticação ----


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


@app.post("/login", response_model=auth.Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> auth.Token:
    user = usuario.get_by_username(session, form.username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(form.password, user.senha_hash)
    ):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    token = auth.create_access_token(user.username, user.papel)
    return auth.Token(access_token=token)


@app.post("/usuarios", response_model=usuario.UsuarioRead, status_code=201)
def criar_usuario(
    data: usuario.UsuarioCreate, session: SessionDep, _: AdminUser
) -> usuario.Usuario:
    if usuario.get_by_username(session, data.username) is not None:
        raise HTTPException(status_code=400, detail="username já existe")
    return usuario.create(session, data)


@app.get("/usuarios", response_model=list[usuario.UsuarioRead])
def listar_usuarios(session: SessionDep, _: AdminUser) -> list[usuario.Usuario]:
    return usuario.list_all(session)


# ---- CRUD genérico ----


def _validate_fks(session: Session, data: Any, *, update: bool = False) -> None:
    inv_id = data.investidor_id
    meio_id = data.meio_captacao_id
    inv_valid = (not update or inv_id is not None) and investidor.get(
        session, inv_id
    ) is None
    meio_valid = (not update or meio_id is not None) and meio_captacao.get(
        session, meio_id
    ) is None
    if inv_valid:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")
    if meio_valid:
        raise HTTPException(status_code=400, detail="meio_captacao_id inexistente")


def register_crud_routes(
    app: FastAPI,
    module: Any,
    prefix: str,
    label: str,
    *,
    read_schema: type,
    create_schema: type,
    update_schema: type,
    before_create: Callable[[Session, Any], None] | None = None,
    before_update: Callable[[Session, Any, Any], None] | None = None,
    handle_delete_error: bool = True,
) -> None:
    @app.get(prefix, response_model=list[read_schema])  # type: ignore[valid-type]
    def _list(session: SessionDep, _: CurrentUser) -> Any:
        return module.list_all(session)

    @app.get(f"{prefix}/{{item_id}}", response_model=read_schema)
    def _get(item_id: int, session: SessionDep, _: CurrentUser) -> Any:
        return _found(module.get(session, item_id), label)

    @app.post(prefix, response_model=read_schema, status_code=201)
    def _create(data: create_schema, session: SessionDep, _: AdminUser) -> Any:  # type: ignore[valid-type]
        if before_create:
            before_create(session, data)
        return module.create(session, data)

    @app.patch(f"{prefix}/{{item_id}}", response_model=read_schema)
    def _update(
        item_id: int,
        data: update_schema,  # type: ignore[valid-type]
        session: SessionDep,
        _: AdminUser,
    ) -> Any:
        obj = _found(module.get(session, item_id), label)
        if before_update:
            before_update(session, obj, data)
        return module.update(session, obj, data)

    @app.delete(f"{prefix}/{{item_id}}", status_code=204)
    def _delete(item_id: int, session: SessionDep, _: AdminUser) -> None:
        obj = _found(module.get(session, item_id), label)
        if handle_delete_error:
            try:
                module.delete(session, obj)
            except IntegrityError:
                session.rollback()
                raise HTTPException(
                    status_code=409, detail=f"{label} possui veículos vinculados"
                ) from None
        else:
            module.delete(session, obj)


# ---- Investidores ----

register_crud_routes(
    app,
    investidor,
    "/investidores",
    "Investidor",
    read_schema=investidor.InvestidorRead,
    create_schema=investidor.InvestidorCreate,
    update_schema=investidor.InvestidorUpdate,
)

# ---- Meios de captação ----

register_crud_routes(
    app,
    meio_captacao,
    "/meios-captacao",
    "Meio de captação",
    read_schema=meio_captacao.MeioCaptacaoRead,
    create_schema=meio_captacao.MeioCaptacaoCreate,
    update_schema=meio_captacao.MeioCaptacaoUpdate,
)

# ---- Veículos ----

register_crud_routes(
    app,
    veiculo,
    "/veiculos",
    "Veículo",
    read_schema=veiculo.VeiculoRead,
    create_schema=veiculo.VeiculoCreate,
    update_schema=veiculo.VeiculoUpdate,
    before_create=partial(_validate_fks),
    before_update=partial(_validate_fks, update=True),
    handle_delete_error=False,
)


# ============================================================================
# UI HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON.
# ============================================================================


class _NaoAutenticadoError(Exception):
    pass


class _NaoAdminError(Exception):
    pass


# ponytail: redirect vale pra navegação normal; num hx-request expirado o htmx
# injeta o login no target. Suficiente pro MVP; tratar com HX-Redirect se incomodar.
@app.exception_handler(_NaoAutenticadoError)
def _handle_nao_autenticado(
    _request: Request, _exc: _NaoAutenticadoError
) -> RedirectResponse:
    return RedirectResponse("/ui/login", status_code=303)


@app.exception_handler(_NaoAdminError)
def _handle_nao_admin(_request: Request, _exc: _NaoAdminError) -> HTMLResponse:
    return HTMLResponse("<p>Requer papel admin</p>", status_code=403)


def get_ui_user(
    session: SessionDep, access_token: Annotated[str | None, Cookie()] = None
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
    return user


UIUser = Annotated[usuario.Usuario, Depends(get_ui_user)]


def require_ui_admin(user: UIUser) -> usuario.Usuario:
    if user.papel != usuario.Papel.admin:
        raise _NaoAdminError
    return user


UIAdmin = Annotated[usuario.Usuario, Depends(require_ui_admin)]


# ---- Login / logout ----


@app.get("/ui/login")
def ui_login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/ui/login")
def ui_login(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    user = usuario.get_by_username(session, username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(password, user.senha_hash)
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"erro": "Usuário ou senha inválidos"},
            status_code=401,
        )
    token = auth.create_access_token(user.username, user.papel)
    resp = RedirectResponse("/ui/veiculos", status_code=303)
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=auth.get_settings().auth_token_expire_minutes * 60,
    )
    return resp


@app.post("/ui/logout")
def ui_logout() -> RedirectResponse:
    resp = RedirectResponse("/ui/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp


# ---- Veículos (UI) ----


def _ctx_form_veiculo(session: Session) -> dict[str, Any]:
    return {
        "tipos": list(veiculo.TipoVeiculo),
        "status": list(veiculo.StatusVeiculo),
        "investidores": investidor.list_all(session),
        "meios": meio_captacao.list_all(session),
    }


def _ok_veiculos(
    request: Request, session: Session, user: usuario.Usuario
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_veiculos_ok.html",
        {"user": user, "veiculos": veiculo.list_all(session)},
    )


def _erro_veiculo(
    request: Request,
    session: Session,
    exc: ValidationError | HTTPException,
    obj: veiculo.Veiculo | None,
) -> HTMLResponse:
    erro = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
    return templates.TemplateResponse(
        request,
        "_form_veiculo.html",
        {**_ctx_form_veiculo(session), "veiculo": obj, "erro": erro},
        status_code=400,
    )


@app.get("/ui/veiculos")
def ui_veiculos(
    request: Request, session: SessionDep, user: UIUser, q: str = ""
) -> HTMLResponse:
    lista = veiculo.search(session, q) if q else veiculo.list_all(session)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "_linhas_veiculos.html", {"user": user, "veiculos": lista}
        )
    return templates.TemplateResponse(
        request, "veiculos.html", {"user": user, "veiculos": lista, "q": q}
    )


@app.get("/ui/veiculos/novo")
def ui_veiculo_novo(request: Request, session: SessionDep, _: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_form_veiculo.html", {**_ctx_form_veiculo(session), "veiculo": None}
    )


@app.get("/ui/veiculos/{item_id}/editar")
def ui_veiculo_editar(
    item_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(veiculo.get(session, item_id), "Veículo")
    return templates.TemplateResponse(
        request, "_form_veiculo.html", {**_ctx_form_veiculo(session), "veiculo": obj}
    )


@app.post("/ui/veiculos")
async def ui_veiculo_criar(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    form = await request.form()
    try:
        data = veiculo.VeiculoCreate.model_validate(dict(form))
        _validate_fks(session, data)
    except (ValidationError, HTTPException) as exc:
        return _erro_veiculo(request, session, exc, None)
    veiculo.create(session, data)
    return _ok_veiculos(request, session, user)


@app.post("/ui/veiculos/{item_id}")
async def ui_veiculo_atualizar(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = _found(veiculo.get(session, item_id), "Veículo")
    form = await request.form()
    try:
        data = veiculo.VeiculoUpdate.model_validate(dict(form))
        _validate_fks(session, data, update=True)
    except (ValidationError, HTTPException) as exc:
        return _erro_veiculo(request, session, exc, obj)
    veiculo.update(session, obj, data)
    return _ok_veiculos(request, session, user)


@app.post("/ui/veiculos/{item_id}/excluir")
def ui_veiculo_excluir(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    obj = _found(veiculo.get(session, item_id), "Veículo")
    veiculo.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "_linhas_veiculos.html",
        {"user": user, "veiculos": veiculo.list_all(session)},
    )


# ---- Usuários (UI, admin) ----


@app.get("/ui/usuarios")
def ui_usuarios(request: Request, session: SessionDep, user: UIAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "usuarios.html", {"user": user, "usuarios": usuario.list_all(session)}
    )


@app.post("/ui/usuarios")
def ui_usuario_criar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str, Form()],
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.leitor,
) -> HTMLResponse:
    erro = None
    if usuario.get_by_username(session, username) is not None:
        erro = "username já existe"
    else:
        usuario.create(
            session, usuario.UsuarioCreate(username=username, senha=senha, papel=papel)
        )
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {"user": user, "usuarios": usuario.list_all(session), "erro": erro},
        status_code=400 if erro else 200,
    )


# ---- Investidores / Meios de captação (UI, mesmo padrão) ----


def register_ui_simples(
    ui_prefix: str, titulo: str, module: Any, create_schema: type, update_schema: type
) -> None:
    def _ctx(user: usuario.Usuario, session: Session, **extra: Any) -> dict[str, Any]:
        return {
            "user": user,
            "titulo": titulo,
            "prefixo": ui_prefix,
            "itens": module.list_all(session),
            **extra,
        }

    def _form_ctx(item: Any, erro: str | None = None) -> dict[str, Any]:
        return {"titulo": titulo, "prefixo": ui_prefix, "item": item, "erro": erro}

    async def _nome(request: Request) -> str:
        return str((await request.form()).get("nome") or "").strip()

    @app.get(ui_prefix)
    def _lista(request: Request, session: SessionDep, user: UIUser) -> HTMLResponse:
        return templates.TemplateResponse(request, "simples.html", _ctx(user, session))

    @app.get(f"{ui_prefix}/novo")
    def _novo(request: Request, _: UIAdmin) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "_form_simples.html", _form_ctx(None)
        )

    @app.get(f"{ui_prefix}/{{item_id}}/editar")
    def _editar(
        item_id: int, request: Request, session: SessionDep, _: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        return templates.TemplateResponse(request, "_form_simples.html", _form_ctx(obj))

    @app.post(ui_prefix)
    async def _criar(
        request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(None, "Nome obrigatório"),
                status_code=400,
            )
        module.create(session, create_schema(nome=nome))
        return templates.TemplateResponse(
            request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}")
    async def _atualizar(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        nome = await _nome(request)
        if not nome:
            return templates.TemplateResponse(
                request,
                "_form_simples.html",
                _form_ctx(obj, "Nome obrigatório"),
                status_code=400,
            )
        module.update(session, obj, update_schema(nome=nome))
        return templates.TemplateResponse(
            request, "_simples_ok.html", _ctx(user, session)
        )

    @app.post(f"{ui_prefix}/{{item_id}}/excluir")
    def _excluir(
        item_id: int, request: Request, session: SessionDep, user: UIAdmin
    ) -> HTMLResponse:
        obj = _found(module.get(session, item_id), titulo)
        msg = None
        try:
            module.delete(session, obj)
        except IntegrityError:
            session.rollback()
            msg = f"{titulo} possui veículos vinculados"
        return templates.TemplateResponse(
            request, "_linhas_simples.html", _ctx(user, session, msg=msg)
        )


register_ui_simples(
    "/ui/investidores",
    "Investidores",
    investidor,
    investidor.InvestidorCreate,
    investidor.InvestidorUpdate,
)
register_ui_simples(
    "/ui/meios-captacao",
    "Meios de captação",
    meio_captacao,
    meio_captacao.MeioCaptacaoCreate,
    meio_captacao.MeioCaptacaoUpdate,
)
