from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.venda import status_veiculo


def _seed_entities(
    session: Session,
) -> tuple[cliente.Cliente, veiculo.Veiculo, veiculo.Veiculo]:
    owner = investidor.Investidor(nome="Investidor status")
    customer = cliente.Cliente(
        nome="Cliente status",
        documento="12345678901",
        tipo=cliente.TipoCliente.pessoa_fisica,
    )
    vehicle = veiculo.Veiculo(
        tipo=veiculo.TipoVeiculo.carro,
        modelo="Gol",
        cor="Branco",
        ano=2020,
        placa="ABC1D23",
        preco=Decimal("40000.00"),
        investidor=owner,
    )
    source_vehicle = veiculo.Veiculo(
        tipo=veiculo.TipoVeiculo.carro,
        modelo="Onix",
        cor="Preto",
        ano=2021,
        placa="XYZ9G87",
        preco=Decimal("50000.00"),
        investidor=owner,
    )
    session.add_all([customer, vehicle, source_vehicle])
    session.flush()
    return customer, vehicle, source_vehicle


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("trade", veiculo.StatusVeiculo.disponivel),
        ("completed", veiculo.StatusVeiculo.vendido),
        ("pending", veiculo.StatusVeiculo.reservado),
        ("none", veiculo.StatusVeiculo.disponivel),
    ],
)
def test_recomputar_status_aplica_precedencia(
    db_session: Session,
    scenario: str,
    expected: veiculo.StatusVeiculo,
) -> None:
    customer, vehicle, source_vehicle = _seed_entities(db_session)
    if scenario != "none":
        db_session.add(
            venda.Venda(
                cliente_id=customer.id,
                veiculo_id=source_vehicle.id if scenario == "trade" else vehicle.id,
                veiculo_troca_id=vehicle.id if scenario == "trade" else None,
                valor_venda=Decimal("40000.00"),
                forma_pagamento="a_vista",
                parcelas=1,
                status=(
                    venda.StatusVenda.concluido
                    if scenario in {"trade", "completed"}
                    else venda.StatusVenda.pendente
                ),
            )
        )
        db_session.flush()

    status_veiculo.recomputar_status_veiculo_por_vendas(db_session, vehicle.id)

    assert vehicle.status is expected


def test_recomputar_status_preserva_indisponivel(db_session: Session) -> None:
    customer, vehicle, _ = _seed_entities(db_session)
    vehicle.status = veiculo.StatusVeiculo.indisponivel
    db_session.add(
        venda.Venda(
            cliente_id=customer.id,
            veiculo_id=vehicle.id,
            valor_venda=Decimal("40000.00"),
            forma_pagamento="a_vista",
            parcelas=1,
            status=venda.StatusVenda.pendente,
        )
    )
    db_session.flush()

    status_veiculo.recomputar_status_veiculo_por_vendas(db_session, vehicle.id)

    assert vehicle.status is veiculo.StatusVeiculo.indisponivel
