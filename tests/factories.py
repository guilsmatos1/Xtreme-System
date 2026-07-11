"""Factories de schemas Pydantic para testes."""

from datetime import date
from decimal import Decimal
from itertools import count

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from xtreme_system.cliente import core as cliente
from xtreme_system.investidor import core as investidor
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda

_seq = count(1)


def _next_id() -> int:
    return next(_seq)


def _documento() -> str:
    return f"{_next_id():011d}"


def _placa() -> str:
    return f"ABC{_next_id() % 10}D{_next_id() % 100:02d}"


class InvestidorCreateFactory(ModelFactory[investidor.InvestidorCreate]):
    __model__ = investidor.InvestidorCreate

    nome = Use(lambda: f"Investidor {_next_id()}")


class ClienteCreateFactory(ModelFactory[cliente.ClienteCreate]):
    __model__ = cliente.ClienteCreate

    nome = Use(lambda: f"Cliente {_next_id()}")
    documento = Use(_documento)
    tipo = cliente.TipoCliente.pessoa_fisica
    email = None
    telefone = None
    endereco = None
    cidade = None
    estado = None
    cep = None
    ativo = True


class VeiculoCreateFactory(ModelFactory[veiculo.VeiculoCreate]):
    __model__ = veiculo.VeiculoCreate

    tipo = veiculo.TipoVeiculo.carro
    modelo = "Gol"
    cor = "Branco"
    ano = 2018
    placa = Use(_placa)
    km = 50000
    preco = Decimal("40000.00")
    procuracao = None
    status = veiculo.StatusVeiculo.disponivel
    tipo_entrada = veiculo.TipoEntrada.compra
    revisao = False
    investidor_id = 1


class VendaCreateFactory(ModelFactory[venda.VendaCreate]):
    __model__ = venda.VendaCreate

    cliente_id = 1
    veiculo_id = 1
    vendedor_id = None
    data_venda = date(2026, 7, 1)
    valor_venda = Decimal("40000.00")
    valor_entrada = None
    debitos = None
    forma_pagamento = "a_vista"
    parcelas = 1
    status = venda.StatusVenda.pendente
    observacoes = None


class UsuarioCreateFactory(ModelFactory[usuario.UsuarioCreate]):
    __model__ = usuario.UsuarioCreate

    username = Use(lambda: f"user_{_next_id()}")
    senha = "senha"
    papel = usuario.Papel.vendedor
    perfil_id = None


class PerfilCreateFactory(ModelFactory[perfil.PerfilCreate]):
    __model__ = perfil.PerfilCreate

    nome = Use(lambda: f"Perfil {_next_id()}")
    paginas = Use(lambda: ["veiculos"])
