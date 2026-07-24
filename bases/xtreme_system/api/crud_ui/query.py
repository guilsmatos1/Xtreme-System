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


def _query_sorted_list(
    query: Query[EntityT],
    sort: str,
    order: str,
    sort_fields: Mapping[str, Any] | None,
) -> list[EntityT]:
    spec = sort_fields.get(sort) if sort_fields is not None else None
    if spec is None:
        return list(query.all())
    order_expr = spec.desc() if order == "desc" else spec.asc()
    return list(query.order_by(order_expr).all())


def _accepts_column(func: Callable[..., Any]) -> bool:
    params = signature(func).parameters.values()
    return any(
        param.kind == Parameter.VAR_KEYWORD
        or (param.kind == Parameter.KEYWORD_ONLY and param.name == "column")
        or (param.kind == Parameter.POSITIONAL_OR_KEYWORD and param.name == "column")
        for param in params
    )


def query_list(
    session: Session,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    *,
    q: str,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
    search_column: str | None = None,
    sort: str = "",
    order: str = "asc",
    sql_sort_fields: Mapping[str, Any] | None = None,
    query_func: QueryFunc[EntityT] | None = None,
    search_query_func: SearchQueryFunc[EntityT] | None = None,
) -> list[EntityT]:
    if q and search_query_func is not None:
        if _accepts_column(search_query_func):
            query = search_query_func(session, q, column=search_column)
        else:
            query = search_query_func(session, q)
        return _query_sorted_list(query, sort, order, sql_sort_fields)
    if not q and query_func is not None:
        return _query_sorted_list(query_func(session), sort, order, sql_sort_fields)
    if q and search_func is not None:
        if _accepts_column(search_func):
            lista = list(search_func(session, q, column=search_column))  # type: ignore[call-arg]
        else:
            lista = list(search_func(session, q))
        return sorted_list(lista, sort, order, sql_sort_fields or {})
    if searchable and q:
        searchable_module = cast(
            SearchableCrudModule[EntityT, CreateSchemaT, UpdateSchemaT], module
        )
        return sorted_list(
            list(searchable_module.search(session, q)),
            sort,
            order,
            sql_sort_fields or {},
        )
    if list_func is not None:
        return sorted_list(list(list_func(session)), sort, order, sql_sort_fields or {})
    return sorted_list(
        list(module.list_all(session)), sort, order, sql_sort_fields or {}
    )
