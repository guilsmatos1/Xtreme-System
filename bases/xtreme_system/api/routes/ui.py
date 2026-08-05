"""Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON."""

import importlib

from fastapi import APIRouter

routers: list[APIRouter] = []

for _module_name in (
    "auditoria",
    "auth",
    "clientes",
    "compras",
    "consignacoes",
    "conta",
    "custos_veiculos",
    "configuracoes",
    "dashboard",
    "investidores",
    "lancamentos",
    "perfis",
    "relatorios",
    "rsd",
    "usuarios",
    "veiculos",
    "veiculos_documentos",
    "veiculos_imagens",
    "veiculos_procuracao",
    "vendas",
):
    module = importlib.import_module(
        f"xtreme_system.api.routes.ui_routes.{_module_name}"
    )
    routers.append(module.router)

__all__ = ["routers"]
