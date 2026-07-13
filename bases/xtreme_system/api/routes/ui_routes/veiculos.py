"""HTMX routes for veiculos."""

import contextlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import uuid4

import structlog
from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, UIAdmin, _found, templates
from xtreme_system.api.route_factories import register_crud_ui_routes
from xtreme_system.api.routes.ui_routes.common import (
    _remover_upload,
    _uploaded_file_path,
    _uploads_cliente_dir,
    _uploads_dir,
    _validar_uploads,
)
from xtreme_system.api.routes.workflows import validate_veiculo_fks
from xtreme_system.api.setup import app
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.imagem_veiculo import core as imagem_veiculo
from xtreme_system.investidor import core as investidor
from xtreme_system.veiculo import core as veiculo

logger = structlog.get_logger(__name__)

# ---- Veículos (UI) ----


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


def _imagem_modal(request: Request, session: Session, veiculo_id: int) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    for img in list(item.imagens):
        path = _uploaded_file_path(img.url or "")
        if path is not None and not path.exists():
            imagem_veiculo.delete(session, img)
    session.refresh(item)
    return templates.TemplateResponse(
        request, "_modal_imagens_veiculo.html", {"veiculo": item}
    )


@app.get("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    return _imagem_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/imagens")
def ui_veiculo_imagens_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    imagens: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    erro = _validar_uploads(imagens)
    if erro:
        return templates.TemplateResponse(
            request,
            "_modal_imagens_veiculo.html",
            {"veiculo": item, "erro": erro},
            status_code=400,
        )
    upload_dir = _uploads_dir(veiculo_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    for imagem in imagens:
        if not imagem.filename:
            continue
        suffix = Path(imagem.filename).suffix.lower()
        filename = f"{uuid4().hex}{suffix}"
        path = upload_dir / filename
        with path.open("wb") as f:
            f.write(imagem.file.read())
        try:
            imagem_veiculo.create(
                session,
                imagem_veiculo.ImagemVeiculoCreate(
                    veiculo_id=veiculo_id,
                    url=f"/static/uploads/veiculos/{veiculo_id}/{filename}",
                ),
            )
        except Exception:
            _remover_upload(path)
            raise
    return _imagem_modal(request, session, veiculo_id)


@app.post("/ui/veiculos/{veiculo_id}/imagens/{img_id}/excluir")
def ui_veiculo_imagens_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
    img_id: int,
) -> HTMLResponse:
    img = _found(imagem_veiculo.get(session, img_id), "Imagem")
    if img.veiculo_id != veiculo_id:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    url = img.url or ""
    imagem_veiculo.delete(session, img)
    path = _uploaded_file_path(url)
    if path is not None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
    return _imagem_modal(request, session, veiculo_id)


def _salvar_documentos_cliente(
    session: Session, cliente_id: int, documentos: list[UploadFile]
) -> None:
    upload_dir = _uploads_cliente_dir(cliente_id)
    for documento in documentos:
        if not documento.filename:
            continue
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(documento.filename).suffix.lower()
        filename = f"{uuid4().hex}{suffix}"
        path = upload_dir / filename
        with path.open("wb") as f:
            f.write(documento.file.read())
        try:
            imagem_documento_cliente.create(
                session,
                imagem_documento_cliente.ImagemDocumentoClienteCreate(
                    cliente_id=cliente_id,
                    url=f"/static/uploads/clientes/{cliente_id}/documentos/{filename}",
                ),
            )
        except Exception:
            _remover_upload(path)
            raise


def _salvar_documento_veiculo(
    session: Session, veiculo_id: int, arquivo: UploadFile | None
) -> None:
    if not arquivo or not arquivo.filename:
        return
    upload_dir = _uploads_dir(veiculo_id) / "documentos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(arquivo.filename).suffix.lower()
    filename = f"{uuid4().hex}{suffix}"
    path = upload_dir / filename
    with path.open("wb") as f:
        f.write(arquivo.file.read())
    try:
        documento_veiculo.create(
            session,
            documento_veiculo.DocumentoVeiculoCreate(
                veiculo_id=veiculo_id,
                url=f"/static/uploads/veiculos/{veiculo_id}/documentos/{filename}",
            ),
        )
    except Exception:
        _remover_upload(path)
        raise


@app.get("/ui/veiculos/{veiculo_id}/cliente-vendedor")
def ui_veiculo_cliente_vendedor(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    veiculo_id: int,
) -> HTMLResponse:
    item = _found(veiculo.get(session, veiculo_id), "Veículo")
    item_compra = compra.get_latest_by_veiculo(session, veiculo_id)
    documentos = []
    if item_compra is not None:
        documentos = imagem_documento_cliente.list_by_cliente(
            session, item_compra.cliente_id
        )
    return templates.TemplateResponse(
        request,
        "_modal_cliente_vendedor.html",
        {"veiculo": item, "compra": item_compra, "documentos": documentos},
    )


