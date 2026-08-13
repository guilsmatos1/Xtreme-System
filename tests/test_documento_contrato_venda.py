"""Geração de PDF do contrato de venda — isolada, sem HTTP/FastAPI."""

import re
import zlib
from datetime import date
from decimal import Decimal
from pathlib import Path

from PIL import Image

from xtreme_system.cliente import core as cliente
from xtreme_system.documento_contrato_venda import core as documento_contrato_venda
from xtreme_system.empresa import core as empresa
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda


def extract_pdf_text(data: bytes) -> str:
    """Decompõe streams FlateDecode do PDF e concatena como latin-1."""
    parts: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        try:
            parts.append(zlib.decompress(match.group(1)).decode("latin-1", "ignore"))
        except zlib.error:
            continue
    return "\n".join(parts)


def _build_empresa() -> empresa.EmpresaConfig:
    obj = empresa.EmpresaConfig()
    obj.id = 1
    obj.nome = "XTREME MOTORS"
    obj.endereco = "Avenida do Cursino, 3247"
    obj.bairro = "Vila da Saude"
    obj.cidade = "Sao Paulo"
    obj.uf = "SP"
    obj.cep = "04133-300"
    obj.telefone = "(11)99135-2467"
    obj.cnpj = "44.237.309.0001-75"
    obj.signatario = "XTREME MOTORS"
    return obj


def _build_cliente() -> cliente.Cliente:
    obj = cliente.Cliente()
    obj.id = 1
    obj.nome = "João Silva"
    obj.documento = "12345678901"
    obj.tipo = cliente.TipoCliente.pessoa_fisica
    obj.telefone = "(11) 99999-0000"
    obj.endereco = "Rua das Flores, 123"
    obj.bairro = "Jardim Paulista"
    obj.cep = "01310-100"
    return obj


def _build_veiculo(modelo: str = "Gol", placa: str = "ABC1D23") -> veiculo.Veiculo:
    obj = veiculo.Veiculo()
    obj.id = 1
    obj.tipo = veiculo.TipoVeiculo.carro
    obj.modelo = modelo
    obj.marca = "Volkswagen"
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
    pdf = documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
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
    pdf = documento_contrato_venda.gerar_pdf(obj, _build_empresa())
    assert pdf.startswith(b"%PDF")


def test_gerar_pdf_renderiza_cliente_e_veiculo() -> None:
    texto = extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    )
    assert "Silva" in texto
    assert "Gol" in texto
    assert "Volkswagen" in texto
    assert "123.456.789-01" in texto
    assert "Documento: 123.456.789-01" in texto
    assert "ABC1D23" in texto
    assert "Bairro:" in texto
    assert "Jardim Paulista" in texto
    assert "99999-0000" in texto  # parênteses saem escapados no stream do PDF
    assert "01310-100" in texto


def test_gerar_pdf_renderiza_cabecalho_da_empresa() -> None:
    texto = extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    )
    assert "Contrato de Venda" in texto
    assert "XTREME MOTORS" in texto
    assert "Avenida do Cursino, 3247 - Vila da Saude" in texto
    assert "04133-300" in texto
    assert "99135-2467" in texto  # parênteses saem escapados no stream do PDF
    assert "44.237.309.0001-75" in texto


def test_gerar_pdf_assinaturas_na_mesma_pagina() -> None:
    pdf = documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    assert pdf.count(b"/Type /Page\n") == 1
    assert "De acordo," in extract_pdf_text(pdf)


def test_gerar_pdf_cpf_do_cliente_abaixo_da_assinatura() -> None:
    texto = extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    )
    assert "CPF: 123.456.789-01" in texto


def test_gerar_pdf_segue_secoes_do_modelo() -> None:
    texto = extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    )
    for rotulo in (
        "Recebemos de:",
        "Telefone 2:",
        "No. Chassi:",
        "Opcionais:",
        "Forma de Pagamento",
        "Valor do Documento:",
        "Consultor de Vendas:",
        "Gerais do Contrato",
        "De acordo,",
    ):
        assert rotulo in texto
    assert "RG:" not in texto
    assert "CNH:" not in texto


def test_gerar_pdf_com_logo_mantem_cabecalho(tmp_path: Path) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGB", (120, 60), "black").save(logo)
    pdf = documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa(), logo)
    assert pdf.startswith(b"%PDF")
    texto = extract_pdf_text(pdf)
    assert "XTREME MOTORS" in texto
    assert "Recebemos de:" in texto


def test_gerar_pdf_formata_valor_em_reais() -> None:
    texto = extract_pdf_text(
        documento_contrato_venda.gerar_pdf(_build_venda(), _build_empresa())
    )
    assert "R$ 40.000,00" in texto
