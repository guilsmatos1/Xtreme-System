from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from xtreme_system.api.crud_types import (
    CrudModule,
    CtxList,
    ListingSpec,
    ListState,
)
from xtreme_system.api.crud_ui.config import ColumnSpec
from xtreme_system.api.crud_ui.query import query_list
from xtreme_system.api.crud_ui.responses import (
    conflict_form_response,
    delete_conflict_detail,
    list_response,
    ok_response,
    rollback_integrity_error_response,
    write_conflict_detail,
)
from xtreme_system.api.deps import SessionDep
from xtreme_system.usuario import core as usuario

LIST_LIMIT_MAX = 200


def _bounded_int(
    value: str | None, *, default: int, min_value: int, max_value: int
) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return min(max(parsed, min_value), max_value)


def current_list_state(request: Request) -> ListState:
    current_url = request.headers.get("HX-Current-URL")
    if current_url:
        query_params = {
            key: values[-1]
            for key, values in parse_qs(
                urlsplit(current_url).query, keep_blank_values=True
            ).items()
        }
    else:
        query_params = dict(request.query_params)

    return ListState(
        q=query_params.get("q", ""),
        sort=query_params.get("sort", ""),
        order=query_params.get("order", "asc"),
        search_column=query_params.get("search_column", ""),
        limit=_bounded_int(
            query_params.get("limit"),
            default=50,
            min_value=1,
            max_value=LIST_LIMIT_MAX,
        ),
        offset=_bounded_int(
            query_params.get("offset"),
            default=0,
            min_value=0,
            max_value=10**9,
        ),
    )


def write_conflict_response(
    session: SessionDep,
    request: Request,
    form: Any,
    *,
    item: object,
    user: usuario.Usuario,
    erro: str,
    dados: dict[str, Any] | None = None,
) -> HTMLResponse:
    return rollback_integrity_error_response(
        session,
        lambda: conflict_form_response(
            form.templates,
            request,
            form.form_template,
            ctx_form=form.ctx_form(session),
            item_key=form.item_key,
            item=item,
            user=user,
            erro=erro,
            dados=dados,
        ),
    )


def write_ok_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    module: CrudModule[Any, Any, Any],
    ok_partial_template: str,
    *,
    user: usuario.Usuario,
    list_key: str,
    ctx_list: CtxList[Any],
    listing: ListingSpec[Any],
) -> HTMLResponse:
    state = current_list_state(request)
    lista = query_list(session, module, listing=listing, state=state)
    return ok_response(
        templates,
        request,
        ok_partial_template,
        user=user,
        list_key=list_key,
        lista=lista,
        ctx_list=ctx_list(session, lista),
    )


def delete_list_response(
    session: SessionDep,
    templates: Jinja2Templates,
    request: Request,
    module: CrudModule[Any, Any, Any],
    list_partial_template: str,
    *,
    user: usuario.Usuario,
    list_key: str,
    ctx_list: CtxList[Any],
    listing: ListingSpec[Any],
    erro: str | None = None,
    status_code: int = 200,
    filter_col: str = "",
    filter_val: str = "",
) -> HTMLResponse:
    state = current_list_state(request)
    lista = query_list(session, module, listing=listing, state=state)
    return list_response(
        templates,
        request,
        list_partial_template,
        user=user,
        list_key=list_key,
        lista=lista,
        ctx_list=ctx_list(session, lista),
        sort=state.sort,
        order=state.order,
        q=state.q if listing.searchable else None,
        search_column=state.search_column,
        limit=state.limit if state.limit is not None else 50,
        offset=state.offset,
        erro=erro,
        status_code=status_code,
        filter_col=filter_col,
        filter_val=filter_val,
    )


__all__ = [
    "LIST_LIMIT_MAX",
    "ColumnSpec",
    "current_list_state",
    "delete_conflict_detail",
    "delete_list_response",
    "write_conflict_detail",
    "write_conflict_response",
    "write_ok_response",
]
