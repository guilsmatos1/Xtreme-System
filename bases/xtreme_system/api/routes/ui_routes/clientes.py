"""HTMX routes for clientes."""

from typing import Annotated, Any

import structlog
from fastapi import Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from markupsafe import Markup
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import ListingSpec, SortField
from xtreme_system.api.crud_ui.routes import (
    ColumnSpec,
    CrudUIBehaviorConfig,
    CrudUIExportConfig,
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    register_crud_ui_routes,
)
from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    UIUser,
    _found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_cliente_dir,
)
from xtreme_system.api.routes.ui_routes.uploads import (
    excluir_anexo_entidade,
    pending_upload_paths,
    salvar_anexos_entidade,
)
from xtreme_system.api.setup import app
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.usuario import core as usuario
from xtreme_system.venda import core as venda

logger = structlog.get_logger(__name__)


def _table_cell(
    column: str, value: Any, *, class_name: str = "", empty: str = "-"
) -> Markup:
    class_attr = Markup(' class="{}"').format(class_name) if class_name else ""
    return Markup('<td{} data-col="{}">{}</td>').format(
        class_attr,
        column,
        empty if value in (None, "") else value,
    )


def _tipo_cell(c: cliente.Cliente) -> Markup:
    tipo = c.tipo.value
    badge_class = {
        "pessoa_fisica": "badge--info",
        "pessoa_juridica": "badge--success",
    }.get(tipo, "")
    badge = Markup('<span class="badge badge--plain {}">{}</span>').format(
        badge_class,
        tipo.replace("_", " ").title(),
    )
    return _table_cell("tipo", badge)


_EditarClienteDep = Annotated[
    usuario.Usuario, Depends(require_operacao("clientes", "editar"))
]
_ExcluirDocumentoDep = Annotated[
    usuario.Usuario, Depends(require_operacao("clientes", "excluir_documento"))
]

# ---- Clientes (UI) ----


def _ctx_form_cliente(route_prefix: str) -> Any:
    def _ctx(_session: Session) -> dict[str, Any]:
        return {"tipos": list(cliente.TipoCliente), "route_prefix": route_prefix}

    return _ctx


def _ctx_lista_cliente(
    *,
    page_title: str,
    page_subtitle: str,
    route_prefix: str,
    empty_title: str,
    empty_text: str,
    vehicles_label: str,
) -> Any:
    def _ctx(_session: Session, _lista: list[Any]) -> dict[str, Any]:
        return {
            "page_title": page_title,
            "page_subtitle": page_subtitle,
            "route_prefix": route_prefix,
            "empty_title": empty_title,
            "empty_text": empty_text,
            "vehicles_label": vehicles_label,
        }

    return _ctx


