from fastapi import FastAPI
from fastapi.routing import APIRoute

from xtreme_system.api.core import app
from xtreme_system.api.routes.ui_routes import vendas


def test_api_app_importa() -> None:
    assert app.title == "Xtreme Motors"


def test_vendas_router_pode_ser_montado_isoladamente() -> None:
    isolated_app = FastAPI()
    isolated_app.include_router(vendas.router)

    assert {
        route.path for route in vendas.router.routes if isinstance(route, APIRoute)
    } >= {
        "/ui/vendas",
        "/ui/vendas/{item_id}",
        "/ui/vendas/{item_id}/fechamento",
    }
    assert not isolated_app.user_middleware
