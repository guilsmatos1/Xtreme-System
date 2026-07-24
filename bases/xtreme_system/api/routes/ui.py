"""Rotas HTMX (server-rendered). Auth por cookie httpOnly, paralela à API JSON."""

import importlib

for _module_name in (
    "auditoria",
    "auth",
    "clientes",
    "compras",
    "conta",
    "custos_veiculos",
    "configuracoes",
    "dashboard",
    "investidores",
    "lancamentos",
    "perfis",
    "relatorios",
    "usuarios",
    "veiculos",
    "veiculos_cliente_vendedor",
    "veiculos_documentos",
    "veiculos_imagens",
    "veiculos_procuracao",
    "vendas",
):
    importlib.import_module(f"xtreme_system.api.routes.ui_routes.{_module_name}")
