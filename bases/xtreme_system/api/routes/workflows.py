"""Shared route workflow helpers used by JSON and HTMX routes."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda


def validate_veiculo_fks(session: Session, data: Any, *, update: bool = False) -> None:
    investidor_id = data.investidor_id
    investidor_deve_existir = not update or investidor_id is not None
    if investidor_deve_existir and investidor.get(session, investidor_id) is None:
        raise HTTPException(status_code=400, detail="investidor_id inexistente")
    if (
        not update
        and hasattr(data, "placa")
        and veiculo.get_by_placa(session, data.placa)
    ):
        raise HTTPException(status_code=400, detail="placa já cadastrada")


def validate_cliente_veiculo_fks(session: Session, data: Any) -> None:
    cli_id = getattr(data, "cliente_id", None)
    vei_id = getattr(data, "veiculo_id", None)
    troca_id = getattr(data, "veiculo_troca_id", None)
    if cli_id is not None and cliente.get(session, cli_id) is None:
        raise HTTPException(status_code=400, detail="cliente_id inexistente")
    if vei_id is not None and veiculo.get(session, vei_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if troca_id is not None and veiculo.get(session, troca_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_troca_id inexistente")
    ven_id = getattr(data, "vendedor_id", None)
    if ven_id is not None and usuario.get(session, ven_id) is None:
        raise HTTPException(status_code=400, detail="vendedor_id inexistente")


def validate_valores_venda_update(venda_obj: venda.Venda, data: Any) -> None:
    try:
        venda.validate_valores_venda_update(venda_obj, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def validate_veiculo_disponivel_para_venda(session: Session, veiculo_id: int) -> None:
    v = session.get(veiculo.Veiculo, veiculo_id, with_for_update=True)
    if v is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if v.status != veiculo.StatusVeiculo.disponivel:
        raise HTTPException(status_code=409, detail="veículo indisponível")


def recompute_vehicle_status_on_delete(
    session: Session, venda_obj: Any, _actor_id: int | None = None
) -> None:
    if venda_obj.status != venda.StatusVenda.concluido:
        return
    venda.recomputar_status_veiculo_por_vendas(
        session, venda_obj.veiculo_id, excluir_venda_id=venda_obj.id
    )
    if venda_obj.veiculo_troca_id is not None:
        venda.recomputar_status_veiculo_por_vendas(
            session, venda_obj.veiculo_troca_id, excluir_venda_id=venda_obj.id
        )
