from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

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
    def list_all(self, session: Session, /) -> list[EntityT]: ...
    def get(self, session: Session, item_id: int, /) -> EntityT | None: ...
    def create(self, session: Session, data: CreateSchemaT_contra, /) -> EntityT: ...
    def update(
        self, session: Session, obj: EntityT, data: UpdateSchemaT_contra, /
    ) -> EntityT: ...
    def delete(self, session: Session, obj: EntityT, /) -> None: ...


class SearchableCrudModule(
    CrudModule[EntityT, CreateSchemaT_contra, UpdateSchemaT_contra],
    Protocol[EntityT, CreateSchemaT_contra, UpdateSchemaT_contra],
):
    def search(self, session: Session, term: str, /) -> list[EntityT]: ...


SortSpec = str | Callable[[EntityT], Any]
CtxForm = Callable[[Session], dict[str, Any]]
CtxList = Callable[[Session, list[EntityT]], dict[str, Any]]
ParseForm = Callable[[Any], dict[str, Any]]
ListFunc = Callable[[Session], list[EntityT]]
SearchFunc = Callable[[Session, str], list[EntityT]]
CsvRow = Callable[[EntityT], list[Any]]
BeforeCreateHook = Callable[[Session, CreateSchemaT], None]
BeforeUpdateHook = Callable[[Session, UpdateSchemaT], None]
BeforeUpdateEntityHook = Callable[[Session, EntityT, UpdateSchemaT], None]
BeforeDeleteHook = Callable[[Session, EntityT], None]
AfterWriteHook = Callable[[Session, EntityT], Any]
