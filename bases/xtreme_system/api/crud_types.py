from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

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


@dataclass(frozen=True)
class SortField[EntityT]:
    """One sort contract; ``sql=None`` explicitly means Python-only."""

    python: SortSpec[EntityT]
    sql: Any | None = None

    def __post_init__(self) -> None:
        if self.sql is not None and not hasattr(self.sql, "asc"):
            raise TypeError


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
type ListingSource = Literal["module", "functions", "query"]
CsvRow = Callable[[EntityT], list[Any]]


class ListingSpecError(ValueError):
    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source} listing source {reason}")


@dataclass(frozen=True)
class ListingSpec[EntityT]:  # pylint: disable=too-many-instance-attributes
    """Listing configuration with one explicit data-source contract."""

    searchable: bool = False
    paginated: bool = True
    source: ListingSource = "module"
    list_func: ListFunc[EntityT] | None = None
    search_func: SearchFunc[EntityT] | None = None
    sort_fields: Mapping[str, SortField[EntityT]] = field(default_factory=dict)
    default_sort: str = ""
    default_order: str = "asc"
    query_func: QueryFunc[EntityT] | None = None
    search_query_func: SearchQueryFunc[EntityT] | None = None

    def __post_init__(self) -> None:
        if self.source == "module":
            if any(
                func is not None
                for func in (
                    self.list_func,
                    self.search_func,
                    self.query_func,
                    self.search_query_func,
                )
            ):
                raise ListingSpecError(self.source, "does not accept custom callables")
        elif self.source == "functions":
            if self.list_func is None:
                raise ListingSpecError(self.source, "requires list_func")
            if self.query_func is not None or self.search_query_func is not None:
                raise ListingSpecError(self.source, "does not accept query callables")
            if self.searchable and self.search_func is None:
                raise ListingSpecError(
                    self.source, "requires search_func when searchable"
                )
        elif self.source == "query":
            if self.query_func is None:
                raise ListingSpecError(self.source, "requires query_func")
            if self.list_func is not None or self.search_func is not None:
                raise ListingSpecError(self.source, "does not accept list callables")
            if self.searchable and self.search_query_func is None:
                raise ListingSpecError(
                    self.source, "requires search_query_func when searchable"
                )
        else:
            raise ListingSpecError(self.source, "is unknown")


@dataclass(frozen=True)
class ListState:
    q: str = ""
    sort: str = ""
    order: str = "asc"
    search_column: str = ""
    limit: int | None = None
    offset: int = 0


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
