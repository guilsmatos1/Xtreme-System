"""HTMX routes for veículos — CRUD override (create/update transacionais)."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.query import query_list
from xtreme_system.api.crud_ui.responses import delete_conflict_detail, list_response
from xtreme_system.api.crud_writes import delete_with_hook
from xtreme_system.api.deps import SessionDep, _found, require_operacao, templates
from xtreme_system.api.route_factories import register_crud_ui_routes
from xtreme_system.api.routes.workflows import validate_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

# Campos do form.html que só devem ser aplicados se o perfil puder vê-los.
_CAMPO_FORM_MAP = {
    "modelo": "modelo",
    "placa": "placa",
    "tipo": "tipo",
    "ano": "ano",
    "km": "km",
    "status": "status",
    "preco": "preco",
    "tipo_entrada": "tipo_entrada",
    "investidor": "investidor_id",
    "procuracao": "procuracao",
    "revisao": "revisao",
    "debitos": "debitos",
}


def _ctx_form_veiculo(session: Session) -> dict[str, Any]:
    compras_por_veiculo = compra.latest_by_veiculo_ids(
        session, [item.id for item in veiculo.list_all(session)]
    )
    return {
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidor.list_all(session),
        "clientes": cliente.list_all(session),
        "tipos_cliente": list(cliente.TipoCliente),
        "compras_por_veiculo": compras_por_veiculo,
    }


def _ctx_lista_veiculos(
    session: Session, veiculos: list[veiculo.Veiculo]
) -> dict[str, Any]:
    compras_por_veiculo = compra.latest_by_veiculo_ids(
        session, [item.id for item in veiculos]
    )
    return {
        "compras_por_veiculo": compras_por_veiculo,
    }


register_crud_ui_routes(
    app,
    templates,
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
    ctx_list=_ctx_lista_veiculos,
    searchable=True,
    before_create=validate_veiculo_fks,
    before_update=lambda session, data: validate_veiculo_fks(
        session, data, update=True
    ),
    before_delete=caixa.deletar_lancamento_veiculo,
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
        "tempo_estoque": "criado_em",
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
        "Estado",
        "Tipo de Entrada",
        "Revisao",
        "Investidor",
        "Procurador",
        "Tempo de Estoque",
    ],
    csv_fields=[
        None,
        "modelo",
        "placa",
        "tipo",
        "ano",
        "km",
        "preco",
        "status",
        "tipo_entrada",
        "revisao",
        "investidor",
        "procuracao",
        "tempo_estoque",
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
        f"{v.tempo_estoque} dias",
    ],
    pagina="veiculos",
    register_create=False,
    register_update=False,
    register_edit=False,
    register_delete=False,
)

_EditarDep = Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))]
_ExcluirDep = Annotated[
    usuario.Usuario, Depends(require_operacao("veiculos", "excluir"))
]


@app.get("/ui/veiculos/{item_id}/editar")
def _editar_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _EditarDep
) -> HTMLResponse:
    obj = _found(veiculo.get(session, item_id), "Veículo")
    return templates.TemplateResponse(
        request,
        "_form_veiculo.html",
        {**_ctx_form_veiculo(session), "veiculo": obj, "user": user},
    )


@app.post("/ui/veiculos/{item_id}/excluir")
def _excluir_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _ExcluirDep
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    obj = _found(veiculo.get(session, item_id), "Veículo")
    erro = None
    status_code = 200
    try:
        delete_with_hook(
            veiculo,
            session,
            obj,
            caixa.deletar_lancamento_veiculo,
            user.id,
        )
    except IntegrityError:
        session.rollback()
        erro = delete_conflict_detail("Veículo")
        status_code = 409
    lista = query_list(
        session, veiculo, q="", searchable=True, list_func=None, search_func=None
    )
    return list_response(
        templates,
        request,
        "_linhas_veiculos.html",
        user=user,
        list_key="veiculos",
        lista=lista,
        ctx_list=_ctx_lista_veiculos(session, lista),
        erro=erro,
        status_code=status_code,
    )


def _ok_veiculo(
    request: Request, session: Session, user: usuario.Usuario
) -> HTMLResponse:
    veiculos = veiculo.list_all(session)
    return templates.TemplateResponse(
        request,
        "_veiculos_ok.html",
        {"user": user, "veiculos": veiculos, **_ctx_lista_veiculos(session, veiculos)},
    )


def _erro_veiculo(
    request: Request, session: Session, user: usuario.Usuario, msg: str
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_veiculo.html",
        {**_ctx_form_veiculo(session), "veiculo": None, "user": user, "erro": msg},
        status_code=400,
    )


@app.post("/ui/veiculos/{item_id}")
async def _atualizar_veiculo(
    item_id: int, request: Request, session: SessionDep, user: _EditarDep
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    obj = _found(veiculo.get(session, item_id), "Veículo")
    form = await request.form()
    dados_form = dict(form)
    for campo, campo_form in _CAMPO_FORM_MAP.items():
        if not perfil.pode_ver_campo(user, "veiculos", campo):
            dados_form.pop(campo_form, None)

    try:
        data = veiculo.VeiculoUpdate.model_validate(dados_form)
        validate_veiculo_fks(session, data, update=True)
    except (ValidationError, HTTPException) as exc:
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return templates.TemplateResponse(
            request,
            "_form_veiculo.html",
            {**_ctx_form_veiculo(session), "veiculo": obj, "user": user, "erro": msg},
            status_code=400,
        )

    debitos = None
    if perfil.pode_ver_campo(user, "veiculos", "debitos"):
        debitos_raw = str(form.get("debitos") or "").strip()
        if debitos_raw:
            try:
                debitos = Decimal(debitos_raw.replace(",", "."))
            except Exception:
                return _erro_veiculo(request, session, user, "Débitos inválidos")

    try:
        atualizado = veiculo.update(session, obj, data, user.id)
        compra_atual = compra.get_latest_by_veiculo(session, atualizado.id)
        if compra_atual is not None and perfil.pode_ver_campo(
            user, "veiculos", "debitos"
        ):
            compra.update(
                session,
                compra_atual,
                compra.CompraUpdate(debitos=debitos),
                user.id,
            )
        caixa.sincronizar_lancamento_veiculo(session, atualizado)
    except IntegrityError:
        session.rollback()
        return _erro_veiculo(request, session, user, "Veículo já existe")
    return _ok_veiculo(request, session, user)
