"""Filesystem locations for UI-managed uploads."""

from pathlib import Path

ui_dir = Path(__file__).resolve().parents[2]


def _uploads_dir(veiculo_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "veiculos" / str(veiculo_id)


def _uploads_cliente_dir(cliente_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "clientes" / str(cliente_id) / "documentos"


def _uploads_procuracao_dir(veiculo_id: int) -> Path:
    return _uploads_dir(veiculo_id) / "procuracao"


def _uploads_compra_dir(compra_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "compras" / str(compra_id) / "comprovantes"


def _uploads_empresa_dir() -> Path:
    return ui_dir / "static" / "uploads" / "empresa"


def _uploads_contrato_venda_dir(venda_id: int) -> Path:
    return ui_dir / "static" / "uploads" / "vendas" / str(venda_id) / "contrato"
