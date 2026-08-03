"""Public compatibility API for CRUD UI route factories."""

import sys

from xtreme_system.api.crud_ui.config import (
    DEFAULT_CRUD_UI_ROUTES,
    ColumnSpec,
    CrudUIBehaviorConfig,
    CrudUICreateRouteConfig,
    CrudUIDeleteRouteConfig,
    CrudUIEditRouteConfig,
    CrudUIExportConfig,
    CrudUIExportRouteConfig,
    CrudUIListConfig,
    CrudUIListRouteConfig,
    CrudUINewRouteConfig,
    CrudUIReferenceConfig,
    CrudUIResourceConfig,
    CrudUIRouteConfig,
    CrudUITemplateConfig,
    CrudUIUpdateRouteConfig,
    DepFactory,
)
from xtreme_system.api.crud_ui.helpers import (
    LIST_LIMIT_MAX,
    current_list_state,
    delete_list_response,
    write_conflict_response,
    write_ok_response,
)
from xtreme_system.api.crud_ui.registrars import (
    register_create_route,
    register_crud_ui_routes,
    register_delete_route,
    register_edit_route,
    register_export_route,
    register_list_route,
    register_new_route,
    register_reference_lookup_routes,
    register_update_route,
)
from xtreme_system.perfil import core as perfil

sys.modules.setdefault(__name__ + ".perfil", perfil)

_DEFAULT_CRUD_UI_ROUTES = DEFAULT_CRUD_UI_ROUTES
_current_list_state = current_list_state

__all__ = [
    "LIST_LIMIT_MAX",
    "ColumnSpec",
    "CrudUIBehaviorConfig",
    "CrudUICreateRouteConfig",
    "CrudUIDeleteRouteConfig",
    "CrudUIEditRouteConfig",
    "CrudUIExportConfig",
    "CrudUIExportRouteConfig",
    "CrudUIListConfig",
    "CrudUIListRouteConfig",
    "CrudUINewRouteConfig",
    "CrudUIReferenceConfig",
    "CrudUIResourceConfig",
    "CrudUIRouteConfig",
    "CrudUITemplateConfig",
    "CrudUIUpdateRouteConfig",
    "DepFactory",
    "delete_list_response",
    "register_create_route",
    "register_crud_ui_routes",
    "register_delete_route",
    "register_edit_route",
    "register_export_route",
    "register_list_route",
    "register_new_route",
    "register_reference_lookup_routes",
    "register_update_route",
    "write_conflict_response",
    "write_ok_response",
]
