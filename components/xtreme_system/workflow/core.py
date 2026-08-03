"""Cross-domain workflows shared by the JSON API and HTMX UI."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.compra import core as compra
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.venda import status_veiculo


def is_lancamento_automatico(obj: caixa.LancamentoInvestimento) -> bool:
    return obj.origem != caixa.OrigemLancamento.manual


def sincronizar_caixa_compra(
    session: Session, obj: compra.Compra, actor_id: int | None = None
) -> None:
    """O lançamento de custo do veículo espelha o valor da compra."""
    veiculo_obj = veiculo.get(session, obj.veiculo_id)
    if veiculo_obj is not None:
        caixa.sincronizar_lancamento_veiculo(session, veiculo_obj, actor_id)


def validate_veiculo_fks(
    session: Session,
    data: veiculo.VeiculoCreate | veiculo.VeiculoUpdate,
    *,
    update: bool = False,
) -> None:
    investidor_id = data.investidor_id
    investidor_deve_existir = not update or investidor_id is not None
    if investidor_deve_existir and (
        investidor_id is None or investidor.get(session, investidor_id) is None
    ):
        raise HTTPException(status_code=400, detail="investidor_id inexistente")
    if (
        not update
        and isinstance(data, veiculo.VeiculoCreate)
        and veiculo.get_by_placa(session, data.placa)
    ):
        raise HTTPException(status_code=400, detail="placa já cadastrada")


ClienteVeiculoData = (
    compra.CompraCreate | compra.CompraUpdate | venda.VendaCreate | venda.VendaUpdate
)


def validate_cliente_veiculo_fks(session: Session, data: ClienteVeiculoData) -> None:
    if data.cliente_id is not None and cliente.get(session, data.cliente_id) is None:
        raise HTTPException(status_code=400, detail="cliente_id inexistente")
    if data.veiculo_id is not None and veiculo.get(session, data.veiculo_id) is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if isinstance(data, (venda.VendaCreate, venda.VendaUpdate)):
        if (
            data.veiculo_troca_id is not None
            and veiculo.get(session, data.veiculo_troca_id) is None
        ):
            raise HTTPException(status_code=400, detail="veiculo_troca_id inexistente")
        if (
            data.vendedor_id is not None
            and usuario.get(session, data.vendedor_id) is None
        ):
            raise HTTPException(status_code=400, detail="vendedor_id inexistente")


def validate_valores_venda_update(
    venda_obj: venda.Venda, data: venda.VendaUpdate
) -> None:
    try:
        venda.validate_valores_venda_update(venda_obj, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def validate_veiculo_disponivel_para_venda(session: Session, veiculo_id: int) -> None:
    veiculo_obj = session.get(veiculo.Veiculo, veiculo_id, with_for_update=True)
    if veiculo_obj is None:
        raise HTTPException(status_code=400, detail="veiculo_id inexistente")
    if veiculo_obj.status != veiculo.StatusVeiculo.disponivel:
        raise HTTPException(status_code=409, detail="veículo indisponível")


def validate_venda_create(session: Session, data: venda.VendaCreate) -> None:
    validate_cliente_veiculo_fks(session, data)
    validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


def validate_venda_update(
    session: Session, obj: venda.Venda, data: venda.VendaUpdate
) -> None:
    validate_cliente_veiculo_fks(session, data)
    validate_valores_venda_update(obj, data)
    if data.veiculo_id is not None and data.veiculo_id != obj.veiculo_id:
        validate_veiculo_disponivel_para_venda(session, data.veiculo_id)


def recompute_vehicle_status_on_delete(
    session: Session, venda_obj: venda.Venda, _actor_id: int | None = None
) -> None:
    status_veiculo.recomputar_status_veiculo_por_vendas(
        session, venda_obj.veiculo_id, excluir_venda_id=venda_obj.id
    )
    if venda_obj.veiculo_troca_id is not None:
        status_veiculo.recomputar_status_veiculo_por_vendas(
            session, venda_obj.veiculo_troca_id, excluir_venda_id=venda_obj.id
        )
