"""Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON."""

import importlib
import sys
from types import ModuleType

from xtreme_system.api.routes.ui_routes import compras as _compras
from xtreme_system.api.routes.ui_routes import veiculos as _veiculos
from xtreme_system.api.routes.ui_routes import veiculos_imagens as _veiculos_imagens
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_cliente_dir,
    _uploads_compra_dir,
    _uploads_dir,
    _validar_uploads,
)
from xtreme_system.imagem_veiculo import core as imagem_veiculo

for _module_name in (
    "auditoria",
    "auth",
    "clientes",
    "compras",
    "custos_veiculos",
    "configuracoes",
    "dashboard",
    "investidores",
    "lancamentos",
    "perfis",
    "usuarios",
    "veiculos_cliente_vendedor",
    "veiculos_comprovantes",
    "veiculos_procuracao",
    "vendas",
):
    importlib.import_module(f"xtreme_system.api.routes.ui_routes.{_module_name}")


class _UiCompatModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name == "_uploads_dir":
            setattr(_veiculos, name, value)
            setattr(_veiculos_imagens, name, value)
        if name == "_uploads_cliente_dir":
            setattr(_veiculos, name, value)
        if name == "_uploads_compra_dir":
            setattr(_compras, name, value)


sys.modules[__name__].__class__ = _UiCompatModule

__all__ = [
    "_uploads_cliente_dir",
    "_uploads_compra_dir",
    "_uploads_dir",
    "_validar_uploads",
    "imagem_veiculo",
]
