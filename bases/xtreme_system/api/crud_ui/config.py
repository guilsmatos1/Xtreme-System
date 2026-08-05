from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.crud_types import (
    AfterWriteHook,
    BeforeCreateHook,
    BeforeDeleteHook,
    BeforeUpdateHook,
    CsvRow,
    CtxForm,
    CtxList,
    EntityT,
    ListingSpec,
    ParseForm,
)
from xtreme_system.usuario import core as usuario

DepFactory = Callable[..., usuario.Usuario]


@dataclass(frozen=True)
class CrudUIResourceConfig[CreateSchemaT: BaseModel, UpdateSchemaT: BaseModel]:
    label: str
    create_schema: type[CreateSchemaT]
    update_schema: type[UpdateSchemaT]
    list_key: str
    item_key: str


@dataclass(frozen=True)
class CrudUITemplateConfig:
    list_template: str
    list_partial_template: str
    ok_partial_template: str
    form_template: str


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class CrudUIBehaviorConfig[EntityT, CreateSchemaT: BaseModel, UpdateSchemaT: BaseModel]:
    ctx_form: CtxForm = lambda _session: {}
    ctx_list: CtxList[EntityT] = lambda _session, _lista: {}
    parse_form: ParseForm = dict
    before_create: BeforeCreateHook[CreateSchemaT] | None = None
    before_update: BeforeUpdateHook[UpdateSchemaT] | None = None
    before_delete: BeforeDeleteHook[EntityT] | None = None
    after_create: AfterWriteHook[EntityT] | None = None
    after_update: AfterWriteHook[EntityT] | None = None
    after_delete: AfterWriteHook[EntityT] | None = None


CrudUIListConfig = ListingSpec


@dataclass(frozen=True)
class ColumnSpec[EntityT]:
    key: str
    label: str
    field: str | None = None
    table: bool = True
    html: Callable[[EntityT], Any] | None = None
    export: Callable[[EntityT], Any] | None = None


@dataclass(frozen=True)
class CrudUIExportConfig[EntityT]:
    csv_filename: str
    columns: Sequence["ColumnSpec[EntityT]"] | None = None
    csv_headers: list[str] | None = None
    csv_row: CsvRow[EntityT] | None = None
    csv_fields: list[str | None] | None = None
    pagina: str | None = None


@dataclass(frozen=True)
class CrudUIReferenceConfig:
    query: Callable[[Session], Any]
    search_query: Callable[[Session, str], Any]
    label: Callable[[Any], str]
    campo: str


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class CrudUIRouteConfig:
    register_list: bool = True
    register_create: bool = True
    register_update: bool = True
    register_edit: bool = True
    register_delete: bool = True
    delete_requires_admin: bool = True
    editar_dep: DepFactory | None = None
    excluir_dep: DepFactory | None = None
    cadastrar_dep: DepFactory | None = None


@dataclass(frozen=True)
class CrudUIListRouteConfig[EntityT]:
    list_key: str
    list_template: str
    list_partial_template: str
    listing: ListingSpec[EntityT]
    ctx_list: CtxList[EntityT]
    columns: Sequence["ColumnSpec[EntityT]"] | None = None
    pagina: str | None = None


@dataclass(frozen=True)
class CrudUIExportRouteConfig[EntityT]:
    listing: ListingSpec[EntityT]
    csv_filename: str
    columns: Sequence[ColumnSpec[EntityT]] | None = None
    csv_headers: list[str] | None = None
    csv_row: CsvRow[EntityT] | None = None
    csv_fields: list[str | None] | None = None
    pagina: str | None = None


@dataclass(frozen=True)
class CrudUINewRouteConfig:
    cadastrar_dep: DepFactory | None = None


@dataclass(frozen=True)
class CrudUIEditRouteConfig:
    label: str
    editar_dep: DepFactory | None = None


@dataclass(frozen=True)
class CrudUICreateRouteConfig[EntityT, CreateSchemaT: BaseModel]:
    label: str
    create_schema: type[CreateSchemaT]
    list_key: str
    ok_partial_template: str
    ctx_list: CtxList[EntityT]
    parse_form: ParseForm
    pagina: str | None
    before_create: BeforeCreateHook[CreateSchemaT] | None
    after_create: AfterWriteHook[EntityT] | None
    listing: ListingSpec[EntityT]
    cadastrar_dep: DepFactory | None = None


@dataclass(frozen=True)
class CrudUIUpdateRouteConfig[EntityT, UpdateSchemaT: BaseModel]:
    label: str
    update_schema: type[UpdateSchemaT]
    list_key: str
    ok_partial_template: str
    ctx_list: CtxList[EntityT]
    parse_form: ParseForm
    before_update: BeforeUpdateHook[UpdateSchemaT] | None
    after_update: AfterWriteHook[EntityT] | None
    listing: ListingSpec[EntityT]
    editar_dep: DepFactory | None = None
    pagina: str | None = None


@dataclass(frozen=True)
class CrudUIDeleteRouteConfig[EntityT]:
    label: str
    list_key: str
    list_partial_template: str
    ctx_list: CtxList[EntityT]
    before_delete: BeforeDeleteHook[EntityT] | None
    after_delete: AfterWriteHook[EntityT] | None
    delete_requires_admin: bool
    listing: ListingSpec[EntityT]
    excluir_dep: DepFactory | None = None


DEFAULT_CRUD_UI_ROUTES = CrudUIRouteConfig()
