from collections.abc import Callable, Mapping
from inspect import Parameter, signature
from typing import Any, cast

from sqlalchemy.orm import Query, Session

from xtreme_system.api.crud_types import (
    CreateSchemaT,
    CrudModule,
    EntityT,
    ListFunc,
    QueryFunc,
    SearchableCrudModule,
    SearchFunc,
    SearchQueryFunc,
    SortSpec,
    UpdateSchemaT,
)


def sort_key(value: Any) -> Any:
    if value is None:
        return ""
    value = getattr(value, "value", value)
    if hasattr(value, "nome"):
        value = value.nome
    return value.lower() if isinstance(value, str) else value


def sort_key_fn(spec: SortSpec[EntityT]) -> Callable[[EntityT], Any]:
    if callable(spec):
        return spec
    return lambda obj: sort_key(getattr(obj, spec))


def _filter_repr(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    value = getattr(value, "value", value)
    if hasattr(value, "nome"):
        value = value.nome
    return str(value).lower()


def filter_list(
    lista: list[EntityT],
    filter_col: str,
    filter_val: str,
    sort_fields: Mapping[str, SortSpec[EntityT]],
) -> list[EntityT]:
    spec = sort_fields.get(filter_col)
    needle = filter_val.strip().lower()
    if spec is None or not needle:
        return lista
    getter = sort_key_fn(spec)
    return [obj for obj in lista if needle in _filter_repr(getter(obj))]


def sorted_list(
    lista: list[EntityT],
    sort: str,
    order: str,
    sort_fields: Mapping[str, SortSpec[EntityT]],
) -> list[EntityT]:
    spec = sort_fields.get(sort)
    if spec is None:
        return lista
    return sorted(lista, key=sort_key_fn(spec), reverse=order == "desc")


def _accepts_list_pagination(list_func: ListFunc[EntityT]) -> bool:
    parameters = signature(list_func).parameters.values()
    return any(
        parameter.kind is Parameter.VAR_KEYWORD
        or (
            parameter.name in {"limit", "offset"}
            and parameter.kind is not Parameter.POSITIONAL_ONLY
        )
        for parameter in parameters
    )


def _query_sorted_list(
    query: Query[EntityT],
    sort: str,
    order: str,
    sort_fields: Mapping[str, Any] | None,
    limit: int | None,
    offset: int,
) -> list[EntityT]:
    spec = sort_fields.get(sort) if sort_fields is not None else None
    entity = None
    if query.column_descriptions:
        entity = query.column_descriptions[0].get("entity")
    id_field = getattr(entity, "id", None)
    if spec is not None:
        order_expr = spec.desc() if order == "desc" else spec.asc()
        query = query.order_by(order_expr)
        if id_field is not None and id_field is not spec:
            id_order_expr = id_field.desc() if order == "desc" else id_field.asc()
            query = query.order_by(id_order_expr)
    elif id_field is not None:
        query = query.order_by(id_field.asc())
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(query.all())


def _accepts_column(func: Callable[..., Any]) -> bool:
    params = signature(func).parameters.values()
    return any(
        param.kind == Parameter.VAR_KEYWORD
        or (param.kind == Parameter.KEYWORD_ONLY and param.name == "column")
        or (param.kind == Parameter.POSITIONAL_OR_KEYWORD and param.name == "column")
        for param in params
    )


def _page_list(lista: list[EntityT], limit: int | None, offset: int) -> list[EntityT]:
    if limit is None:
        return lista[offset:]
    return lista[offset : offset + limit]


def _search_list(
    search_func: SearchFunc[EntityT],
    session: Session,
    q: str,
    search_column: str | None,
) -> list[EntityT]:
    if _accepts_column(search_func):
        return list(search_func(session, q, column=search_column))  # type: ignore[call-arg]
    return list(search_func(session, q))


def _paginated_list(
    list_func: ListFunc[EntityT],
    session: Session,
    limit: int | None,
    offset: int,
) -> list[EntityT] | None:
    if _accepts_list_pagination(list_func):
        return list(list_func(session, limit=limit, offset=offset))
    return None


def query_list(
    session: Session,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    *,
    q: str,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    search_column: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort: str = "",
    order: str = "asc",
    sort_fields: Mapping[str, SortSpec[EntityT]] | None = None,
    sql_sort_fields: Mapping[str, Any] | None = None,
    query_func: QueryFunc[EntityT] | None = None,
    search_query_func: SearchQueryFunc[EntityT] | None = None,
) -> list[EntityT]:
    python_sort_fields = sort_fields or {}
    if q and search_query_func is not None:
        if _accepts_column(search_query_func):
            query = search_query_func(session, q, column=search_column)
        else:
            query = search_query_func(session, q)
        return _query_sorted_list(query, sort, order, sql_sort_fields, limit, offset)
    if not q and query_func is not None:
        return _query_sorted_list(
            query_func(session), sort, order, sql_sort_fields, limit, offset
        )
    if q and search_func is not None:
        lista = _search_list(search_func, session, q, search_column)
        result = _page_list(
            sorted_list(lista, sort, order, python_sort_fields), limit, offset
        )
    elif searchable and q:
        searchable_module = cast(
            SearchableCrudModule[EntityT, CreateSchemaT, UpdateSchemaT], module
        )
        result = _page_list(
            sorted_list(
                list(searchable_module.search(session, q)),
                sort,
                order,
                python_sort_fields,
            ),
            limit,
            offset,
        )
    else:
        callable_list = list_func or module.list_all
        paginated_result = _paginated_list(callable_list, session, limit, offset)
        if paginated_result is None:
            result = _page_list(
                sorted_list(
                    list(callable_list(session)), sort, order, python_sort_fields
                ),
                limit,
                offset,
            )
        else:
            result = paginated_result
    return result