def _veiculos_cliente_modal(
    request: Request, session: Session, cliente_id: int
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    return templates.TemplateResponse(
        request,
        "_modal_veiculos_cliente.html",
        {
            "cliente": item,
            "modal_title": "Veículos",
            "grupos": [
                {
                    "titulo": "Veículos comprados",
                    "registros": venda.list_by_cliente(session, cliente_id),
                    "kind": "comprador",
                    "empty_text": "Este cliente ainda não comprou nenhum veículo.",
                },
                {
                    "titulo": "Veículos vendidos",
                    "registros": compra.list_by_cliente(session, cliente_id),
                    "kind": "vendedor",
                    "empty_text": (
                        "Este cliente ainda não vendeu nenhum veículo para a loja."
                    ),
                },
            ],
        },
    )


def _documentos_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    cliente_id: int,
    *,
    action_oob: bool = False,
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    session.refresh(item)
    return templates.TemplateResponse(
        request,
        "_modal_documentos_cliente.html",
        {
            "cliente": item,
            "user": user,
            "action_oob": action_oob,
            "pending_upload_paths": pending_upload_paths(session),
        },
    )


def _documentos_erro_modal(
    request: Request,
    session: Session,
    user: usuario.Usuario,
    cliente_id: int,
    erro: str,
) -> HTMLResponse:
    item = _found(cliente.get(session, cliente_id), "Cliente")
    session.refresh(item)
    return templates.TemplateResponse(
        request,
        "_modal_documentos_cliente.html",
        {
            "cliente": item,
            "user": user,
            "erro": erro,
            "action_oob": False,
            "pending_upload_paths": pending_upload_paths(session),
        },
        status_code=400,
    )


@app.get("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos(
    request: Request,
    session: SessionDep,
    user: _EditarClienteDep,
    cliente_id: int,
) -> HTMLResponse:
    return _documentos_modal(request, session, user, cliente_id)


@app.post("/ui/clientes/{cliente_id}/documentos")
def ui_cliente_documentos_upload(
    request: Request,
    session: SessionDep,
    user: _EditarClienteDep,
    cliente_id: int,
    documentos: Annotated[list[UploadFile], File(default_factory=list)],
) -> HTMLResponse:
    _found(cliente.get(session, cliente_id), "Cliente")
    erro = salvar_anexos_entidade(
        session,
        upload_dir=_uploads_cliente_dir(cliente_id),
        url_prefix=f"/static/uploads/clientes/{cliente_id}/documentos",
        create_fn=imagem_documento_cliente.create,
        schema=imagem_documento_cliente.ImagemDocumentoClienteCreate,
        fk_field="cliente_id",
        fk_id=cliente_id,
        arquivos=documentos,
        actor_id=user.id,
    )
    if erro:
        return _documentos_erro_modal(request, session, user, cliente_id, erro)
    return _documentos_modal(request, session, user, cliente_id, action_oob=True)


@app.post("/ui/clientes/{cliente_id}/documentos/{doc_id}/excluir")
def ui_cliente_documentos_excluir(
    request: Request,
    session: SessionDep,
    user: _ExcluirDocumentoDep,
    cliente_id: int,
    doc_id: int,
) -> HTMLResponse:
    doc = _found(imagem_documento_cliente.get(session, doc_id), "Documento")
    excluir_anexo_entidade(
        session,
        anexo=doc,
        parent_field="cliente_id",
        parent_id=cliente_id,
        delete_fn=imagem_documento_cliente.delete,
        actor_id=user.id,
        not_found_detail="Documento não encontrado",
    )
    return _documentos_modal(request, session, user, cliente_id, action_oob=True)


@app.get("/ui/clientes")
def ui_clientes_redirect(_: UIUser) -> RedirectResponse:
    return RedirectResponse("/ui/clientes/todos", status_code=303)


@app.get("/ui/clientes/todos/{cliente_id}/veiculos")
def ui_cliente_veiculos(
    request: Request,
    session: SessionDep,
    _: UIAdmin,
    cliente_id: int,
) -> HTMLResponse:
    return _veiculos_cliente_modal(request, session, cliente_id)


def _register_clientes_page(
    *,
    prefix: str,
    page_title: str,
    page_subtitle: str,
    empty_title: str,
    empty_text: str,
    vehicles_label: str,
    list_func: Any,
    search_func: Any,
    query_func: Any,
    search_query_func: Any,
    csv_filename: str,
) -> None:
    register_crud_ui_routes(
        app,
        templates,
        cliente,
        prefix,
        resource=CrudUIResourceConfig(
            label="Cliente",
            create_schema=cliente.ClienteCreate,
            update_schema=cliente.ClienteUpdate,
            list_key="clientes",
            item_key="cliente",
        ),
        templates_config=CrudUITemplateConfig(
            list_template="clientes.html",
            list_partial_template="_linhas_clientes.html",
            ok_partial_template="_clientes_ok.html",
            form_template="_form_cliente.html",
        ),
        behavior=CrudUIBehaviorConfig(
            ctx_form=_ctx_form_cliente(prefix),
            ctx_list=_ctx_lista_cliente(
                page_title=page_title,
                page_subtitle=page_subtitle,
                route_prefix=prefix,
                empty_title=empty_title,
                empty_text=empty_text,
                vehicles_label=vehicles_label,
            ),
        ),
        listing=ListingSpec(
            sort_fields={
                "nome": SortField("nome", cliente.Cliente.nome),
                "documento": SortField("documento", cliente.Cliente.documento),
                "telefone": SortField("telefone", cliente.Cliente.telefone),
                "tipo": SortField("tipo", cliente.Cliente.tipo),
                "cidade": SortField("cidade", cliente.Cliente.cidade),
                "estado": SortField("estado", cliente.Cliente.estado),
            },
            searchable=True,
            list_func=list_func,
            search_func=search_func,
            query_func=query_func,
            search_query_func=search_query_func,
        ),
        export=CrudUIExportConfig[cliente.Cliente](
            csv_filename=csv_filename,
            pagina="clientes",
            columns=[
                ColumnSpec("id", "ID", table=False, export=lambda c: c.id),
                ColumnSpec(
                    "nome",
                    "Nome",
                    field="nome",
                    html=lambda c: _table_cell(
                        "nome", c.nome, class_name="cell-strong"
                    ),
                    export=lambda c: c.nome,
                ),
                ColumnSpec(
                    "documento",
                    "Documento",
                    field="documento",
                    html=lambda c: _table_cell(
                        "documento",
                        cliente.formatar_documento(c.documento),
                        class_name="cell-mono",
                    ),
                    export=lambda c: c.documento,
                ),
                ColumnSpec(
                    "tipo",
                    "Tipo",
                    field="tipo",
                    html=_tipo_cell,
                    export=lambda c: c.tipo.value,
                ),
                ColumnSpec(
                    "telefone",
                    "Telefone",
                    field="telefone",
                    html=lambda c: _table_cell(
                        "telefone", cliente.formatar_telefone(c.telefone)
                    ),
                    export=lambda c: c.telefone or "",
                ),
                ColumnSpec(
                    "cidade",
                    "Cidade",
                    field="cidade",
                    html=lambda c: _table_cell("cidade", c.cidade),
                    export=lambda c: c.cidade or "",
                ),
                ColumnSpec(
                    "estado",
                    "UF",
                    field="estado",
                    html=lambda c: _table_cell("estado", c.estado),
                    export=lambda c: c.estado or "",
                ),
            ],
        ),
        routes=CrudUIRouteConfig(
            cadastrar_dep=require_operacao("clientes", "cadastrar"),
            editar_dep=require_operacao("clientes", "editar"),
            excluir_dep=require_operacao("clientes", "excluir"),
        ),
    )


_register_clientes_page(
    prefix="/ui/clientes/todos",
    page_title="Clientes",
    page_subtitle="Todos os clientes cadastrados",
    empty_title="Nenhum cliente encontrado",
    empty_text="Crie um novo cliente para começar.",
    vehicles_label="Veículos",
    list_func=cliente.list_all,
    search_func=cliente.search,
    query_func=cliente.query,
    search_query_func=cliente.search_query,
    csv_filename="clientes.csv",
)
