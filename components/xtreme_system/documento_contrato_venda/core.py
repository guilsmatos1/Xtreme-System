"""Documento de contrato de venda: model (FK venda), schemas e CRUD."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey, event
from sqlalchemy.orm import Mapped, mapped_column

from xtreme_system.crud import attachment
from xtreme_system.database.core import Base
from xtreme_system.upload_file.core import schedule_uploaded_file_delete

if TYPE_CHECKING:
    from xtreme_system.cliente.core import Cliente
    from xtreme_system.empresa.core import EmpresaConfig
    from xtreme_system.venda.core import Venda


class DocumentoContratoVenda(Base):
    __tablename__ = "documento_contrato_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


@event.listens_for(DocumentoContratoVenda, "after_delete")
def _delete_upload_file(
    _mapper: object, _connection: object, target: DocumentoContratoVenda
) -> None:
    schedule_uploaded_file_delete(target)


class DocumentoContratoVendaCreate(BaseModel):
    venda_id: int
    url: str


class DocumentoContratoVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda_id: int
    url: str


list_all = attachment.make_list_all(DocumentoContratoVenda)
list_by_venda = attachment.make_list_by_field(DocumentoContratoVenda, "venda_id")
get = attachment.make_get(DocumentoContratoVenda)
create = attachment.make_create(DocumentoContratoVenda, DocumentoContratoVendaCreate)
delete = attachment.make_delete(DocumentoContratoVenda)


_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

_CONDICOES_GERAIS = (
    "O veículo acima é comprado no atual estado de conservação conforme foi examinado"
    " pelo comprador. A empresa garante ao comprador, o veículo acima descrito quanto a"
    " sua procedência e documentação, bem como ausência de débitos anteriores à data da"
    " venda (multas, IPVA e quaisquer ônus que incidam sobre o veículo).",
    "I-Caso o comprador não efetuar o pagamento tratado ou desistir do negócio, o mesmo"
    " perderá o direito ao sinal ora dado.",
    "II-O vendedor/Comprador declara para os devidos fins de direito que o veiculo"
    " acima citado é livre e desembaraçado de quaisquer ônus.",
    "III- É de total responsabilidade do Comprador o veiculo dado em troca , portanto"
    " fica integralmente responsável por multas, débitos, ,queixas de roubo ou furto.",
    "IV- Veiculo com garantia parcial de Motor e Câmbio por 90 dias ou 3.000Km ou o que"
    " ocorrer primeiro,",
    "* Estão excluídos da garantia tudo que se refere ao acabamento do veículo"
    " (estofamentos, forrações, pintura, para choques) bem como pneus, por seu estado"
    " de conservação ser de fácil constatação por leigo, e que o COMPRADOR concorda com"
    " o atual estado em que se encontram.",
    "* As peças que sofrem desgaste natural em função do uso deverão ser substituídas"
    " periodicamente, de acordo com as especificações do fabricante (embreagem,"
    " pastilhas de freio, velas de ignição, correias, amortecedores, etc). Tais custos"
    " serão suportados pelo comprador",
    "V- Em caso de problema mecânico o qual esta coberto na garantia, o comprador se"
    " compromete a trazer o veiculo à loja para solução do problema com mecânico"
    " conveniado com a loja.",
    "Para maior clareza as partes firmam a presente em duas vias de igual teor.",
)

_MARGEM = 15.0
_ALTURA_LINHA = 4.5
_LARGURA_LOGO = 26.0
_ALTURA_LOGO = 20.0
_ESPACO_ASSINATURA = 22.0
# "De acordo,"/data + espaço da rubrica + linhas + nomes + CNPJ.
_ALTURA_ASSINATURAS = 6 + _ALTURA_LINHA + _ESPACO_ASSINATURA + 8 + _ALTURA_LINHA * 2


def _moeda(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    inteiro, _, centavos = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def _data_extenso(dia: date) -> str:
    return f"{dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def _largura(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def _grid(pdf: FPDF, *celulas: tuple[str, float]) -> None:
    """Linha de colunas com quebra automática; larguras em fração da página útil."""
    x0, y0 = pdf.get_x(), pdf.get_y()
    total = _largura(pdf)
    alturas = []
    for texto, fracao in celulas:
        linhas = cast(
            "list[str]",
            pdf.multi_cell(
                total * fracao,
                _ALTURA_LINHA,
                texto,
                markdown=True,
                dry_run=True,
                output="LINES",
            ),
        )
        alturas.append(max(len(linhas), 1) * _ALTURA_LINHA)
    x = x0
    for texto, fracao in celulas:
        pdf.set_xy(x, y0)
        pdf.multi_cell(total * fracao, _ALTURA_LINHA, texto, markdown=True)
        x += total * fracao
    pdf.set_xy(x0, y0 + max(alturas))


def _regua(pdf: FPDF) -> None:
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)


def _cabecalho(
    pdf: FPDF, empresa_config: "EmpresaConfig", logo_path: Path | None
) -> None:
    pdf.set_font("Helvetica", "BU", 11)
    pdf.cell(0, 6, "Contrato de Venda", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Logo à esquerda, com o bloco de texto deslocado para a direita (como no modelo).
    y_logo = pdf.get_y()
    margem_original = pdf.l_margin
    if logo_path is not None:
        pdf.image(
            str(logo_path),
            x=pdf.l_margin,
            y=y_logo,
            w=_LARGURA_LOGO,
            h=_ALTURA_LOGO,
            keep_aspect_ratio=True,
        )
        pdf.set_left_margin(margem_original + _LARGURA_LOGO + 4)
        pdf.set_xy(pdf.l_margin, y_logo)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, empresa_config.nome, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    endereco = " - ".join(
        parte for parte in (empresa_config.endereco, empresa_config.bairro) if parte
    )
    pdf.cell(0, 4.5, endereco, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    cidade = f"{empresa_config.cidade}- {empresa_config.uf}"
    if empresa_config.cep:
        cidade += f" CEP: {empresa_config.cep}"
    pdf.cell(0, 4.5, cidade, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    contato = " - ".join(
        parte
        for parte in (
            empresa_config.telefone,
            f"CNPJ: {empresa_config.cnpj}" if empresa_config.cnpj else "",
        )
        if parte
    )
    pdf.cell(0, 4.5, contato, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if logo_path is not None:
        pdf.set_left_margin(margem_original)
        pdf.set_x(margem_original)
        # A régua nunca corta o logo, mesmo com poucos campos preenchidos.
        pdf.set_y(max(pdf.get_y(), y_logo + _ALTURA_LOGO))
    pdf.ln(1)
    _regua(pdf)
    pdf.ln(2)


def _bloco_comprador(pdf: FPDF, cliente_obj: "Cliente") -> None:
    pdf.set_font("Helvetica", "", 9)
    _grid(pdf, ("**Recebemos de:**", 0.28), (cliente_obj.nome, 0.72))
    _grid(
        pdf,
        (f"**CPF:** {cliente_obj.documento}", 0.34),
        ("**RG:**", 0.33),
        ("**CNH:**", 0.33),
    )
    _grid(
        pdf,
        (f"**Endereço:** {cliente_obj.endereco or ''}", 0.5),
        (f"**Bairro:** {cliente_obj.bairro or ''}", 0.5),
    )
    _grid(
        pdf,
        (f"**Cidade:** {cliente_obj.cidade or ''}", 0.34),
        (f"**Estado:** {cliente_obj.estado or ''}", 0.33),
        (f"**CEP:** {cliente_obj.cep or ''}", 0.33),
    )
    _grid(
        pdf,
        (f"**Telefone 1:** {cliente_obj.telefone or ''}", 0.34),
        ("**Telefone 2:**", 0.33),
        ("**Telefone 3:**", 0.33),
    )
    _grid(
        pdf,
        (f"**Contato:** {cliente_obj.telefone or ''}", 0.34),
        (f"**E-mail:** {cliente_obj.email or ''}", 0.66),
    )
    pdf.ln(4)


def _bloco_veiculo(pdf: FPDF, venda_obj: "Venda") -> None:
    veiculo_obj = venda_obj.veiculo
    _grid(
        pdf,
        (
            f"A importância de **{_moeda(venda_obj.valor_venda)}** como pagamento da"
            " venda do veículo:",
            0.6,
        ),
        (f"**Ano/Modelo: {veiculo_obj.ano}**", 0.4),
    )
    pdf.ln(2)
    _grid(
        pdf,
        (f"**Fabricante:** {veiculo_obj.marca or ''}", 0.34),
        (f"**Veículo:** {veiculo_obj.modelo}", 0.66),
    )
    _grid(
        pdf,
        (f"**Placa:** {veiculo_obj.placa}", 0.34),
        (f"**No. Chassi:** {veiculo_obj.chassi or ''}", 0.33),
        (f"**Cor:** {veiculo_obj.cor}", 0.33),
    )
    km = venda_obj.km if venda_obj.km is not None else veiculo_obj.km
    _grid(
        pdf,
        ("**No. Motor:**", 0.34),
        ("**Combustível:**", 0.33),
        (f"**Km:** {km if km is not None else ''}", 0.33),
    )
    _grid(
        pdf,
        (f"**Renavam:** {veiculo_obj.renavam or ''}", 0.34),
        ("**Opcionais:**", 0.66),
    )
    pdf.ln(4)


def _linhas_pagamento(venda_obj: "Venda") -> list[tuple[str, str, str]]:
    data_venda = (
        venda_obj.data_venda.strftime("%d/%m/%Y") if venda_obj.data_venda else ""
    )
    linhas: list[tuple[str, str, str]] = []
    if venda_obj.valor_entrada is not None:
        linhas.append((_moeda(venda_obj.valor_entrada), data_venda, "Entrada"))
    linhas.append(
        (_moeda(venda_obj.valor_venda), data_venda, venda_obj.forma_pagamento)
    )
    if venda_obj.pagamento_pendente and venda_obj.valor_pendente is not None:
        linhas.append(
            (
                _moeda(venda_obj.valor_pendente),
                venda_obj.datas_pagamento or "",
                "Pendente",
            )
        )
    return linhas


def _bloco_pagamento(pdf: FPDF, venda_obj: "Venda") -> None:
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(
        0,
        5,
        "Forma de Pagamento",
        align="C",
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    _grid(pdf, ("**Valor**", 0.3), ("**Data**", 0.3), ("**Descrição**", 0.4))
    _regua(pdf)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    for valor_txt, data_txt, descricao in _linhas_pagamento(venda_obj):
        _grid(pdf, (valor_txt, 0.3), (data_txt, 0.3), (descricao, 0.4))
    _regua(pdf)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "Documento", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, "Valor do Documento:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    consultor = venda_obj.vendedor.nome if venda_obj.vendedor is not None else ""
    pdf.cell(
        0,
        5,
        f"Consultor de Vendas: {consultor or ''}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)


def _condicoes_gerais(pdf: FPDF) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(
        0,
        6,
        "Condições Gerais do Contrato",
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 8.5)
    for paragrafo in _CONDICOES_GERAIS:
        pdf.multi_cell(0, 4, paragrafo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _assinaturas(
    pdf: FPDF, venda_obj: "Venda", empresa_config: "EmpresaConfig"
) -> None:
    # O bloco inteiro fica na mesma página; só quebra se de fato não couber.
    if pdf.get_y() + _ALTURA_ASSINATURAS > pdf.h - pdf.b_margin:
        pdf.add_page()
    else:
        pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    assinatura_data = venda_obj.data_venda or datetime.now(UTC).date()
    _grid(
        pdf,
        ("De acordo,", 0.5),
        (f"{empresa_config.cidade}, {_data_extenso(assinatura_data)}.", 0.5),
    )
    # Espaço em branco entre a data e a linha, para a assinatura manuscrita.
    pdf.ln(_ESPACO_ASSINATURA)
    meio = _largura(pdf) / 2
    y = pdf.get_y()
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin + 5, y, pdf.l_margin + meio - 10, y)
    pdf.line(pdf.l_margin + meio, y, pdf.w - pdf.r_margin, y)
    pdf.set_line_width(0.2)
    pdf.ln(4)
    _regua(pdf)
    pdf.ln(4)
    _grid(
        pdf,
        (f"    {venda_obj.cliente.nome}", 0.5),
        (f"{empresa_config.signatario or empresa_config.nome}", 0.5),
    )
    if empresa_config.cnpj:
        _grid(pdf, ("", 0.5), (f"CNPJ: {empresa_config.cnpj}", 0.5))


def gerar_pdf(
    venda_obj: "Venda",
    empresa_config: "EmpresaConfig",
    logo_path: Path | None = None,
) -> bytes:
    """Gera o contrato de venda no layout do modelo em `docs/contrato_modelo.pdf`."""
    pdf = FPDF()
    pdf.set_margins(_MARGEM, 12, _MARGEM)
    pdf.set_auto_page_break(True, margin=12)
    pdf.add_page()

    _cabecalho(pdf, empresa_config, logo_path)
    _bloco_comprador(pdf, venda_obj.cliente)
    _bloco_veiculo(pdf, venda_obj)
    _bloco_pagamento(pdf, venda_obj)
    _condicoes_gerais(pdf)
    _assinaturas(pdf, venda_obj, empresa_config)

    return bytes(pdf.output())
