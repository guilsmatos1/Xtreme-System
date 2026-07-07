"""CRUD end-to-end dos bricks, em SQLite in-memory (sem depender do Postgres)."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from xtreme_system.database.core import Base
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.veiculo import core as veiculo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_veiculo_ciclo_completo(session: Session) -> None:
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    meio = meio_captacao.create(
        session, meio_captacao.MeioCaptacaoCreate(nome="Instagram")
    )

    criado = veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Gol",
            cor="Branco",
            ano=2018,
            placa="AAA1B22",
            km=70000,
            preco=Decimal("32000.00"),
            investidor_id=inv.id,
            meio_captacao_id=meio.id,
        ),
    )
    assert criado.id is not None
    assert criado.status is veiculo.StatusVeiculo.disponivel
    assert criado.investidor.nome == "Ana"

    veiculo.update(
        session, criado, veiculo.VeiculoUpdate(status=veiculo.StatusVeiculo.vendido)
    )
    assert veiculo.get(session, criado.id).status is veiculo.StatusVeiculo.vendido
    assert len(veiculo.list_all(session)) == 1

    veiculo.delete(session, criado)
    assert veiculo.get(session, criado.id) is None
