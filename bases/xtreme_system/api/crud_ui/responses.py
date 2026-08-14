import csv
import io
import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

import structlog
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import EntityT
from xtreme_system.cliente.core import (
    CampoClienteObrigatorioError,
    CepClienteInvalidoError,
    DocumentoClienteInvalidoError,
    EmailClienteInvalidoError,
    EstadoClienteInvalidoError,
    TipoClienteInvalidoError,
)
from xtreme_system.venda.core import (
    ERRO_PAGAMENTO_PENDENTE_DATAS_OBRIGATORIAS,
    ERRO_PAGAMENTO_PENDENTE_VALOR_OBRIGATORIO,
    ERRO_PAGAMENTO_SEM_PENDENCIA_COM_DATAS,
    ERRO_PAGAMENTO_SEM_PENDENCIA_COM_VALOR,
    ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA,
)

logger = structlog.get_logger(__name__)

_HTMX_SUCCESS_EVENTS = {
    "htmx:toast": {"message": "Alterações salvas com sucesso.", "variant": "success"},
    "htmx:close-modal": {},
}

_LABELS = {
    "cliente_id": "Cliente",
    "documento": "Documento",
    "email": "E-mail",
    "telefone": "Telefone",
    "telefone2": "Telefone 2",
    "endereco": "Endereço",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "estado": "Estado",
    "cep": "CEP",
    "profissao": "Profissão",
    "veiculo_id": "Veículo",
    "vendedor_id": "Vendedor",
    "data_venda": "Data da venda",
    "valor_venda": "Valor da venda",
    "valor_entrada": "Entrada",
    "debitos": "Débitos do veículo",
    "km": "Quilometragem",
    "forma_pagamento": "Forma de pagamento",
    "parcelas": "Parcelas",
    "status": "Estado",
    "observacoes": "Observações",
    "veiculo_troca_id": "Veículo da troca",
    "valor_diferenca": "Valor da diferença",
    "pagamento_pendente": "Pagamento pendente",
    "valor_pendente": "Valor pendente",
    "datas_pagamento": "Datas de pagamento",
    "veic_troca_tipo": "Tipo",
    "veic_troca_placa": "Placa",
    "veic_troca_modelo": "Modelo",
    "veic_troca_marca": "Marca",
    "veic_troca_cor": "Cor",
    "veic_troca_ano": "Ano",
    "veic_troca_km": "Quilometragem",
    "veic_troca_chassi": "Chassi",
    "veic_troca_renavam": "RENAVAM",
    "veic_troca_proprietario_atual": "Proprietário Atual",
    "veic_troca_preco": "Valor de avaliação",
    "veic_troca_investidor_id": "Investidor",
    "data_compra": "Data da compra",
    "valor_compra": "Valor da compra",
    "tipo": "Tipo",
    "tipo_entrada": "Tipo de entrada",
    "modelo": "Modelo",
    "marca": "Marca",
    "cor": "Cor",
    "ano": "Ano",
    "placa": "Placa",
    "chassi": "Chassi",
    "renavam": "RENAVAM",
    "preco": "Preço anunciado",
    "procuracao": "Procurador",
    "numero_motor": "Número do Motor",
    "proprietario_atual": "Proprietário Atual",
    "proprietario_anterior": "Proprietário Anterior",
    "proprietario_documento": "Documento do Proprietário",
    "combustivel": "Combustível",
    "tipo_documento": "Tipo (Documento)",
    "categoria": "Categoria",
    "especie": "Espécie",
    "procedencia": "Procedência",
    "municipio": "Município",
    "potencia": "Potência",
    "cilindrada": "Cilindrada",
    "revisao": "Revisão",
    "investidor_id": "Investidor",
    "nome": "Nome",
    "paginas": "Páginas com acesso",
    "restricoes": "Restrições",
    "valor": "Valor",
    "descricao": "Descrição",
}

_MSGS = {
    "missing": "preencha este campo",
    "none_required": "preencha este campo",
    "decimal_parsing": "informe um valor numérico válido",
    "decimal_type": "informe um valor numérico válido",
    "float_parsing": "informe um número válido",
    "float_type": "informe um número válido",
    "int_parsing": "informe um número inteiro válido",
    "int_type": "informe um número inteiro válido",
    "greater_than": "deve ser maior que zero",
    "greater_than_equal": "deve ser maior ou igual a zero",
    "less_than": "deve ser menor que o limite permitido",
    "less_than_equal": "deve ser menor ou igual ao limite permitido",
    "string_type": "informe um texto válido",
    "bool_parsing": "selecione uma opção válida",
    "bool_type": "selecione uma opção válida",
    "date_parsing": "informe uma data válida",
    "date_from_datetime_parsing": "informe uma data válida",
    "enum": "selecione uma opção válida",
    "value_error": "informe um valor válido",
}

