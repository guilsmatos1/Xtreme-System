"""API FastAPI: CRUD de investidores, meios de captação e veículos."""

from xtreme_system.api.routes import json as _json  # noqa: F401
from xtreme_system.api.routes import ui as _ui  # noqa: F401
from xtreme_system.api.setup import app

__all__ = ["app"]
