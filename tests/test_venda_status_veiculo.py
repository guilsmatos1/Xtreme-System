import threading
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda
from xtreme_system.venda import status_veiculo
from xtreme_system.workflow.core import validate_veiculo_disponivel_para_venda


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


def test_recomputar_status_bloqueia_criacao_de_venda_concorrente(
    db_session: Session,
) -> None:
    engine = db_session.get_bind()
    if engine.dialect.name != "postgresql":
        pytest.skip("row-lock concurrency requires PostgreSQL")

    customer, vehicle, _ = _seed_entities(db_session)
    db_session.commit()

    session_one = Session(bind=engine, autoflush=False, expire_on_commit=False)
    sale_validated = threading.Event()
    sale_started = threading.Event()
    allow_sale = threading.Event()
    errors: list[BaseException] = []

    def create_concurrent_sale() -> None:
        session_two = Session(bind=engine, autoflush=False, expire_on_commit=False)
        try:
            sale_started.set()
            validate_veiculo_disponivel_para_venda(session_two, vehicle.id)
            sale_validated.set()
            if not allow_sale.wait(timeout=2):
                errors.append(AssertionError("concurrent sale was not released"))
                return
            venda.create(
                session_two,
                venda.VendaCreate(
                    cliente_id=customer.id,
                    veiculo_id=vehicle.id,
                    valor_venda=Decimal("40000.00"),
                    forma_pagamento="a_vista",
                    parcelas=1,
                ),
            )
            session_two.commit()
        except BaseException as exc:
            errors.append(exc)
            session_two.rollback()
        finally:
            session_two.close()

    thread = threading.Thread(target=create_concurrent_sale)
    try:
        status_veiculo.recomputar_status_veiculo_por_vendas(session_one, vehicle.id)
        thread.start()
        assert sale_started.wait(timeout=1)
        assert not sale_validated.wait(timeout=1)

        session_one.commit()
        allow_sale.set()
        thread.join(timeout=2)
    finally:
        allow_sale.set()
        if session_one.in_transaction():
            session_one.rollback()
        if thread.is_alive():
            thread.join(timeout=2)
        session_one.close()

    assert not thread.is_alive()
    if errors:
        raise errors[0]

    db_session.expire_all()
    persisted_vehicle = db_session.get(veiculo.Veiculo, vehicle.id)
    assert persisted_vehicle is not None
    assert persisted_vehicle.status is veiculo.StatusVeiculo.reservado
