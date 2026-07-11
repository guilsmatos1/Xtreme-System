from decimal import Decimal

from tests.factories import ClienteCreateFactory, VeiculoCreateFactory
from xtreme_system.cliente import core as cliente
from xtreme_system.veiculo import core as veiculo


def test_factories_geram_schemas_pydantic_validos() -> None:
    cliente_data = ClienteCreateFactory.build()
    veiculo_data = VeiculoCreateFactory.build(investidor_id=123)

    assert isinstance(cliente_data, cliente.ClienteCreate)
    assert cliente_data.tipo is cliente.TipoCliente.pessoa_fisica
    assert isinstance(veiculo_data, veiculo.VeiculoCreate)
    assert veiculo_data.investidor_id == 123
    assert veiculo_data.preco == Decimal("40000.00")
