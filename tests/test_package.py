from xtreme_system.api.core import app


def test_api_app_importa() -> None:
    assert app.title == "Xtreme Estoque"