_SKIP_LOC = {"body", "__root__"}

_VALUE_ERROR_REWRITE: dict[str, tuple[str | None, str]] = {
    ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA: (
        "valor_entrada",
        "não pode ser maior que o valor da venda",
    ),
    ERRO_PAGAMENTO_PENDENTE_VALOR_OBRIGATORIO: (
        "valor_pendente",
        "informe um valor pendente maior que zero",
    ),
    ERRO_PAGAMENTO_PENDENTE_DATAS_OBRIGATORIAS: (
        "datas_pagamento",
        "informe as datas de pagamento",
    ),
    ERRO_PAGAMENTO_SEM_PENDENCIA_COM_VALOR: (
        "pagamento_pendente",
        "marque pagamento pendente para informar um valor pendente",
    ),
    ERRO_PAGAMENTO_SEM_PENDENCIA_COM_DATAS: (
        "pagamento_pendente",
        "marque pagamento pendente para informar as datas",
    ),
    str(DocumentoClienteInvalidoError()): (
        "documento",
        "CPF deve ter 11 dígitos (pessoa física) ou CNPJ 14 dígitos (pessoa jurídica)",
    ),
    str(EmailClienteInvalidoError()): (
        "email",
        "informe um e-mail válido",
    ),
    str(CepClienteInvalidoError()): (
        "cep",
        "informe um CEP com 8 dígitos",
    ),
    str(EstadoClienteInvalidoError()): (
        "estado",
        "informe a UF com 2 letras",
    ),
    str(CampoClienteObrigatorioError()): (None, "preencha este campo"),
    str(TipoClienteInvalidoError()): ("tipo", "selecione um tipo válido"),
}


def _loc_field(error: Mapping[str, Any]) -> str | None:
    for part in reversed(error.get("loc") or ()):
        if isinstance(part, str) and part not in _SKIP_LOC:
            return part
    return None


def _label_for(field: str | None) -> str | None:
    if field is None:
        return None
    if field in _LABELS:
        return _LABELS[field]
    pretty = field.replace("_", " ").strip()
    if not pretty:
        return None
    return pretty[0].upper() + pretty[1:]


def _value_error_text(error: Mapping[str, Any]) -> str | None:
    ctx = error.get("ctx") or {}
    raw = ctx.get("error")
    if raw is not None:
        text = str(raw).strip().rstrip(".")
        if text:
            return text
    msg = str(error.get("msg") or "")
    prefix = "Value error, "
    if msg.startswith(prefix):
        return msg[len(prefix) :].strip().rstrip(".")
    return None


def _resolved_error(error: Mapping[str, Any]) -> tuple[str | None, str]:
    field = _loc_field(error)
    err_type = error.get("type")
    if err_type == "value_error":
        raw = _value_error_text(error)
        if raw in _VALUE_ERROR_REWRITE:
            mapped_field, friendly = _VALUE_ERROR_REWRITE[raw]
            return field or mapped_field, friendly
        if raw:
            return field, raw
    message_key = err_type if isinstance(err_type, str) else ""
    return field, _MSGS.get(message_key, "informe um valor válido")


def _format_line(field: str | None, message: str) -> str:
    message = message.rstrip(".")
    label = _label_for(field)
    if label:
        text = f"{label}: {message}"
    elif message:
        text = message[:1].upper() + message[1:]
    else:
        text = "Informe um valor válido"
    return text if text.endswith(".") else f"{text}."


def validation_error_field(exc: ValidationError) -> str | None:
    """Return the first schema field implicated by a Pydantic error."""
    for error in exc.errors():
        field, _message = _resolved_error(error)
        if field:
            return field
    return None


def validation_error_detail(
    exc: ValidationError, *, campos_ocultados: set[str] | None = None
) -> str:
    """Format Pydantic errors as localized, user-facing messages.

    `campos_ocultados` lists schema fields removed from the form by
    `perfil.campos_form_visiveis` for this user — a "missing" error on one of
    these is a permission gap, not something the user can fix by retyping.
    """
    messages = []
    for error in exc.errors():
        field, message = _resolved_error(error)
        campo_oculto = (
            campos_ocultados is not None
            and field is not None
            and field in campos_ocultados
        )
        if error.get("type") == "missing" and campo_oculto:
            label = _label_for(field) or "Campo"
            messages.append(
                f"{label}: campo obrigatório, mas seu perfil não tem permissão "
                "para preenchê-lo. Peça a um administrador para liberar o acesso."
            )
            continue
        messages.append(_format_line(field, message))
    return "\n".join(messages)


