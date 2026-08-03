import csv
import io
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import EntityT

_HTMX_SUCCESS_EVENTS = {
    "htmx:toast": {"message": "Alterações salvas com sucesso."},
    "htmx:close-modal": {},
}


def validation_error_detail(exc: ValidationError) -> str:
    """Format Pydantic errors without discarding the field that failed."""
    return "; ".join(
        f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()
    )


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