def _documentos_modal(
    request: Request,
    session: Session,
    cliente_id: int,
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    for doc in list(item.documentos):
        path = _uploaded_file_path(doc.url or "")
        if path is not None and not path.exists():
            imagem_documento_cliente.delete(session, doc)
    session.refresh(item)
    return templates.TemplateResponse(
        request, "_modal_documentos_cliente.html", {"cliente": item}
    )


@app.get("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
) -> HTMLResponse:
    return _documentos_modal(request, session, cliente_id)


@app.post("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos_upload(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    erro = _validar_uploads(documentos)
    if erro:
        return templates.TemplateResponse(
            request,
            "_modal_documentos_cliente.html",
            {"cliente": item, "erro": erro},
            status_code=400,
        )
    _salvar_documentos_cliente(session, cliente_id, documentos)
    return _documentos_modal(request, session, cliente_id)


@app.post("/ui/clientes/{cliente_id}/documentos/{doc_id}/excluir")
def ui_cliente_documentos_excluir(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
    doc_id: int,
) -> HTMLResponse:
    doc = _found(imagem_documento_cliente.get(session, doc_id), "Documento")
    if doc.cliente_id != cliente_id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    url = doc.url or ""
    imagem_documento_cliente.delete(session, doc)
    path = _uploaded_file_path(url)
    if path is not None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
    return _documentos_modal(request, session, cliente_id)


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

    atualizado = veiculo.update(session, obj, data)
    compra_atual = compra.get_latest_by_veiculo(session, atualizado.id)
    if compra_atual is not None:
        compra.update(session, compra_atual, compra.CompraUpdate(debitos=debitos))
    caixa.sincronizar_lancamento_veiculo(session, atualizado)
    return _ok_veiculo(request, session, user)


def _resolver_vendedor(
    session: Session, form: Any
) -> tuple[cliente.Cliente | None, cliente.ClienteCreate | None, str | None]:
    """Retorna (cliente_existente, dados_novo_cliente, erro)."""
    cliente_sel = str(form.get("cliente_vendedor_id") or "").strip()
    if cliente_sel:
        try:
            seller = cliente.get(session, int(cliente_sel))
        except ValueError:
            seller = None
        if seller is None:
            return None, None, "Cliente vendedor inválido ou inexistente"
        return seller, None, None

    nome = str(form.get("cli_nome") or "").strip()
    documento = str(form.get("cli_documento") or "").strip()
    erro: str | None = None
    if not nome or not documento:
        erro = "Informe os dados do cliente vendedor"
    elif cliente.get_by_documento(session, documento):
        erro = "CPF já cadastrado — selecione o cliente na lista"
    if erro:
        return None, None, erro
    try:
        novo_cliente_data = cliente.ClienteCreate.model_validate(
            {
                "nome": nome,
                "documento": documento,
                "tipo": form.get("cli_tipo") or "pessoa_fisica",
                "telefone": str(form.get("cli_telefone") or "").strip() or None,
                "email": str(form.get("cli_email") or "").strip() or None,
                "endereco": str(form.get("cli_endereco") or "").strip() or None,
                "cidade": str(form.get("cli_cidade") or "").strip() or None,
                "estado": str(form.get("cli_estado") or "").strip() or None,
                "cep": str(form.get("cli_cep") or "").strip() or None,
            }
        )
    except ValidationError:
        return None, None, "Dados do cliente vendedor inválidos"
    return None, novo_cliente_data, None


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

    seller, novo_cliente_data, erro = _resolver_vendedor(session, form)
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
    todos = cast(
        list[UploadFile], list(documentos) + ([doc_veiculo] if doc_veiculo else [])
    )
    erro = _validar_uploads(todos)
    if erro:
        return _erro_veiculo(request, session, erro)

    obj = veiculo.create(session, data)
    if novo_cliente_data is not None:
        seller = cliente.create(session, novo_cliente_data)
    assert seller is not None  # noqa: S101 -- invariante interna: erro is None garante seller definido
    _salvar_documentos_cliente(session, seller.id, cast(list[UploadFile], documentos))
    _salvar_documento_veiculo(session, obj.id, doc_veiculo)
    compra.create(
        session,
        compra.CompraCreate(
            cliente_id=seller.id,
            veiculo_id=obj.id,
            data_compra=datetime.now(UTC).date(),
            valor_compra=obj.preco,
            debitos=debitos,
        ),
    )
    caixa.criar_lancamento_veiculo(session, obj)
    veiculos = veiculo.list_all(session)
    return templates.TemplateResponse(
        request,
        "_veiculos_ok.html",
        {"user": user, "veiculos": veiculos, **_ctx_lista_veiculos(session, veiculos)},
    )
