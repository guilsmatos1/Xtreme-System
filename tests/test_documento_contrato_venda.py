"""Geração de PDF do contrato de venda — isolada, sem HTTP/FastAPI."""

import re
import zlib
from datetime import date
from decimal import Decimal

from xtreme_system.cliente import core as cliente
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda


def _extract_pdf_text(data: bytes) -> str:
    """Decompõe streams FlateDecode do PDF e concatena como latin-1."""
    parts: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        try:
            parts.append(zlib.decompress(match.group(1)).decode("latin-1", "ignore"))
        except zlib.error:
            continue
    return "\n".join(parts)


def _build_cliente() -> cliente.Cliente:
    obj = cliente.Cliente()
    obj.id = 1
    obj.nome = "João Silva"
    obj.documento = "12345678901"
    obj.tipo = cliente.TipoCliente.pessoa_fisica
    obj.telefone = "(11) 99999-0000"
    obj.endereco = "Rua das Flores, 123"
    return obj


def _build_veiculo(modelo: str = "Gol", placa: str = "ABC1D23") -> veiculo.Veiculo:
    obj = veiculo.Veiculo()
    obj.id = 1
    obj.tipo = veiculo.TipoVeiculo.carro
    obj.modelo = modelo
    obj.cor = "Branco"
    obj.ano = 2018
    obj.placa = placa
    obj.km = 50000
    obj.preco = Decimal("40000.00")
    obj.investidor_id = 1
    return obj


def _build_venda(
    *,
    veiculo_troca: veiculo.Veiculo | None = None,
    valor_entrada: Decimal | None = Decimal("10000.00"),
    debitos: Decimal | None = Decimal("500.00"),
    km: int | None = 50000,
    valor_diferenca: Decimal | None = None,
    valor_pendente: Decimal | None = None,
    datas_pagamento: str | None = None,
    observacoes: str | None = "Observação de teste",
) -> venda.Venda:
    obj = venda.Venda()
    obj.id = 1
    obj.data_venda = date(2026, 7, 1)
    obj.valor_venda = Decimal("40000.00")
    obj.valor_entrada = valor_entrada
    obj.debitos = debitos
    obj.km = km
    obj.forma_pagamento = "a_vista"
    obj.parcelas = 1
    obj.status = venda.StatusVenda.pendente
    obj.observacoes = observacoes
    obj.veiculo_troca_id = 2 if veiculo_troca is not None else None
    obj.valor_diferenca = valor_diferenca
    obj.pagamento_pendente = False
    obj.valor_pendente = valor_pendente
    obj.datas_pagamento = datas_pagamento
    obj.cliente = _build_cliente()
    obj.veiculo = _build_veiculo()
    obj.veiculo_troca = veiculo_troca
    return obj


def test_gerar_pdf_retorna_pdf_valido() -> None:
    pdf = documento_contrato_venda.gerar_pdf(_build_venda())
    assert pdf.startswith(b"%PDF")


def test_gerar_pdf_campos_opcionais_nulos_nao_quebram() -> None:
    obj = _build_venda(
        valor_entrada=None,
        debitos=None,
        km=None,
        valor_diferenca=None,
        valor_pendente=None,
        datas_pagamento=None,
        observacoes=None,
        veiculo_troca=None,
    )
    pdf = documento_contrato_venda.gerar_pdf(obj)
    assert pdf.startswith(b"%PDF")


def test_gerar_pdf_renderiza_cliente_e_veiculo() -> None:
    texto = _extract_pdf_text(documento_contrato_venda.gerar_pdf(_build_venda()))
    assert "Silva" in texto
    assert "Gol" in texto
    assert "12345678901" in texto
    assert "ABC1D23" in texto


def test_gerar_pdf_renderiza_veiculo_troca() -> None:
    troca = _build_veiculo(modelo="Uno", placa="XYZ9W87")
    texto = _extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(veiculo_troca=troca))
    )
    assert "Uno" in texto
    assert "XYZ9W87" in texto
