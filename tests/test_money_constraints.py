from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.exc import IntegrityError

from xtreme_system.caixa.core import LancamentoInvestimento
from xtreme_system.compra.core import Compra
from xtreme_system.custo_veiculo.core import CustoVeiculo
from xtreme_system.database.core import Base
from xtreme_system.fechamento_venda.core import ParticipacaoFechamentoVenda
from xtreme_system.veiculo.core import Veiculo
from xtreme_system.venda.core import Venda


def test_money_check_constraints_are_in_metadata() -> None:
    expected = {
        "veiculo": {"ck_veiculo_preco_positive"},
        "venda": {
            "ck_venda_valor_venda_positive",
            "ck_venda_valor_entrada_nonnegative",
            "ck_venda_valor_entrada_lte_valor_venda",
            "ck_venda_debitos_nonnegative",
            "ck_venda_valor_diferenca_nonnegative",
            "ck_venda_valor_pendente_nonnegative",
        },
        "compra": {
            "ck_compra_valor_compra_positive",
            "ck_compra_debitos_nonnegative",
        },
        "custo_veiculo": {"ck_custo_veiculo_valor_positive"},
        "lancamento_investimento": {"ck_lancamento_investimento_valor_positive"},
        "participacao_fechamento_venda": {"ck_participacao_percentual_range"},
    }

    for table_name, names in expected.items():
        actual = {
            constraint.name
            for constraint in Base.metadata.tables[table_name].constraints
            if constraint.name in names
        }
        assert actual == names


@pytest.mark.parametrize(
    ("table", "values"),
    [
        (
            Veiculo.__table__,
            {
                "tipo": "moto",
                "modelo": "modelo",
                "cor": "cor",
                "ano": 2026,
                "placa": "ABC1234",
                "preco": Decimal("0"),
                "status": "disponivel",
                "tipo_entrada": "compra",
                "revisao": False,
                "investidor_id": 1,
            },
        ),
        (
            Venda.__table__,
            {
                "cliente_id": 1,
                "veiculo_id": 1,
                "valor_venda": Decimal("0"),
                "forma_pagamento": "pix",
                "status": "pendente",
                "pagamento_pendente": False,
            },
        ),
        (
            Compra.__table__,
            {
                "cliente_id": 1,
                "veiculo_id": 1,
                "data_compra": date(2026, 7, 31),
                "valor_compra": Decimal("0"),
                "status": "pendente",
            },
        ),
        (
            CustoVeiculo.__table__,
            {
                "veiculo_id": 1,
                "categoria": "manutencao",
                "valor": Decimal("0"),
                "data_custo": date(2026, 7, 31),
            },
        ),
        (
            LancamentoInvestimento.__table__,
            {
                "investidor_id": 1,
                "tipo": "aporte",
                "origem": "manual",
                "valor": Decimal("0"),
                "descricao": "aporte",
            },
        ),
        (
            ParticipacaoFechamentoVenda.__table__,
            {
                "fechamento_venda_id": 1,
                "investidor_id": 1,
                "percentual": Decimal("100.01"),
                "valor": Decimal("1.00"),
            },
        ),
    ],
)
def test_money_check_constraints_reject_invalid_values(
    table: Table, values: Mapping[str, Any]
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with (
            engine.begin() as connection,
            connection.begin_nested(),
            pytest.raises(IntegrityError),
        ):
            connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()


def test_venda_entry_cannot_exceed_sale_value() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    venda_table = cast(Table, Venda.__table__)
    try:
        with (
            engine.begin() as connection,
            connection.begin_nested(),
            pytest.raises(IntegrityError),
        ):
            connection.execute(
                venda_table.insert().values(
                    cliente_id=1,
                    veiculo_id=1,
                    valor_venda=Decimal("100.00"),
                    valor_entrada=Decimal("100.01"),
                    forma_pagamento="pix",
                    status="pendente",
                    pagamento_pendente=False,
                )
            )
    finally:
        engine.dispose()


def test_vehicle_origin_investment_allows_zero_cost_placeholder() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    lancamento_table = cast(Table, LancamentoInvestimento.__table__)
    try:
        with engine.begin() as connection:
            connection.execute(
                lancamento_table.insert().values(
                    investidor_id=1,
                    tipo="custo",
                    origem="veiculo",
                    valor=Decimal("0"),
                    descricao="consignado",
                )
            )
    finally:
        engine.dispose()
