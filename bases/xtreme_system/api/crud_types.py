from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Query, Session

EntityT = TypeVar("EntityT")
ReadSchemaT = TypeVar("ReadSchemaT", bound=BaseModel)
CreateSchemaT = TypeVar("CreateSchemaT", bound=BaseModel)
UpdateSchemaT = TypeVar("UpdateSchemaT", bound=BaseModel)
CreateSchemaT_contra = TypeVar(
    "CreateSchemaT_contra", bound=BaseModel, contravariant=True
)
UpdateSchemaT_contra = TypeVar(
    "UpdateSchemaT_contra", bound=BaseModel, contravariant=True
)
ResultT = TypeVar("ResultT")
ArgT = TypeVar("ArgT")


class CrudModule(Protocol[EntityT, CreateSchemaT_contra, UpdateSchemaT_contra]):
    def list_all(
        self,
        session: Session,
        /,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[EntityT]: ...
    def get(self, session: Session, item_id: int, /) -> EntityT | None: ...
    def create(
        self,
        session: Session,
        data: CreateSchemaT_contra,
        actor_id: int | None = None,
        /,
    ) -> EntityT: ...
    def update(
        self,
        session: Session,
        obj: EntityT,
        data: UpdateSchemaT_contra,
        actor_id: int | None = None,
        /,
    ) -> EntityT: ...
    def delete(
        self,
        session: Session,
        obj: EntityT,
        actor_id: int | None = None,
        /,
    ) -> None: ...


class SearchableCrudModule(
    CrudModule[EntityT, CreateSchemaT_contra, UpdateSchemaT_contra],
    Protocol[EntityT, CreateSchemaT_contra, UpdateSchemaT_contra],
):
    def search(self, session: Session, term: str, /) -> list[EntityT]: ...


SortSpec = str | Callable[[EntityT], Any]
CtxForm = Callable[[Session], dict[str, Any]]
CtxList = Callable[[Session, list[EntityT]], dict[str, Any]]
ParseForm = Callable[[Any], dict[str, Any]]


class PlainListFunc(Protocol[EntityT]):
    def __call__(self, session: Session, /) -> list[EntityT]: ...


class PaginatedListFunc(Protocol[EntityT]):
    def __call__(
        self,
        session: Session,
        /,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[EntityT]: ...


class PlainSearchFunc(Protocol[EntityT]):
    def __call__(self, session: Session, term: str, /) -> list[EntityT]: ...


class ColumnSearchFunc(Protocol[EntityT]):
    def __call__(
        self,
        session: Session,
        term: str,
        /,
        *,
        column: str | None = None,
    ) -> list[EntityT]: ...


def adapt_list_func[M](func: PlainListFunc[M]) -> PaginatedListFunc[M]:
    def adapted(
        session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[M]:
        del limit, offset
        return func(session)

    return adapted


def adapt_search_func[M](func: PlainSearchFunc[M]) -> ColumnSearchFunc[M]:
    def adapted(session: Session, term: str, *, column: str | None = None) -> list[M]:
        del column
        return func(session, term)

    return adapted


ListFunc = PaginatedListFunc
SearchFunc = ColumnSearchFunc
type QueryFunc[EntityT] = Callable[[Session], Query[EntityT]]
type SearchQueryFunc[EntityT] = Callable[..., Query[EntityT]]
CsvRow = Callable[[EntityT], list[Any]]


@dataclass(frozen=True)
class ListingSpec[EntityT]:
    searchable: bool = False
    list_func: ListFunc[EntityT] | None = None
    search_func: SearchFunc[EntityT] | None = None
    sort_fields: Mapping[str, SortSpec[EntityT]] = field(default_factory=dict)
    sql_sort_fields: Mapping[str, Any] | None = None
    query_func: QueryFunc[EntityT] | None = None
    search_query_func: SearchQueryFunc[EntityT] | None = None


@dataclass(frozen=True)
class FormSpec:
    templates: Jinja2Templates
    form_template: str
    ctx_form: CtxForm
    item_key: str


BeforeCreateHook = Callable[[Session, CreateSchemaT], None]
BeforeUpdateHook = Callable[[Session, UpdateSchemaT], None]
BeforeUpdateEntityHook = Callable[[Session, EntityT, UpdateSchemaT], None]
BeforeDeleteHook = Callable[[Session, EntityT, int | None], None]
AfterWriteHook = Callable[[Session, EntityT, int | None], Any]
