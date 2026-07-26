"""HTMX routes for compras."""

from datetime import UTC, datetime
from typing import Annotated, Any, cast

import structlog
from fastapi import Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_ui.query import sort_key as _sort_key
from xtreme_system.api.crud_ui.responses import rollback_integrity_error_response
from xtreme_system.api.crud_ui.routes import register_crud_ui_routes
from xtreme_system.api.deps import (
    SessionDep,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_compra_dir,
    _validar_uploads,
    criar_aninhado_ou_resposta_conflito,
    resolver_cliente,
    rollback_se_criou_aninhados,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    excluir_anexo_entidade,
    pending_upload_paths,
    remover_orfaos,
    salvar_anexos_entidade,
    salvar_arquivos,
)
from xtreme_system.api.routes.workflows import validate_cliente_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.imagem_comprovante_compra import core as imagem_comprovante_compra
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

logger = structlog.get_logger(__name__)

_EditarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "editar"))
]
_CadastrarCompraDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "cadastrar"))
]
_ExcluirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "excluir_comprovante"))
]
_AbrirComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "abrir_comprovante"))
]
_EnviarComprovanteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("compras", "enviar_comprovante"))
]


def _ctx_form_compra(session: Session) -> dict[str, Any]:
    return {
        "clientes": cliente.list_all(session),
        "data_atual": datetime.now(UTC).date().isoformat(),
        "tipos_cliente": list(cliente.TipoCliente),
        "tipos": list(veiculo.TipoVeiculo),
        "tipo_entradas": list(veiculo.TipoEntrada),
        "investidores": investidor.list_all(session),
    }


def _parse_compra_form(form: Any) -> dict[str, Any]:
    data = dict(form)
    if data.get("debitos") == "":
        data["debitos"] = None
    if data.get("observacoes") == "":
        data["observacoes"] = None
    if not data.get("data_compra"):
        data["data_compra"] = str(datetime.now(UTC).date())
    return data


def _filtrar_campos_ocultos_compra(
    user: usuario.Usuario, data: dict[str, Any]
) -> dict[str, Any]:
    return perfil.filtrar_campos_form_ocultos(user, "compras", data)


def _ctx_lista_compras(
    session: Session, compras: list[compra.Compra]
) -> dict[str, Any]:
    compra_ids = [item.id for item in compras]
    comprovantes_por_compra: dict[
        int, list[imagem_comprovante_compra.ImagemComprovanteCompra]
    ] = {compra_id: [] for compra_id in compra_ids}
    for comprovante in imagem_comprovante_compra.list_by_compra_ids(
        session, compra_ids
    ):
        comprovantes_por_compra[comprovante.compra_id].append(comprovante)
    return {
        "comprovantes_por_compra": comprovantes_por_compra,
    }


def _remover_arquivos_comprovantes(
    session: Session, obj: compra.Compra, _actor_id: int | None = None
) -> None:
    for comprovante in imagem_comprovante_compra.list_by_compra(session, obj.id):
        path = _uploaded_file_path(comprovante.url or "")
        if path is not None:
            _remover_upload(path)


def _deletar_compra_e_veiculo(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    _remover_arquivos_comprovantes(session, obj, actor_id)
    veiculo_obj = veiculo.get(session, obj.veiculo_id)
    if veiculo_obj:
        veiculo.delete(session, veiculo_obj, actor_id)


def _comprovantes_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    compra_id: int,
    erro: str | None = None,
    *,
    action_oob: bool = False,
) -> HTMLResponse:
    item = _found(compra.get(session, compra_id), "Compra")
    comprovantes = imagem_comprovante_compra.list_by_compra(session, compra_id)
    remover_orfaos(session, comprovantes, imagem_comprovante_compra.delete)
    comprovantes = imagem_comprovante_compra.list_by_compra(session, compra_id)
    return templates.TemplateResponse(
        request,
        "_modal_comprovantes_compra.html",
        {
            "compra": item,
            "comprovantes": comprovantes,
            "user": user,
            "erro": erro,
            "action_oob": action_oob,
            "pending_upload_paths": pending_upload_paths(session),
        },
        status_code=400 if erro else 200,
    )


@app.get("/ui/compras/{compra_id}/comprovantes")
def ui_compra_comprovantes(
    request: Request,
    session: SessionDep,
    user: _AbrirComprovanteDep,
    compra_id: int,
) -> HTMLResponse:
    return _comprovantes_modal(request, session, user, compra_id)


