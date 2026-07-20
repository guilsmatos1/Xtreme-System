import csv
import io
from typing import Any

from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from xtreme_system.api.crud_types import EntityT


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
    status_code: int = 200,
) -> HTMLResponse:
    context = {**ctx_form, item_key: item}
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
    )


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
    erro: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    context = {
        "user": user,
        list_key: lista,
        "sort": sort,
        "order": order,
        "filter_col": filter_col,
        "filter_val": filter_val,
        **ctx_list,
    }
    if q is not None:
        context["q"] = q
    if erro is not None:
        context["erro"] = erro
    return templates.TemplateResponse(
        request,
        template,
        context,
        status_code=status_code,
    )


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
    return templates.TemplateResponse(
        request,
        template,
        {"user": user, list_key: lista, **ctx_list},
    )


def write_conflict_detail(label: str) -> str:
    return f"{label} já existe"


def delete_conflict_detail(label: str) -> str:
    return f"{label} possui registros vinculados"
