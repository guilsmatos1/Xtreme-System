"""Rotas JSON: autenticação, usuários e CRUD dos recursos de negócio."""

from datetime import date
from typing import Annotated, Any

from fastapi import Depends, Form, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import AdminUser, CurrentUser, SessionDep, _found
from xtreme_system.api.route_factories import (
    JSON_LIST_LIMIT_MAX,
    json_visible,
    register_crud_routes,
)
from xtreme_system.api.routes.workflows import (
    recompute_vehicle_status_on_delete,
    validate_cliente_veiculo_fks,
    validate_valores_venda_update,
    validate_veiculo_disponivel_para_venda,
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
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.whatsapp import core as whatsapp

AUDITORIA_LIMIT_MAX = 200

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
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> auth.Token:
    user = usuario.get_by_username(session, form.username)
    if (
        user is None
        or not user.ativo
        or not auth.verify_password(form.password, user.senha_hash)
    ):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    token = auth.create_access_token(user.username)
    return auth.Token(access_token=token)


@app.post("/usuarios", response_model=usuario.UsuarioRead, status_code=201)
def criar_usuario(
    data: usuario.UsuarioCreate, session: SessionDep, admin: AdminUser
) -> usuario.Usuario:
    if usuario.get_by_username(session, data.username) is not None:
        raise HTTPException(status_code=400, detail="username já existe")
    if data.perfil_id is not None and perfil.get(session, data.perfil_id) is None:
        raise HTTPException(status_code=400, detail="perfil não encontrado")
    try:
        return usuario.create(session, data, admin.id)
    except usuario.SenhaFracaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/usuarios", response_model=list[usuario.UsuarioRead])
def listar_usuarios(
    session: SessionDep,
    _: AdminUser,
    limit: Annotated[int, Query(ge=1, le=JSON_LIST_LIMIT_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[usuario.Usuario]:
    return usuario.list_all(session, limit=limit, offset=offset)


@app.delete("/usuarios/{user_id}", status_code=204)
def deletar_usuario(
    user_id: int, session: SessionDep, current: CurrentUser, _: AdminUser
) -> None:
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="não pode excluir a si mesmo")
    obj = _found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj, current.id)


@app.post("/usuarios/{user_id}/senha", status_code=204)
def trocar_senha_usuario(
    user_id: int,
    session: SessionDep,
    admin: AdminUser,
    nova_senha: Annotated[str, Form()],
) -> None:
    obj = _found(usuario.get(session, user_id), "Usuário")
    try:
        usuario.change_password(session, obj, nova_senha, admin.id)
    except usuario.SenhaFracaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---- Investidores ----

register_crud_routes(
    app,
    investidor,
    "/investidores",
    "Investidor",
    read_schema=investidor.InvestidorRead,
    create_schema=investidor.InvestidorCreate,
    update_schema=investidor.InvestidorUpdate,
    pagina="investidores",
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
    pagina="veiculos",
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
    pagina="investidores",
)


# ---- Fechamento de vendas ----


def _fechamento_preview_json(
    obj: fechamento_venda.FechamentoVendaPreview, user: usuario.Usuario
) -> dict[str, Any]:
    return json_visible(
        obj,
        user,
        "vendas",
        campos_protegidos=("debitos",),
        campos_permissao={
            "lucro": (
                "custo_veiculo",
                "custos_operacionais",
                "lucro_liquido",
            ),
            "participacao": ("investidores",),
        },
    )


def _fechamento_json(
    obj: fechamento_venda.FechamentoVenda, user: usuario.Usuario
) -> dict[str, Any]:
    return json_visible(
        obj,
        user,
        "vendas",
        fechamento_venda.FechamentoVendaRead,
        campos_protegidos=("debitos",),
        campos_permissao={
            "lucro": (
                "custo_veiculo",
                "custos_operacionais",
                "lucro_liquido",
            ),
            "participacao": ("participacoes",),
        },
    )


@app.get(
    "/vendas/{venda_id}/fechamento/preview",
)
def preview_fechamento_venda(
    venda_id: int, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    venda_obj = _found(venda.get(session, venda_id), "Venda")
    return _fechamento_preview_json(fechamento_venda.preview(session, venda_obj), user)


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
    try:
        return fechamento_venda.confirmar(session, venda_obj, data, usuario_id=admin.id)
    except fechamento_venda.FechamentoVendaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@app.get(
    "/fechamentos-vendas",
)
def listar_fechamentos_vendas(
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=JSON_LIST_LIMIT_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    try:
        fechamentos = fechamento_venda.list_all(session, limit=limit, offset=offset)
    except fechamento_venda.FechamentoVendaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return [_fechamento_json(obj, user) for obj in fechamentos]


@app.get(
    "/fechamentos-vendas/{fechamento_id}",
)
def obter_fechamento_venda(
    fechamento_id: int, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    return _fechamento_json(
        _found(fechamento_venda.get(session, fechamento_id), "Fechamento"), user
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
    pagina="clientes",
)


# ---- Vendas ----


def _validate_venda_create(session: Session, data: Any) -> None:
    validate_cliente_veiculo_fks(session, data)
    validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


def _validate_venda_update(session: Session, obj: Any, data: Any) -> None:
    validate_cliente_veiculo_fks(session, data)
    validate_valores_venda_update(obj, data)
    if data.veiculo_id is not None and data.veiculo_id != obj.veiculo_id:
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


register_crud_routes(
    app,
    venda,
    "/vendas",
    "Venda",
    read_schema=venda.VendaRead,
    create_schema=venda.VendaCreate,
    update_schema=venda.VendaUpdate,
    before_create=_validate_venda_create,
    before_update=_validate_venda_update,
    before_delete=recompute_vehicle_status_on_delete,
    after_create=whatsapp.notificar_venda,
    pagina="vendas",
    actor_field="vendedor_id",
)


# ---- Compras ----


def _validate_compra_create(session: Session, data: Any) -> None:
    validate_cliente_veiculo_fks(session, data)


def _validate_compra_update(session: Session, _obj: Any, data: Any) -> None:
    validate_cliente_veiculo_fks(session, data)


def _sincronizar_caixa_compra(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    """O lançamento de custo do veículo espelha o valor da compra."""
    veiculo_obj = veiculo.get(session, obj.veiculo_id)
    if veiculo_obj is not None:
        caixa.sincronizar_lancamento_veiculo(session, veiculo_obj, actor_id)


register_crud_routes(
    app,
    compra,
    "/compras",
    "Compra",
    read_schema=compra.CompraRead,
    create_schema=compra.CompraCreate,
    update_schema=compra.CompraUpdate,
    before_create=_validate_compra_create,
    before_update=_validate_compra_update,
    after_create=_sincronizar_caixa_compra,
    after_update=_sincronizar_caixa_compra,
    pagina="compras",
    actor_field="usuario_id",
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
    limit: Annotated[int, Query(ge=1, le=AUDITORIA_LIMIT_MAX)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
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
