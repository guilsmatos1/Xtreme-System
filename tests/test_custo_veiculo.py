"""Custos de veículos: CRUD e validações do componente."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


def _veiculo(session: Session) -> veiculo.Veiculo:
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    session.add(u)
    session.flush()
    session.info["usuario_id"] = u.id
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Investidor"))
    return veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Onix",
            cor="Prata",
            ano=2024,
            placa="CST1A23",
            km=12000,
            preco=Decimal("85000.00"),
            investidor_id=inv.id,
        ),
    )


def test_crud_custo_veiculo(db_session: Session) -> None:
    item = _veiculo(db_session)

    custo = custo_veiculo.create(
        db_session,
        custo_veiculo.CustoVeiculoCreate(
            veiculo_id=item.id,
            categoria="Manutenção",
            descricao="Troca de óleo",
            valor=Decimal("250.00"),
            data_custo="2026-07-14",
        ),
    )

    assert custo.id
    assert custo.veiculo.modelo == "Onix"
    assert custo_veiculo.list_all(db_session) == [custo]

    atualizado = custo_veiculo.update(
        db_session,
        custo,
        custo_veiculo.CustoVeiculoUpdate(
            categoria="Peças", valor=Decimal("300.00"), descricao=None
        ),
    )
    assert atualizado.categoria == "Peças"
    assert atualizado.valor == Decimal("300.00")

    custo_veiculo.delete(db_session, atualizado)
    assert custo_veiculo.list_all(db_session) == []


def test_schema_rejeita_valor_nao_positivo_e_categoria_vazia() -> None:
    with pytest.raises(ValidationError):
        custo_veiculo.CustoVeiculoCreate(
            veiculo_id=1,
            categoria="Manutenção",
            valor=Decimal("0"),
            data_custo="2026-07-14",
        )

    with pytest.raises(ValidationError):
        custo_veiculo.CustoVeiculoCreate(
            veiculo_id=1,
            categoria="",
            valor=Decimal("10.00"),
            data_custo="2026-07-14",
        )


def test_custo_veiculo_remove_em_cascata_ao_excluir_veiculo(
    db_session: Session,
) -> None:
    item = _veiculo(db_session)
    custo_veiculo.create(
        db_session,
        custo_veiculo.CustoVeiculoCreate(
            veiculo_id=item.id,
            categoria="Peças",
            valor=Decimal("150.00"),
            data_custo="2026-07-14",
        ),
    )

    veiculo.delete(db_session, item)

    assert custo_veiculo.list_all(db_session) == []
