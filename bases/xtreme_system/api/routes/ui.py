"""Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON."""

import importlib
import sys
from types import ModuleType

from xtreme_system.api.routes.ui_routes import veiculos as _veiculos
from xtreme_system.api.routes.ui_routes.common import (
    _uploads_cliente_dir,
    _uploads_dir,
    _validar_uploads,
)
from xtreme_system.documento_veiculo import core as documento_veiculo
from xtreme_system.imagem_documento_cliente import core as imagem_documento_cliente
from xtreme_system.imagem_veiculo import core as imagem_veiculo

for _module_name in (
    "auditoria",
    "auth",
    "clientes",
    "configuracoes",
    "dashboard",
    "investidores",
    "perfis",
    "usuarios",
    "vendas",
):
    importlib.import_module(f"xtreme_system.api.routes.ui_routes.{_module_name}")

_salvar_documento_veiculo = _veiculos._salvar_documento_veiculo  # noqa: SLF001
_salvar_documentos_cliente = _veiculos._salvar_documentos_cliente  # noqa: SLF001


class _UiCompatModule(ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name in {"_uploads_dir", "_uploads_cliente_dir"}:
            setattr(_veiculos, name, value)


sys.modules[__name__].__class__ = _UiCompatModule

__all__ = [
    "_salvar_documento_veiculo",
    "_salvar_documentos_cliente",
    "_uploads_cliente_dir",
    "_uploads_dir",
    "_validar_uploads",
    "documento_veiculo",
    "imagem_documento_cliente",
    "imagem_veiculo",
]
