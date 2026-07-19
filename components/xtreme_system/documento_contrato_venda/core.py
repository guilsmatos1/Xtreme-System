"""Documento de contrato de venda: model (FK venda), schemas e CRUD."""

from typing import TYPE_CHECKING

from fpdf import FPDF
from pydantic import BaseModel, ConfigDict
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, Session, mapped_column

from xtreme_system.crud import core as crud
from xtreme_system.database.core import Base

if TYPE_CHECKING:
    from xtreme_system.venda.core import Venda


class DocumentoContratoVenda(Base):
    __tablename__ = "documento_contrato_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str]


class DocumentoContratoVendaCreate(BaseModel):
    venda_id: int
    url: str


class DocumentoContratoVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda_id: int
    url: str


def list_all(session: Session) -> list[DocumentoContratoVenda]:
    return crud.list_all(session, DocumentoContratoVenda)


def list_by_venda(session: Session, venda_id: int) -> list[DocumentoContratoVenda]:
    return list(
        session.query(DocumentoContratoVenda).filter_by(venda_id=venda_id).all()
    )


def get(session: Session, documento_id: int) -> DocumentoContratoVenda | None:
    return crud.get(session, DocumentoContratoVenda, documento_id)


def create(
    session: Session,
    data: DocumentoContratoVendaCreate,
    actor_id: int | None = None,
) -> DocumentoContratoVenda:
    return crud.create(session, DocumentoContratoVenda, data, actor_id)


def delete(
    session: Session, obj: DocumentoContratoVenda, actor_id: int | None = None
) -> None:
    crud.delete(session, obj, actor_id)


def gerar_pdf(venda_obj: "Venda") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "CONTRATO DE VENDA", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    def _secao(titulo: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)

    def _linha(texto: str) -> None:
        pdf.multi_cell(0, 7, texto, new_x="LMARGIN", new_y="NEXT")

    _linha(f"Venda: #{venda_obj.id}")
    _linha(f"Data: {venda_obj.data_venda.isoformat() if venda_obj.data_venda else '-'}")

    _secao("Cliente")
    _linha(f"Nome: {venda_obj.cliente.nome}")
    _linha(f"CPF/CNPJ: {venda_obj.cliente.documento}")
    _linha(f"Telefone: {venda_obj.cliente.telefone or '-'}")
    _linha(f"Endereço: {venda_obj.cliente.endereco or '-'}")

    _secao("Veículo")
    _linha(f"Modelo: {venda_obj.veiculo.modelo}")
    _linha(f"Placa: {venda_obj.veiculo.placa}")
    _linha(f"KM: {venda_obj.km if venda_obj.km is not None else '-'}")

    _secao("Condições")
    _linha(f"Valor da venda: R$ {venda_obj.valor_venda:.2f}")
    _linha(
        f"Valor de entrada: R$ {venda_obj.valor_entrada:.2f}"
        if venda_obj.valor_entrada is not None
        else "Valor de entrada: -"
    )
    _linha(
        f"Débitos do veículo: R$ {venda_obj.debitos:.2f}"
        if venda_obj.debitos is not None
        else "Débitos do veículo: -"
    )
    if venda_obj.veiculo_troca is not None:
        troca = venda_obj.veiculo_troca
        _linha(f"Veículo da troca: {troca.modelo} ({troca.placa})")
    else:
        _linha("Veículo da troca: -")
    _linha(
        f"Valor da diferença: R$ {venda_obj.valor_diferenca:.2f}"
        if venda_obj.valor_diferenca is not None
        else "Valor da diferença: -"
    )
    pendente_txt = (
        f" - R$ {venda_obj.valor_pendente:.2f}"
        if venda_obj.valor_pendente is not None
        else ""
    )
    _linha(
        "Pagamento pendente: "
        f"{'Sim' if venda_obj.pagamento_pendente else 'Não'}{pendente_txt}"
    )
    _linha(f"Datas de pagamento: {venda_obj.datas_pagamento or '-'}")
    _linha(f"Forma de pagamento: {venda_obj.forma_pagamento}")
    _linha(f"Parcelas: {venda_obj.parcelas}")
    _linha(f"Observações: {venda_obj.observacoes or '-'}")

    return bytes(pdf.output())