@app.post("/ui/compras/{compra_id}/comprovantes")
def ui_compra_comprovantes_upload(
    request: Request,
    session: SessionDep,
    user: _EnviarComprovanteDep,
    compra_id: int,
    comprovantes: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    _found(compra.get(session, compra_id), "Compra")
    erro = salvar_anexos_entidade(
        session,
        upload_dir=_uploads_compra_dir(compra_id),
        url_prefix=f"/static/uploads/compras/{compra_id}/comprovantes",
        create_fn=imagem_comprovante_compra.create,
        schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
        fk_field="compra_id",
        fk_id=compra_id,
        arquivos=comprovantes,
        actor_id=user.id,
    )
    if erro:
        return _comprovantes_modal(request, session, user, compra_id, erro)

    return _comprovantes_modal(request, session, user, compra_id, action_oob=True)


@app.post("/ui/compras/{compra_id}/comprovantes/{comprovante_id}/excluir")
def ui_compra_comprovantes_excluir(
    request: Request,
    session: SessionDep,
    user: _ExcluirComprovanteDep,
    compra_id: int,
    comprovante_id: int,
) -> HTMLResponse:
    comprovante = _found(
        imagem_comprovante_compra.get(session, comprovante_id), "Comprovante"
    )
    excluir_anexo_entidade(
        session,
        anexo=comprovante,
        parent_field="compra_id",
        parent_id=compra_id,
        delete_fn=imagem_comprovante_compra.delete,
        actor_id=user.id,
        not_found_detail="Comprovante não encontrado",
    )
    return _comprovantes_modal(request, session, user, compra_id, action_oob=True)


def _resolver_veiculo(
    session: Session, form: Any
) -> tuple[veiculo.Veiculo | None, veiculo.VeiculoCreate | None, str | None]:
    veiculo_sel = str(form.get("veiculo_id") or "").strip()
    if veiculo_sel:
        try:
            existente = veiculo.get(session, int(veiculo_sel))
        except ValueError:
            existente = None
        if existente is None:
            return None, None, "Veículo inválido ou inexistente"
        return existente, None, None

    placa = str(form.get("vei_placa") or "").strip().upper()
    if not placa:
        return None, None, "Informe a placa do veículo"
    if veiculo.get_by_placa(session, placa):
        return None, None, "Placa já cadastrada — selecione o veículo na lista"
    try:
        novo_veiculo_data = veiculo.VeiculoCreate.model_validate(
            {
                "tipo": form.get("vei_tipo"),
                "tipo_entrada": form.get("vei_tipo_entrada"),
                "placa": placa,
                "modelo": str(form.get("vei_modelo") or "").strip(),
                "marca": str(form.get("vei_marca") or "").strip() or None,
                "cor": str(form.get("vei_cor") or "").strip(),
                "ano": int(form.get("vei_ano") or 0),
                "km": str(form.get("vei_km") or "").strip() or None,
                "chassi": str(form.get("vei_chassi") or "").strip() or None,
                "renavam": str(form.get("vei_renavam") or "").strip() or None,
                "preco": str(form.get("valor_compra") or "").strip(),
                "proprietario_registrado": str(
                    form.get("vei_proprietario_registrado") or ""
                ).strip()
                or None,
                "investidor_id": int(form.get("vei_investidor_id") or 0),
            }
        )
    except (ValidationError, ValueError):
        return None, None, "Dados do veículo inválidos"
    return None, novo_veiculo_data, None


def _erro_compra(
    request: Request, session: Session, user: usuario.Usuario, msg: str
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_form_compra.html",
        {**_ctx_form_compra(session), "compra": None, "user": user, "erro": msg},
        status_code=400,
    )


def _ok_compra(request: Request, session: Session, user: Any) -> HTMLResponse:
    compras = compra.list_all(session)
    return templates.TemplateResponse(
        request,
        "_compras_ok.html",
        {"user": user, "compras": compras},
    )


@app.post("/ui/compras")
async def _criar_compra(  # noqa: PLR0911
    request: Request, session: SessionDep, user: _CadastrarCompraDep
) -> HTMLResponse:
    form = await request.form()

    comprovantes = cast(
        list[UploadFile],
        [
            arquivo
            for arquivo in form.getlist("comprovantes_pagamento")
            if hasattr(arquivo, "filename") and hasattr(arquivo, "file")
        ],
    )
    if not perfil.pode_operacao(user, "compras", "enviar_comprovante"):
        comprovantes = []
    erro = _validar_uploads(comprovantes)
    if erro:
        return _erro_compra(request, session, user, erro)

    cliente_obj, novo_cliente_data, erro = resolver_cliente(session, form)
    if erro:
        return _erro_compra(request, session, user, erro)

    veiculo_obj, novo_veiculo_data, erro = _resolver_veiculo(session, form)
    if erro:
        return _erro_compra(request, session, user, erro)

    novo_cliente_obj, response = criar_aninhado_ou_resposta_conflito(
        session,
        novo_cliente_data,
        cliente.create,
        user.id,
        lambda: _erro_compra(request, session, user, "Cliente já existe"),
    )
    if response is not None:
        return response
    if novo_cliente_obj is not None:
        cliente_obj = novo_cliente_obj

    novo_veiculo_obj, response = criar_aninhado_ou_resposta_conflito(
        session,
        novo_veiculo_data,
        veiculo.create,
        user.id,
        lambda: _erro_compra(request, session, user, "Veículo já existe"),
    )
    if response is not None:
        return response
    if novo_veiculo_obj is not None:
        veiculo_obj = novo_veiculo_obj

    assert cliente_obj is not None  # noqa: S101
    assert veiculo_obj is not None  # noqa: S101

    try:
        data = compra.CompraCreate.model_validate(
            _filtrar_campos_ocultos_compra(
                user,
                {
                    **_parse_compra_form(form),
                    "cliente_id": cliente_obj.id,
                    "veiculo_id": veiculo_obj.id,
                    "usuario_id": user.id,
                },
            )
        )
        validate_cliente_veiculo_fks(session, data)
    except (ValidationError, HTTPException) as exc:
        rollback_se_criou_aninhados(session, novo_cliente_data, novo_veiculo_data)
        msg = exc.detail if isinstance(exc, HTTPException) else "Dados inválidos"
        return _erro_compra(request, session, user, msg)

    try:
        obj = compra.create(session, data, user.id)
        salvar_arquivos(
            session,
            upload_dir=_uploads_compra_dir(obj.id),
            url_prefix=f"/static/uploads/compras/{obj.id}/comprovantes",
            create_fn=imagem_comprovante_compra.create,
            schema=imagem_comprovante_compra.ImagemComprovanteCompraCreate,
            fk_field="compra_id",
            fk_id=obj.id,
            arquivos=comprovantes,
            actor_id=user.id,
        )
    except IntegrityError:
        return rollback_integrity_error_response(
            session, lambda: _erro_compra(request, session, user, "Compra já existe")
        )
    return _ok_compra(request, session, user)


register_crud_ui_routes(
    app,
    templates,
    compra,
    "/ui/compras",
    "Compra",
    create_schema=compra.CompraCreate,
    update_schema=compra.CompraUpdate,
    list_key="compras",
    item_key="compra",
    list_template="compras.html",
    list_partial_template="_linhas_compras.html",
    ok_partial_template="_compras_ok.html",
    form_template="_form_compra.html",
    ctx_form=_ctx_form_compra,
    ctx_list=_ctx_lista_compras,
    searchable=True,
    search_func=compra.search,
    parse_form=_parse_compra_form,
    before_create=validate_cliente_veiculo_fks,
    before_update=validate_cliente_veiculo_fks,
    before_delete=_deletar_compra_e_veiculo,
    register_create=False,
    cadastrar_dep=require_operacao("compras", "cadastrar"),
    sort_fields={
        "cliente": lambda c: _sort_key(c.cliente.nome),
        "documento": lambda c: _sort_key(c.cliente.documento or ""),
        "modelo": lambda c: _sort_key(c.veiculo.modelo),
        "placa": lambda c: _sort_key(c.veiculo.placa),
        "data": "data_compra",
        "valor": "valor_compra",
        "status": "status",
        "observacoes": lambda c: _sort_key(c.observacoes or ""),
        "usuario": lambda c: _sort_key(
            (c.usuario.nome or c.usuario.username) if c.usuario else ""
        ),
    },
    sql_sort_fields={
        "cliente": cliente.Cliente.nome,
        "documento": cliente.Cliente.documento,
        "modelo": veiculo.Veiculo.modelo,
        "placa": veiculo.Veiculo.placa,
        "data": compra.Compra.data_compra,
        "valor": compra.Compra.valor_compra,
        "status": compra.Compra.status,
        "observacoes": compra.Compra.observacoes,
        "usuario": usuario.Usuario.nome,
    },
    query_func=compra.query,
    search_query_func=compra.search_query,
    csv_filename="compras.csv",
    csv_headers=[
        "ID",
        "Data",
        "Nome do Cliente",
        "Documento do Cliente",
        "Estado",
        "Placa",
        "Veiculo",
        "Valor Compra",
        "Observacoes",
        "Usuario",
    ],
    csv_fields=[
        None,
        "data_compra",
        "cliente",
        "documento_cliente",
        "status",
        "placa",
        "veiculo",
        "valor_compra",
        "observacoes",
        "usuario",
    ],
    csv_row=lambda c: [
        c.id,
        c.data_compra.isoformat(),
        c.cliente.nome,
        c.cliente.documento or "",
        c.status.value,
        c.veiculo.placa,
        c.veiculo.modelo,
        f"{c.valor_compra:.2f}",
        c.observacoes or "",
        (c.usuario.nome or c.usuario.username) if c.usuario else "",
    ],
    editar_dep=require_operacao("compras", "editar"),
    excluir_dep=require_operacao("compras", "excluir"),
    pagina="compras",
)