def success_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    context: dict[str, Any],
) -> HTMLResponse:
    """Render a successful HTMX response with shared toast and modal behavior."""
    response = templates.TemplateResponse(request, template, context)
    if request.headers.get("HX-Request"):
        response.headers["HX-Trigger"] = json.dumps(_HTMX_SUCCESS_EVENTS)
    return response


def csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def form_response(
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    *,
    ctx_form: dict[str, Any],
    item_key: str,
    item: EntityT | None,
    user: object = None,
    erro: str | None = None,
    dados: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    context = {**ctx_form, item_key: item}
    context["dados"] = dados or {}
    if user is not None:
        context["user"] = user
    if erro is not None:
        context["erro"] = erro
    return templates.TemplateResponse(
        request,
        form_template,
        context,
        status_code=status_code,
    )


def error_response(
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    *,
    ctx_form: dict[str, Any],
    item_key: str,
    item: EntityT | None,
    erro: str,
    status_code: int,
    user: object = None,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return form_response(
        templates,
        request,
        form_template,
        ctx_form=ctx_form,
        item_key=item_key,
        item=item,
        user=user,
        erro=erro,
        dados=dados,
        status_code=status_code,
    )


def conflict_form_response(
    templates: Jinja2Templates,
    request: Request,
    form_template: str,
    *,
    ctx_form: dict[str, Any],
    item_key: str,
    item: EntityT | None,
    erro: str,
    user: object = None,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return error_response(
        templates,
        request,
        form_template,
        ctx_form=ctx_form,
        item_key=item_key,
        item=item,
        erro=erro,
        status_code=409,
        user=user,
        dados=dados,
    )


def rollback_integrity_error_response(
    session: Session, build_response: Callable[[], HTMLResponse]
) -> HTMLResponse:
    logger.warning("write_rolled_back", reason="integrity_error")
    session.rollback()
    return build_response()


def list_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    *,
    user: object,
    list_key: str,
    lista: list[EntityT],
    ctx_list: dict[str, Any],
    sort: str = "",
    order: str = "asc",
    q: str | None = None,
    filter_col: str = "",
    filter_val: str = "",
    search_column: str = "",
    limit: int = 50,
    offset: int = 0,
    erro: str | None = None,
    status_code: int = 200,
    success: bool = False,
) -> HTMLResponse:
    qs_params = {
        chave: valor
        for chave, valor in {
            "q": q,
            "sort": sort or None,
            "order": order if sort else None,
            "search_column": search_column or None,
            "filter_col": filter_col or None,
            "filter_val": filter_val or None,
        }.items()
        if valor not in (None, "")
    }
    page_count = len(lista)
    context = {
        "user": user,
        list_key: lista,
        "sort": sort,
        "order": order,
        "filter_col": filter_col,
        "filter_val": filter_val,
        "search_column": search_column,
        "limit": limit,
        "offset": offset,
        "page_count": page_count,
        "page_start": offset + 1 if page_count else 0,
        "page_end": offset + page_count,
        "tem_anterior": offset > 0,
        "tem_proximo": page_count == limit,
        "offset_anterior": offset - limit if offset - limit > 0 else 0,
        "offset_proximo": offset + limit,
        "qs_base": urlencode(qs_params),
        "oob": bool(request.headers.get("HX-Request")),
        **ctx_list,
    }
    if q is not None:
        context["q"] = q
    if erro is not None:
        context["erro"] = erro
    response = templates.TemplateResponse(
        request,
        template,
        context,
        status_code=status_code,
    )
    if success and request.headers.get("HX-Request"):
        response.headers["HX-Trigger"] = json.dumps(_HTMX_SUCCESS_EVENTS)
    return response


def ok_response(
    templates: Jinja2Templates,
    request: Request,
    template: str,
    *,
    user: object,
    list_key: str,
    lista: list[EntityT],
    ctx_list: dict[str, Any],
) -> HTMLResponse:
    return success_response(
        templates,
        request,
        template,
        {"user": user, list_key: lista, **ctx_list},
    )


def write_conflict_detail(label: str) -> str:
    return f"{label} já existe"


def delete_conflict_detail(label: str, detail: str | None = None) -> str:
    return detail or f"{label} possui registros vinculados"
