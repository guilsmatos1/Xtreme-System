from collections.abc import Callable, Mapping
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


def query_list(
    session: Session,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    *,
    q: str,
    searchable: bool,
    list_func: ListFunc[EntityT] | None,
    search_func: SearchFunc[EntityT] | None,
) -> list[EntityT]:
    if q and search_func is not None:
        return list(search_func(session, q))
    if searchable and q:
        searchable_module = cast(
            SearchableCrudModule[EntityT, CreateSchemaT, UpdateSchemaT], module
        )
        return list(searchable_module.search(session, q))
    if list_func is not None:
        return list(list_func(session))
    return list(module.list_all(session))
