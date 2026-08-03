"""Cross-aggregate vehicle status rules driven by sales."""

from __future__ import annotations

from sqlalchemy.orm import Session

from xtreme_system.crud import core as crud
from xtreme_system.veiculo.core import StatusVeiculo, Veiculo
from xtreme_system.venda import core as venda


def veiculo_tem_outra_venda_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(venda.Venda).filter(
        venda.Venda.veiculo_id == veiculo_id,
        venda.Venda.status == venda.StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(venda.Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def veiculo_tem_outra_venda_pendente(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(venda.Venda).filter(
        venda.Venda.veiculo_id == veiculo_id,
        venda.Venda.status == venda.StatusVenda.pendente,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(venda.Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def veiculo_tem_outra_troca_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(venda.Venda).filter(
        venda.Venda.veiculo_troca_id == veiculo_id,
        venda.Venda.status == venda.StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(venda.Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def recomputar_status_veiculo_por_vendas(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> None:
    """Apply sales precedence: sold > reserved > available.

    A completed trade-in makes the vehicle available, and ``indisponivel``
    remains a manual override that synchronization never replaces.
    """
    v = session.get(Veiculo, veiculo_id, with_for_update=True)
    if v is None or v.status == StatusVeiculo.indisponivel:
        return
    if veiculo_tem_outra_troca_concluida(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.disponivel
    elif veiculo_tem_outra_venda_concluida(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.vendido
    elif veiculo_tem_outra_venda_pendente(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.reservado
    else:
        v.status = StatusVeiculo.disponivel


def sincronizar_apos_escrita(
    session: Session,
    obj: venda.Venda,
    *,
    anterior_id: int | None = None,
    troca_anterior_id: int | None = None,
) -> venda.Venda:
    """Recompute all vehicles affected by a persisted sale write."""
    if anterior_id is not None and anterior_id != obj.veiculo_id:
        recomputar_status_veiculo_por_vendas(
            session, anterior_id, excluir_venda_id=obj.id
        )
    recomputar_status_veiculo_por_vendas(session, obj.veiculo_id)
    if troca_anterior_id is not None and troca_anterior_id != obj.veiculo_troca_id:
        recomputar_status_veiculo_por_vendas(
            session, troca_anterior_id, excluir_venda_id=obj.id
        )
    if obj.veiculo_troca_id is not None:
        recomputar_status_veiculo_por_vendas(session, obj.veiculo_troca_id)
    crud.flush(session)
    session.refresh(obj)
    return obj
