"""Rotas JSON: autenticação, usuários e CRUD dos recursos de negócio."""

from datetime import date
from typing import Annotated, Any

from fastapi import Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import AdminUser, CurrentUser, SessionDep, _found
from xtreme_system.api.route_factories import register_crud_routes
from xtreme_system.api.routes.workflows import (
    validate_cliente_veiculo_fks,
    validate_veiculo_fks,
)
from xtreme_system.api.setup import app
from xtreme_system.auditoria import core as auditoria
from xtreme_system.auth import core as auth
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp

# ---- Health check (sem auth) ----


@app.get("/health")
def health(session: SessionDep) -> JSONResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            {"status": "degradado", "database": "indisponivel"},
            status_code=503,
        )
    return JSONResponse({"status": "ok", "database": "ok"})


# ---- Autenticação ----


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
    data: usuario.UsuarioCreate, session: SessionDep, admin: AdminUser
) -> usuario.Usuario:
    if usuario.get_by_username(session, data.username) is not None:
        raise HTTPException(status_code=400, detail="username já existe")
    session.info["usuario_id"] = admin.id
    return usuario.create(session, data)


@app.get("/usuarios", response_model=list[usuario.UsuarioRead])
def listar_usuarios(session: SessionDep, _: AdminUser) -> list[usuario.Usuario]:
    return usuario.list_all(session)


@app.delete("/usuarios/{user_id}", status_code=204)
def deletar_usuario(
    user_id: int, session: SessionDep, current: CurrentUser, _: AdminUser
) -> None:
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="não pode excluir a si mesmo")
    obj = _found(usuario.get(session, user_id), "Usuário")
    session.info["usuario_id"] = current.id
    usuario.delete(session, obj)


@app.post("/usuarios/{user_id}/senha", status_code=204)
def trocar_senha_usuario(
    user_id: int,
    session: SessionDep,
    admin: AdminUser,
    nova_senha: Annotated[str, Form()],
) -> None:
    obj = _found(usuario.get(session, user_id), "Usuário")
    session.info["usuario_id"] = admin.id
    usuario.change_password(session, obj, nova_senha)


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

# ---- Veículos ----

register_crud_routes(
    app,
    veiculo,
    "/veiculos",
    "Veículo",
    read_schema=veiculo.VeiculoRead,
    create_schema=veiculo.VeiculoCreate,
    update_schema=veiculo.VeiculoUpdate,
    before_create=validate_veiculo_fks,
    before_update=lambda session, _obj, data: validate_veiculo_fks(
        session, data, update=True
    ),
    before_delete=caixa.deletar_lancamento_veiculo,
    after_create=caixa.criar_lancamento_veiculo,
    after_update=caixa.sincronizar_lancamento_veiculo,
    handle_delete_error=False,
)

# ---- Caixa dos investidores ----


def _validate_investidor_lancamento(session: Session, data: Any) -> None:
    if investidor.get(session, data.investidor_id) is None:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")


def _guard_lancamento_veiculo(_session: Session, obj: Any, _data: Any = None) -> None:
    if obj.origem != caixa.OrigemLancamento.manual:
        raise HTTPException(
            status_code=400,
            detail="Lançamento automático não pode ser alterado manualmente",
        )


register_crud_routes(
    app,
    caixa,
    "/lancamentos-caixa",
    "Lançamento de caixa",
    read_schema=caixa.LancamentoInvestimentoRead,
    create_schema=caixa.LancamentoInvestimentoCreate,
    update_schema=caixa.LancamentoInvestimentoUpdate,
    before_create=_validate_investidor_lancamento,
    before_update=_guard_lancamento_veiculo,
    before_delete=_guard_lancamento_veiculo,
)


# ---- Fechamento de vendas ----


@app.get(
    "/vendas/{venda_id}/fechamento/preview",
    response_model=fechamento_venda.FechamentoVendaPreview,
)
def preview_fechamento_venda(
    venda_id: int, session: SessionDep, _: CurrentUser
) -> fechamento_venda.FechamentoVendaPreview:
    venda_obj = _found(venda.get(session, venda_id), "Venda")
    return fechamento_venda.preview(session, venda_obj)


@app.post(
    "/vendas/{venda_id}/fechamento",
    response_model=fechamento_venda.FechamentoVendaRead,
    status_code=201,
)
def confirmar_fechamento_venda(
    venda_id: int,
    data: fechamento_venda.FechamentoVendaCreate,
    session: SessionDep,
    admin: AdminUser,
) -> fechamento_venda.FechamentoVenda:
    venda_obj = _found(venda.get(session, venda_id), "Venda")
    session.info["usuario_id"] = admin.id
    try:
        return fechamento_venda.confirmar(session, venda_obj, data, usuario_id=admin.id)
    except fechamento_venda.FechamentoVendaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.get(
    "/fechamentos-vendas",
    response_model=list[fechamento_venda.FechamentoVendaRead],
)
def listar_fechamentos_vendas(
    session: SessionDep, _: CurrentUser
) -> list[fechamento_venda.FechamentoVenda]:
    return fechamento_venda.list_all(session)


@app.get(
    "/fechamentos-vendas/{fechamento_id}",
    response_model=fechamento_venda.FechamentoVendaRead,
)
def obter_fechamento_venda(
    fechamento_id: int, session: SessionDep, _: CurrentUser
) -> fechamento_venda.FechamentoVenda:
    return _found(fechamento_venda.get(session, fechamento_id), "Fechamento")


# ---- Clientes ----

register_crud_routes(
    app,
    cliente,
    "/clientes",
    "Cliente",
    read_schema=cliente.ClienteRead,
    create_schema=cliente.ClienteCreate,
    update_schema=cliente.ClienteUpdate,
)


# ---- Vendas ----

register_crud_routes(
    app,
    venda,
    "/vendas",
    "Venda",
    read_schema=venda.VendaRead,
    create_schema=venda.VendaCreate,
    update_schema=venda.VendaUpdate,
    before_create=validate_cliente_veiculo_fks,
    before_update=lambda session, _obj, data: validate_cliente_veiculo_fks(
        session, data
    ),
    after_create=whatsapp.notificar_venda,
)


# ---- Compras ----

register_crud_routes(
    app,
    compra,
    "/compras",
    "Compra",
    read_schema=compra.CompraRead,
    create_schema=compra.CompraCreate,
    update_schema=compra.CompraUpdate,
    before_create=validate_cliente_veiculo_fks,
    before_update=lambda session, _obj, data: validate_cliente_veiculo_fks(
        session, data
    ),
)


# ---- Auditoria (somente leitura, admin) ----


@app.get("/auditoria", response_model=list[auditoria.AuditoriaRead])
def listar_auditoria(
    session: SessionDep,
    _: AdminUser,
    usuario_id: int | None = None,
    tabela: str | None = None,
    tipo_acao: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[auditoria.Auditoria]:
    return auditoria.query(
        session,
        usuario_id=usuario_id,
        tabela=tabela,
        tipo_acao=tipo_acao,
        data_de=data_de,
        data_ate=data_ate,
        limit=limit,
        offset=offset,
    )
