"""Rotas JSON: autenticação, usuários e CRUD dos recursos de negócio."""

from functools import partial
from typing import Annotated, Any

from fastapi import Depends, Form, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from xtreme_system.api.deps import AdminUser, CurrentUser, SessionDep, _found
from xtreme_system.api.route_factories import register_crud_routes
from xtreme_system.api.setup import app
from xtreme_system.auth import core as auth
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda

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
    data: usuario.UsuarioCreate, session: SessionDep, _: AdminUser
) -> usuario.Usuario:
    if usuario.get_by_username(session, data.username) is not None:
        raise HTTPException(status_code=400, detail="username já existe")
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
    usuario.delete(session, obj)


@app.post("/usuarios/{user_id}/senha", status_code=204)
def trocar_senha_usuario(
    user_id: int,
    session: SessionDep,
    _: AdminUser,
    nova_senha: Annotated[str, Form()],
) -> None:
    obj = _found(usuario.get(session, user_id), "Usuário")
    usuario.change_password(session, obj, nova_senha)


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
    if (
        not update
        and hasattr(data, "placa")
        and veiculo.get_by_placa(session, data.placa)
    ):
        raise HTTPException(status_code=400, detail="placa já cadastrada")


def _validate_venda_fks(session: Session, data: Any) -> None:
    cli_id = getattr(data, "cliente_id", None)
    vei_id = getattr(data, "veiculo_id", None)
    if cli_id is not None and cliente.get(session, cli_id) is None:
        raise HTTPException(status_code=400, detail="cliente_id inexistente")
    if vei_id is not None and veiculo.get(session, vei_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")


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
    before_update=lambda session, _obj, data: _validate_fks(session, data, update=True),
    after_create=caixa.criar_lancamento_veiculo,
    after_update=caixa.sincronizar_lancamento_veiculo,
    handle_delete_error=False,
)

# ---- Caixa dos investidores ----


def _validate_investidor_lancamento(session: Session, data: Any) -> None:
    if investidor.get(session, data.investidor_id) is None:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")


def _guard_lancamento_veiculo(_session: Session, obj: Any, _data: Any = None) -> None:
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=400,
            detail="Lançamento de veículo só pode ser alterado na tela de Veículos",
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
    before_create=_validate_venda_fks,
    before_update=lambda session, _obj, data: _validate_venda_fks(session, data),
)
