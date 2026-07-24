from collections.abc import Callable, Mapping
from inspect import Parameter, signature
from typing import Any, cast

from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    CreateSchemaT,
    CrudModule,
    EntityT,
    ListFunc,
    SearchableCrudModule,
    SearchFunc,
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


def _accepts_search_column(search_func: SearchFunc[EntityT]) -> bool:
    parameters = signature(search_func).parameters.values()
    return any(
        parameter.kind is Parameter.VAR_KEYWORD
        or (
            parameter.name == "column"
            and parameter.kind is not Parameter.POSITIONAL_ONLY
        )
        for parameter in parameters
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
    limit: int | None = None,
    offset: int = 0,
) -> list[EntityT]:
    def _page(lista: list[EntityT]) -> list[EntityT]:
        if limit is None:
            return lista[offset:]
        return lista[offset : offset + limit]

    if q and search_func is not None:
        if _accepts_search_column(search_func):
            lista = list(search_func(session, q, column=search_column))  # type: ignore[call-arg]
        else:
            lista = list(search_func(session, q))
        return _page(lista)
    if searchable and q:
        searchable_module = cast(
            SearchableCrudModule[EntityT, CreateSchemaT, UpdateSchemaT], module
        )
        return _page(list(searchable_module.search(session, q)))
    if list_func is not None:
        if _accepts_list_pagination(list_func):
            return list(list_func(session, limit=limit, offset=offset))
        return _page(list(list_func(session)))
    list_all = module.list_all
    if _accepts_list_pagination(list_all):
        return list(list_all(session, limit=limit, offset=offset))
    return _page(list(list_all(session)))
