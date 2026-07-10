"""Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, UIUser, _found, templates
from xtreme_system.api.route_factories import (
    _csv_response,
    _sort_key,
    register_crud_ui_routes,
    register_ui_simples,
)
from xtreme_system.api.routes.json import _validate_fks, _validate_venda_fks
from xtreme_system.api.setup import app
from xtreme_system.auth import core as auth
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda

# ---- Clientes (UI) ----


def _ctx_form_cliente(_session: Session) -> dict[str, Any]:
    return {"tipos": list(cliente.TipoCliente)}


register_crud_ui_routes(
    app,
    cliente,
    "/ui/clientes",
    "Cliente",
    create_schema=cliente.ClienteCreate,
    update_schema=cliente.ClienteUpdate,
    list_key="clientes",
    item_key="cliente",
    list_template="clientes.html",
    list_partial_template="_linhas_clientes.html",
    ok_partial_template="_clientes_ok.html",
    form_template="_form_cliente.html",
    ctx_form=_ctx_form_cliente,
    searchable=True,
    sort_fields={
        "nome": "nome",
        "documento": "documento",
        "tipo": "tipo",
        "cidade": "cidade",
        "estado": "estado",
        "ativo": "ativo",
    },
    csv_filename="clientes.csv",
    csv_headers=["ID", "Nome", "CPF", "Tipo", "Cidade", "Estado", "Ativo"],
    csv_row=lambda c: [
        c.id,
        c.nome,
        c.documento,
        c.tipo.value,
        c.cidade or "",
        c.estado or "",
        "sim" if c.ativo else "nao",
    ],
)


# ---- Vendas (UI) ----


def _ctx_form_venda(session: Session) -> dict[str, Any]:
    veiculos = veiculo.list_all(session)
    veiculos_disponiveis = [
        v for v in veiculos if v.status == veiculo.StatusVeiculo.disponivel
    ]
    return {
        "clientes": cliente.list_all(session),
        "veiculos": veiculos_disponiveis,
        "status": list(venda.StatusVenda),
    }


def _parse_venda_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("valor_entrada") == "":
        data["valor_entrada"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_venda"):
        data["data_venda"] = str(date.today())
    return data


register_crud_ui_routes(
    app,
    venda,
    "/ui/vendas",
    "Venda",
    create_schema=venda.VendaCreate,
    update_schema=venda.VendaUpdate,
    list_key="vendas",
    item_key="venda",
    list_template="vendas.html",
    list_partial_template="_linhas_vendas.html",
    ok_partial_template="_vendas_ok.html",
    form_template="_form_venda.html",
    ctx_form=_ctx_form_venda,
    parse_form=_parse_venda_form,
    before_create=_validate_venda_fks,
    before_update=_validate_venda_fks,
    sort_fields={
        "cliente": lambda v: _sort_key(v.cliente.nome),
        "veiculo": lambda v: _sort_key(v.veiculo.modelo),
        "data": "data_venda",
        "valor": "valor_venda",
        "entrada": "valor_entrada",
        "pagamento": "forma_pagamento",
        "parcelas": "parcelas",
        "status": "status",
    },
    csv_filename="vendas.csv",
    csv_headers=[
        "ID",
        "Cliente",
        "Veiculo",
        "Data",
        "Valor Venda",
        "Valor Entrada",
        "Forma Pagamento",
        "Parcelas",
        "Status",
        "Observacoes",
    ],
    csv_row=lambda v: [
        v.id,
        v.cliente.nome,
        f"{v.veiculo.modelo} ({v.veiculo.placa})",
        v.data_venda.isoformat(),
        f"{v.valor_venda:.2f}",
        f"{v.valor_entrada:.2f}" if v.valor_entrada is not None else "",
        v.forma_pagamento,
        v.parcelas,
        v.status.value,
        v.observacoes or "",
    ],
)


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
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidor.list_all(session),
        "meios": meio_captacao.list_all(session),
    }


register_crud_ui_routes(
    app,
    veiculo,
    "/ui/veiculos",
    "Veículo",
    create_schema=veiculo.VeiculoCreate,
    update_schema=veiculo.VeiculoUpdate,
    list_key="veiculos",
    item_key="veiculo",
    list_template="veiculos.html",
    list_partial_template="_linhas_veiculos.html",
    ok_partial_template="_veiculos_ok.html",
    form_template="_form_veiculo.html",
    ctx_form=_ctx_form_veiculo,
    searchable=True,
    before_create=_validate_fks,
    before_update=lambda session, data: _validate_fks(session, data, update=True),
    after_create=caixa.criar_lancamento_veiculo,
    after_update=caixa.sincronizar_lancamento_veiculo,
    sort_fields={
        "modelo": "modelo",
        "placa": "placa",
        "tipo": "tipo",
        "ano": "ano",
        "km": "km",
        "preco": "preco",
        "status": "status",
        "tipo_entrada": "tipo_entrada",
        "revisao": "revisao",
        "investidor": "investidor",
        "procuracao": "procuracao",
        "captacao": "meio_captacao",
    },
    csv_filename="veiculos.csv",
    csv_headers=[
        "ID",
        "Modelo",
        "Placa",
        "Tipo",
        "Ano",
        "KM",
        "Preco",
        "Status",
        "Tipo de Entrada",
        "Revisao",
        "Investidor",
        "Procurador",
        "Captacao",
    ],
    csv_row=lambda v: [
        v.id,
        v.modelo,
        v.placa,
        v.tipo.value,
        v.ano,
        v.km,
        f"{v.preco:.2f}",
        v.status.value,
        v.tipo_entrada.value,
        "Sim" if v.revisao else "Não",
        v.investidor.nome,
        v.procuracao or "",
        v.meio_captacao.nome,
    ],
)


# ---- Caixa dos investidores (UI) ----


_LANCAMENTO_SORT_FIELDS: dict[str, str] = {
    "data": "criado_em",
    "tipo": "tipo",
    "descricao": "descricao",
    "valor": "valor",
}


def _ctx_lancamentos(
    session: Session, investidor_id: int, sort: str = "", order: str = "asc"
) -> dict[str, Any]:
    lancamentos = caixa.list_by_investidor(session, investidor_id)
    field = _LANCAMENTO_SORT_FIELDS.get(sort)
    if field:
        lancamentos = sorted(
            lancamentos,
            key=lambda lanc: _sort_key(getattr(lanc, field)),
            reverse=order == "desc",
        )
    return {
        "investidor": _found(investidor.get(session, investidor_id), "Investidor"),
        "lancamentos": lancamentos,
        "saldo": caixa.saldo(session, investidor_id),
        "sort": sort,
        "order": order,
    }


def _ok_lancamentos(
    request: Request, session: Session, user: usuario.Usuario, investidor_id: int
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_lancamentos_ok.html",
        {"user": user, **_ctx_lancamentos(session, investidor_id)},
    )


def _erro_lancamento(
    request: Request,
    investidor_id: int,
    exc: ValidationError | HTTPException,
    obj: caixa.LancamentoInvestimento | None,
) -> HTMLResponse:
    erro = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": obj,
            "tipos": list(caixa.TipoLancamento),
            "erro": erro,
        },
        status_code=400,
    )


@app.get("/ui/caixa")
def ui_caixa(
    request: Request,
    session: SessionDep,
    user: UIUser,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_veiculos, valor_veiculos, total_aportado = caixa.agregados_investidores(session)
    reverse = order == "desc"
    if sort == "investidor":
        investidores = sorted(
            investidores, key=lambda i: _sort_key(i.nome), reverse=reverse
        )
    elif sort == "saldo":
        investidores = sorted(
            investidores, key=lambda i: saldos.get(i.id, 0), reverse=reverse
        )
    elif sort == "num_veiculos":
        investidores = sorted(
            investidores, key=lambda i: num_veiculos.get(i.id, 0), reverse=reverse
        )
    elif sort == "valor_veiculos":
        investidores = sorted(
            investidores,
            key=lambda i: valor_veiculos.get(i.id, Decimal("0")),
            reverse=reverse,
        )
    elif sort == "total_investido":
        investidores = sorted(
            investidores,
            key=lambda i: total_aportado.get(i.id, Decimal("0")),
            reverse=reverse,
        )
    return templates.TemplateResponse(
        request,
        "caixa.html",
        {
            "user": user,
            "investidores": investidores,
            "saldos": saldos,
            "num_veiculos": num_veiculos,
            "valor_veiculos": valor_veiculos,
            "total_aportado": total_aportado,
            "sort": sort,
            "order": order,
        },
    )


@app.get("/ui/caixa/exportar")
def ui_caixa_exportar(session: SessionDep, _: UIUser) -> Response:
    investidores = investidor.list_all(session)
    saldos = caixa.saldos(session)
    num_v, val_v, tot_a = caixa.agregados_investidores(session)
    return _csv_response(
        "caixa.csv",
        ["Investidor", "Saldo", "N° Veículos", "Valor em Veículos", "Total Investido"],
        [
            [
                i.nome,
                f"{saldos.get(i.id, Decimal('0')):.2f}",
                num_v.get(i.id, 0),
                f"{val_v.get(i.id, Decimal('0')):.2f}",
                f"{tot_a.get(i.id, Decimal('0')):.2f}",
            ]
            for i in investidores
        ],
    )


@app.get("/ui/caixa/{investidor_id}")
def ui_caixa_investidor(
    investidor_id: int,
    request: Request,
    session: SessionDep,
    user: UIUser,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    ctx = {
        "user": user,
        "investidor_id": investidor_id,
        **_ctx_lancamentos(session, investidor_id, sort, order),
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_linhas_lancamentos.html", ctx)
    return templates.TemplateResponse(request, "caixa_investidor.html", ctx)


@app.get("/ui/caixa/{investidor_id}/exportar")
def ui_caixa_investidor_exportar(
    investidor_id: int, session: SessionDep, _: UIUser
) -> Response:
    investidor_obj = _found(investidor.get(session, investidor_id), "Investidor")
    lancamentos = caixa.list_by_investidor(session, investidor_id)
    return _csv_response(
        f"caixa-{investidor_obj.nome}.csv",
        ["Data", "Tipo", "Descricao", "Valor"],
        [
            [
                lanc.criado_em.isoformat(),
                lanc.tipo.value,
                lanc.descricao or "",
                f"{lanc.valor:.2f}",
            ]
            for lanc in lancamentos
        ],
    )


@app.get("/ui/caixa/{investidor_id}/novo")
def ui_lancamento_novo(
    investidor_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    _found(investidor.get(session, investidor_id), "Investidor")
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": None,
            "tipos": list(caixa.TipoLancamento),
        },
    )


@app.get("/ui/caixa/{investidor_id}/{lancamento_id}/editar")
def ui_lancamento_editar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    _: UIAdmin,
) -> HTMLResponse:
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=403, detail="Editável apenas na tela de Veículos"
        )
    return templates.TemplateResponse(
        request,
        "_form_lancamento.html",
        {
            "investidor_id": investidor_id,
            "lancamento": obj,
            "tipos": list(caixa.TipoLancamento),
        },
    )


@app.post("/ui/caixa/{investidor_id}")
async def ui_lancamento_criar(
    investidor_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    _found(investidor.get(session, investidor_id), "Investidor")
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoCreate.model_validate(
            {**dict(form), "investidor_id": investidor_id}
        )
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, None)
    caixa.create(session, data)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/caixa/{investidor_id}/{lancamento_id}")
async def ui_lancamento_atualizar(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=403, detail="Editável apenas na tela de Veículos"
        )
    form = await request.form()
    try:
        data = caixa.LancamentoInvestimentoUpdate.model_validate(dict(form))
    except ValidationError as exc:
        return _erro_lancamento(request, investidor_id, exc, obj)
    caixa.update(session, obj, data)
    return _ok_lancamentos(request, session, user, investidor_id)


@app.post("/ui/caixa/{investidor_id}/{lancamento_id}/excluir")
def ui_lancamento_excluir(
    investidor_id: int,
    lancamento_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
) -> HTMLResponse:
    obj = _found(caixa.get(session, lancamento_id), "Lançamento")
    if obj.origem == caixa.OrigemLancamento.veiculo:
        raise HTTPException(
            status_code=403, detail="Exclusão apenas na tela de Veículos"
        )
    caixa.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "_linhas_lancamentos.html",
        {
            "user": user,
            "investidor_id": investidor_id,
            **_ctx_lancamentos(session, investidor_id),
        },
    )


# ---- Usuários (UI, admin) ----


_USUARIO_SORT_FIELDS: dict[str, str] = {
    "id": "id",
    "username": "username",
    "papel": "papel",
    "ativo": "ativo",
}


@app.get("/ui/usuarios")
def ui_usuarios(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    sort: str = "",
    order: str = "asc",
) -> HTMLResponse:
    usuarios = usuario.list_all(session)
    field = _USUARIO_SORT_FIELDS.get(sort)
    if field:
        usuarios = sorted(
            usuarios,
            key=lambda u: _sort_key(getattr(u, field)),
            reverse=order == "desc",
        )
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {"user": user, "usuarios": usuarios, "sort": sort, "order": order},
    )


@app.get("/ui/usuarios/exportar")
def ui_usuarios_exportar(session: SessionDep, _: UIAdmin) -> Response:
    usuarios = usuario.list_all(session)
    return _csv_response(
        "usuarios.csv",
        ["ID", "Usuario", "Papel", "Ativo"],
        [
            [u.id, u.username, u.papel.value, "sim" if u.ativo else "nao"]
            for u in usuarios
        ],
    )


@app.post("/ui/usuarios")
def ui_usuario_criar(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    username: Annotated[str, Form()],
    senha: Annotated[str, Form()],
    papel: Annotated[usuario.Papel, Form()] = usuario.Papel.vendedor,
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


@app.post("/ui/usuarios/{user_id}/excluir")
def ui_usuario_excluir(
    user_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    if user_id == user.id:
        return templates.TemplateResponse(
            request,
            "usuarios.html",
            {
                "user": user,
                "usuarios": usuario.list_all(session),
                "erro": "não pode excluir a si mesmo",
            },
            status_code=400,
        )
    obj = _found(usuario.get(session, user_id), "Usuário")
    usuario.delete(session, obj)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "sort": "",
            "order": "asc",
        },
    )


@app.get("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_form(
    user_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
    return templates.TemplateResponse(request, "_form_senha.html", {"usuario": obj})


@app.post("/ui/usuarios/{user_id}/senha")
def ui_usuario_senha_alterar(
    user_id: int,
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    nova_senha: Annotated[str, Form()],
) -> HTMLResponse:
    obj = _found(usuario.get(session, user_id), "Usuário")
    usuario.change_password(session, obj, nova_senha)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "user": user,
            "usuarios": usuario.list_all(session),
            "sort": "",
            "order": "asc",
        },
    )


# ---- Investidores / Meios de captação (UI, mesmo padrão) ----


register_ui_simples(
    app,
    "/ui/investidores",
    "Investidores",
    investidor,
    investidor.InvestidorCreate,
    investidor.InvestidorUpdate,
    "investidores.csv",
)
register_ui_simples(
    app,
    "/ui/meios-captacao",
    "Meios de captação",
    meio_captacao,
    meio_captacao.MeioCaptacaoCreate,
    meio_captacao.MeioCaptacaoUpdate,
    "meios-captacao.csv",
)
