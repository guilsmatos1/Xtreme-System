"""Filesystem locations for UI-managed uploads."""

from pathlib import Path

ui_dir = Path(__file__).resolve().parents[2]

__all__ = [
    "ui_dir",
    "uploads_cliente_dir",
    "uploads_compra_dir",
    "uploads_consignacao_dir",
    "uploads_contrato_venda_dir",
    "uploads_dir",
    "uploads_empresa_dir",
]


def uploads_dir(veiculo_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "veiculos" / str(veiculo_id)


def uploads_cliente_dir(cliente_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "clientes" / str(cliente_id) / "documentos"


def _uploads_procuracao_dir(veiculo_id: int) -> Path:
    return uploads_dir(veiculo_id) / "procuracao"


def uploads_compra_dir(compra_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "compras" / str(compra_id) / "comprovantes"


def uploads_consignacao_dir(consignacao_id: int) -> Path:
    return (
        ui_dir
        / "static"
        / "uploads"
        / "consignacoes"
        / str(consignacao_id)
        / "contratos"
    )


def uploads_empresa_dir() -> Path:
    return ui_dir / "static" / "uploads" / "empresa"


def uploads_contrato_venda_dir(venda_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "vendas" / str(venda_id) / "contrato"
