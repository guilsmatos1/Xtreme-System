"""HTMX routes for veículos — CRUD override (create/update transacionais)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_cliente_dir,
    _uploads_compra_dir,
    _uploads_dir,
    _uploads_procuracao_dir,
    _validar_uploads,
    resolver_cliente,
)
from xtreme_system.api.routes.ui_routes.uploads import salvar_arquivos
from xtreme_system.api.routes.workflows import validate_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.documento_procuracao import core as documento_procuracao
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.veiculo import core as veiculo


def _ctx_form_veiculo(session: Session) -> dict[str, Any]:
    return {
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidor.list_all(session),
        "clientes": cliente.list_all(session),
        "tipos_cliente": list(cliente.TipoCliente),
        "compras_por_veiculo": compra.latest_by_veiculo_ids(
            session, [item.id for item in veiculo.list_all(session)]
        ),
    }


def _ctx_lista_veiculos(
    session: Session, veiculos: list[veiculo.Veiculo]
) -> dict[str, Any]:
    return {
        "compras_por_veiculo": compra.latest_by_veiculo_ids(
            session, [item.id for item in veiculos]
        )
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
    ],
    register_create=False,
    register_update=False,
)


def _ok_veiculo(request: Request, session: Session, user: UIAdmin) -> HTMLResponse:
    veiculos = veiculo.list_all(session)
    return templates.TemplateResponse(
        request,
        "_veiculos_ok.html",
        {"user": user, "veiculos": veiculos, **_ctx_lista_veiculos(session, veiculos)},
    )


def _erro_veiculo(request: Request, session: Session, msg: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_veiculo.html",
        {**_ctx_form_veiculo(session), "veiculo": None, "erro": msg},
        status_code=400,
    )


@app.post("/ui/veiculos/{item_id}")
async def _atualizar_veiculo(
    item_id: int, request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    obj = _found(veiculo.get(session, item_id), "Veículo")
    form = await request.form()

    try:
        data = veiculo.VeiculoUpdate.model_validate(dict(form))
        validate_veiculo_fks(session, data, update=True)
    except (ValidationError, HTTPException) as exc:
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return templates.TemplateResponse(
            request,
            "_form_veiculo.html",
            {**_ctx_form_veiculo(session), "veiculo": obj, "erro": msg},
            status_code=400,
        )

    debitos_raw = str(form.get("debitos") or "").strip()
    debitos = None
    if debitos_raw:
        try:
            debitos = Decimal(debitos_raw.replace(",", "."))
        except Exception:
            return _erro_veiculo(request, session, "Débitos inválidos")

    try:
        atualizado = veiculo.update(session, obj, data)
        compra_atual = compra.get_latest_by_veiculo(session, atualizado.id)
        if compra_atual is not None:
            compra.update(session, compra_atual, compra.CompraUpdate(debitos=debitos))
        caixa.sincronizar_lancamento_veiculo(session, atualizado)
    except IntegrityError:
        session.rollback()
        return _erro_veiculo(request, session, "Veículo já existe")
    return _ok_veiculo(request, session, user)


@app.post("/ui/veiculos")
async def _criar_veiculo(
    request: Request, session: SessionDep, user: UIAdmin
) -> HTMLResponse:
    session.info["usuario_id"] = user.id
    form = await request.form()

    try:
        data = veiculo.VeiculoCreate.model_validate(dict(form))
        validate_veiculo_fks(session, data)
    except (ValidationError, HTTPException) as exc:
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_veiculo(request, session, msg)

    seller, novo_cliente_data, erro = resolver_cliente(
        session,
        form,
        cliente_field="cliente_vendedor_id",
        required_msg="Informe os dados do cliente vendedor",
        invalid_selected_msg="Cliente vendedor inválido ou inexistente",
        invalid_new_msg="Dados do cliente vendedor inválidos",
    )
    if erro:
        return _erro_veiculo(request, session, erro)

    debitos_raw = str(form.get("debitos") or "").strip()
    debitos = None
    if debitos_raw:
        try:
            debitos = Decimal(debitos_raw.replace(",", "."))
        except Exception:
            return _erro_veiculo(request, session, "Débitos inválidos")

    documentos = [
        arquivo
        for arquivo in form.getlist("documentos_cliente")
        if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
    ]
    doc_veiculo = cast(UploadFile | None, form.get("documento_veiculo"))
    docs_procuracao = [
        arquivo
        for arquivo in form.getlist("documentos_procuracao")
        if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
    ]
    comprovantes_pagamento = [
        arquivo
        for arquivo in form.getlist("comprovantes_pagamento")
        if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
    ]
    todos = cast(
        list[UploadFile],
        list(documentos)
        + ([doc_veiculo] if doc_veiculo else [])
        + list(docs_procuracao)
        + list(comprovantes_pagamento),
    )
    erro = _validar_uploads(todos)
    if erro:
        return _erro_veiculo(request, session, erro)

    try:
        obj = veiculo.create(session, data)
        if novo_cliente_data is not None:
            seller = cliente.create(session, novo_cliente_data)
        assert seller is not None  # noqa: S101 -- invariante interna: erro is None garante seller definido
        salvar_arquivos(
            session,
            upload_dir=_uploads_cliente_dir(seller.id),
            url_prefix=f"/static/uploads/clientes/{seller.id}/documentos",
            create_fn=imagem_documento_cliente.create,
            schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
            fk_field="cliente_id",
            fk_id=seller.id,
            arquivos=cast(list[UploadFile], documentos),
        )
        salvar_arquivos(
            session,
            upload_dir=_uploads_dir(obj.id) / "documentos",
            url_prefix=f"/static/uploads/veiculos/{obj.id}/documentos",
            create_fn=documento_veiculo.create,
            schema=documento_veiculo.DocumentoVeiculoCreate,
            fk_field="veiculo_id",
            fk_id=obj.id,
            arquivos=[doc_veiculo] if doc_veiculo else [],
        )
        salvar_arquivos(
            session,
            upload_dir=_uploads_procuracao_dir(obj.id),
            url_prefix=f"/static/uploads/veiculos/{obj.id}/procuracao",
            create_fn=documento_procuracao.create,
            schema=documento_procuracao.DocumentoProcuracaoCreate,
            fk_field="veiculo_id",
            fk_id=obj.id,
            arquivos=cast(list[UploadFile], docs_procuracao),
        )
        nova_compra = compra.create(
            session,
            compra.CompraCreate(
                cliente_id=seller.id,
                veiculo_id=obj.id,
                data_compra=datetime.now(UTC).date(),
                valor_compra=obj.preco,
                debitos=debitos,
            ),
        )
        salvar_arquivos(
            session,
            upload_dir=_uploads_compra_dir(nova_compra.id),
            url_prefix=f"/static/uploads/compras/{nova_compra.id}/comprovantes",
            create_fn=imagem_comprovante_compra.create,
            schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
            fk_field="compra_id",
            fk_id=nova_compra.id,
            arquivos=cast(list[UploadFile], comprovantes_pagamento),
        )
        caixa.criar_lancamento_veiculo(session, obj)
    except IntegrityError:
        session.rollback()
        return _erro_veiculo(request, session, "Veículo já existe")
    veiculos = veiculo.list_all(session)
    return templates.TemplateResponse(
        request,
        "_veiculos_ok.html",
        {"user": user, "veiculos": veiculos, **_ctx_lista_veiculos(session, veiculos)},
    )
