from collections.abc import Callable, Mapping
from typing import Any, cast

from sqlalchemy.orm import Query, Session

from xtreme_system.api.crud_types import (
    ColumnSearchFunc,
    CreateSchemaT,
    CrudModule,
    EntityT,
    ListFunc,
    ListingSpec,
    ListState,
    SearchableCrudModule,
    SortField,
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
    sort_fields: Mapping[str, SortField[EntityT]],
) -> list[EntityT]:
    field = sort_fields.get(filter_col)
    needle = filter_val.strip().lower()
    if field is None or not needle:
        return lista
    getter = sort_key_fn(field.python)
    return [obj for obj in lista if needle in _filter_repr(getter(obj))]


def sorted_list(
    lista: list[EntityT],
    sort: str,
    order: str,
    sort_fields: Mapping[str, SortField[EntityT]],
) -> list[EntityT]:
    field = sort_fields.get(sort)
    if field is None:
        return lista
    return sorted(lista, key=sort_key_fn(field.python), reverse=order == "desc")


def _query_sorted_list(
    query: Query[EntityT],
    sort: str,
    order: str,
    sort_fields: Mapping[str, SortField[EntityT]],
    limit: int | None,
    offset: int,
) -> list[EntityT]:
    field = sort_fields.get(sort)
    spec = field.sql if field is not None else None
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


def _page_list(lista: list[EntityT], limit: int | None, offset: int) -> list[EntityT]:
    if limit is None:
        return lista[offset:]
    return lista[offset : offset + limit]


def _search_list(
    search_func: ColumnSearchFunc[EntityT],
    session: Session,
    q: str,
    search_column: str | None,
) -> list[EntityT]:
    return list(search_func(session, q, column=search_column))


def _paginated_list(
    list_func: ListFunc[EntityT],
    session: Session,
    limit: int | None,
    offset: int,
) -> list[EntityT]:
    return list(list_func(session, limit=limit, offset=offset))


def query_list(
    session: Session,
    module: CrudModule[EntityT, CreateSchemaT, UpdateSchemaT],
    *,
    listing: ListingSpec[EntityT],
    state: ListState,
) -> list[EntityT]:
    sort = state.sort or listing.default_sort
    order = state.order if state.sort else listing.default_order
    limit = state.limit if listing.paginated else None
    offset = state.offset if listing.paginated else 0
    if state.q and listing.search_query_func is not None:
        query = listing.search_query_func(
            session, state.q, column=state.search_column or None
        )
        return _query_sorted_list(
            query,
            sort,
            order,
            listing.sort_fields,
            limit,
            offset,
        )
    if not state.q and listing.query_func is not None:
        return _query_sorted_list(
            listing.query_func(session),
            sort,
            order,
            listing.sort_fields,
            limit,
            offset,
        )
    if state.q and listing.search_func is not None:
        lista = _search_list(
            listing.search_func, session, state.q, state.search_column or None
        )
        result = _page_list(
            sorted_list(lista, sort, order, listing.sort_fields),
            limit,
            offset,
        )
    elif listing.searchable and state.q:
        searchable_module = cast(
            SearchableCrudModule[EntityT, CreateSchemaT, UpdateSchemaT], module
        )
        result = _page_list(
            sorted_list(
                list(searchable_module.search(session, state.q)),
                sort,
                order,
                listing.sort_fields,
            ),
            limit,
            offset,
        )
    else:
        callable_list = listing.list_func or module.list_all
        if not sort or sort not in listing.sort_fields:
            return _paginated_list(callable_list, session, limit, offset)
        result = _page_list(
            sorted_list(
                _paginated_list(callable_list, session, None, 0),
                sort,
                order,
                listing.sort_fields,
            ),
            limit,
            offset,
        )
    return result
