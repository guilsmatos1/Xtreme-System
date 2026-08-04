"""Venda: enum de status, model (com FKs), schemas e CRUD."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, Query, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.crud.search import apply_text_search
from xtreme_system.database.core import Base
from xtreme_system.documento_contrato_venda.core import DocumentoContratoVenda
from xtreme_system.imagem_comprovante_venda.core import ImagemComprovanteVenda
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import Veiculo, VeiculoRead
from xtreme_system.venda import status_veiculo

ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA = "valor_entrada não pode exceder valor_venda"
ERRO_PAGAMENTO_PENDENTE_VALOR_OBRIGATORIO = (
    "pagamento_pendente exige valor_pendente maior que zero"
)
ERRO_PAGAMENTO_PENDENTE_DATAS_OBRIGATORIAS = "pagamento_pendente exige datas_pagamento"
ERRO_PAGAMENTO_SEM_PENDENCIA_COM_VALOR = (
    "valor_pendente maior que zero exige pagamento_pendente"
)
ERRO_PAGAMENTO_SEM_PENDENCIA_COM_DATAS = "datas_pagamento exige pagamento_pendente"


class StatusVenda(StrEnum):
    pendente = "pendente"
    aprovado = "aprovado"
    cancelado = "cancelado"
    concluido = "concluido"


def _tem_texto(valor: str | None) -> bool:
    return bool(valor and valor.strip())


def validar_coerencia_pagamento(
    pagamento_pendente: bool,
    valor_pendente: Decimal | None,
    datas_pagamento: str | None,
) -> None:
    if pagamento_pendente:
        if valor_pendente is None or valor_pendente <= 0:
            raise ValueError(ERRO_PAGAMENTO_PENDENTE_VALOR_OBRIGATORIO)
        if not _tem_texto(datas_pagamento):
            raise ValueError(ERRO_PAGAMENTO_PENDENTE_DATAS_OBRIGATORIAS)
        return

    if valor_pendente is not None and valor_pendente > 0:
        raise ValueError(ERRO_PAGAMENTO_SEM_PENDENCIA_COM_VALOR)
    if _tem_texto(datas_pagamento):
        raise ValueError(ERRO_PAGAMENTO_SEM_PENDENCIA_COM_DATAS)


def validar_coerencia_valores(
    valor_venda: Decimal, valor_entrada: Decimal | None
) -> None:
    if valor_entrada is not None and valor_entrada > valor_venda:
        raise ValueError(ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA)


class Venda(Base):
    __tablename__ = "venda"
    __table_args__ = (
        CheckConstraint("valor_venda > 0", name="ck_venda_valor_venda_positive"),
        CheckConstraint(
            "valor_entrada IS NULL OR valor_entrada >= 0",
            name="ck_venda_valor_entrada_nonnegative",
        ),
        CheckConstraint(
            "valor_entrada IS NULL OR valor_entrada <= valor_venda",
            name="ck_venda_valor_entrada_lte_valor_venda",
        ),
        CheckConstraint(
            "debitos IS NULL OR debitos >= 0",
            name="ck_venda_debitos_nonnegative",
        ),
        CheckConstraint(
            "valor_diferenca IS NULL OR valor_diferenca >= 0",
            name="ck_venda_valor_diferenca_nonnegative",
        ),
        CheckConstraint(
            "valor_pendente IS NULL OR valor_pendente >= 0",
            name="ck_venda_valor_pendente_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculo.id"), index=True)
    vendedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), index=True
    )
    data_venda: Mapped[date | None] = mapped_column(Date, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valor_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_entrada: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    km: Mapped[int | None] = mapped_column()
    forma_pagamento: Mapped[str]
    parcelas: Mapped[int | None]
    status: Mapped[StatusVenda] = mapped_column(default=StatusVenda.pendente)
    observacoes: Mapped[str | None]
    veiculo_troca_id: Mapped[int | None] = mapped_column(
        ForeignKey("veiculo.id"), index=True
    )
    valor_diferenca: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pagamento_pendente: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    valor_pendente: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    datas_pagamento: Mapped[str | None]

    cliente: Mapped[Cliente] = relationship(lazy="selectin")
    veiculo: Mapped[Veiculo] = relationship(lazy="selectin", foreign_keys=[veiculo_id])
    veiculo_troca: Mapped[Veiculo | None] = relationship(
        lazy="selectin", foreign_keys=[veiculo_troca_id]
    )
    vendedor: Mapped[Usuario | None] = relationship(lazy="selectin")
    comprovantes: Mapped[list["ImagemComprovanteVenda"]] = relationship(
        cascade="all, delete-orphan"
    )
    contratos: Mapped[list["DocumentoContratoVenda"]] = relationship(
        cascade="all, delete-orphan"
    )


Index(
    "uq_venda_veiculo_concluida",
    Venda.veiculo_id,
    unique=True,
    postgresql_where=text("status = 'concluido'"),
    sqlite_where=text("status = 'concluido'"),
)


VENDA_NAO_CANCELADA = Venda.status != StatusVenda.cancelado


class VendaCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal = Field(gt=0)
    valor_entrada: Decimal | None = Field(default=None, ge=0)
    debitos: Decimal | None = Field(default=None, ge=0)
    km: int | None = Field(default=None, ge=0)
    forma_pagamento: str
    parcelas: int | None = Field(default=None, ge=1)
    status: StatusVenda = StatusVenda.pendente
    observacoes: str | None = None
    veiculo_troca_id: int | None = None
    valor_diferenca: Decimal | None = Field(default=None, ge=0)
    pagamento_pendente: bool = False
    valor_pendente: Decimal | None = Field(default=None, ge=0)
    datas_pagamento: str | None = None

    @model_validator(mode="after")
    def validar_valores(self) -> Self:
        validar_coerencia_valores(self.valor_venda, self.valor_entrada)
        validar_coerencia_pagamento(
            self.pagamento_pendente, self.valor_pendente, self.datas_pagamento
        )
        return self


class VendaUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    vendedor_id: int | None = None
    data_venda: date | None = None
    valor_venda: Decimal | None = Field(default=None, gt=0)
    valor_entrada: Decimal | None = Field(default=None, ge=0)
    debitos: Decimal | None = Field(default=None, ge=0)
    km: int | None = Field(default=None, ge=0)
    forma_pagamento: str | None = None
    parcelas: int | None = Field(default=None, ge=1)
    status: StatusVenda | None = None
    observacoes: str | None = None
    veiculo_troca_id: int | None = None
    valor_diferenca: Decimal | None = Field(default=None, ge=0)
    pagamento_pendente: bool = False
    valor_pendente: Decimal | None = Field(default=None, ge=0)
    datas_pagamento: str | None = None


def validate_valores_venda_update(venda_obj: Venda, data: VendaUpdate) -> None:
    valor_venda = (
        data.valor_venda if data.valor_venda is not None else venda_obj.valor_venda
    )
    valor_entrada = (
        data.valor_entrada
        if data.valor_entrada is not None
        else venda_obj.valor_entrada
    )
    validar_coerencia_valores(valor_venda, valor_entrada)
    pagamento_pendente = (
        data.pagamento_pendente
        if "pagamento_pendente" in data.model_fields_set
        else venda_obj.pagamento_pendente
    )
    valor_pendente = (
        data.valor_pendente
        if "valor_pendente" in data.model_fields_set
        else venda_obj.valor_pendente
    )
    datas_pagamento = (
        data.datas_pagamento
        if "datas_pagamento" in data.model_fields_set
        else venda_obj.datas_pagamento
    )
    validar_coerencia_pagamento(pagamento_pendente, valor_pendente, datas_pagamento)


class VendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    cliente: ClienteRead
    veiculo_id: int
    veiculo: VeiculoRead
    veiculo_troca: VeiculoRead | None
    vendedor: UsuarioRead | None
    data_venda: date | None
    criado_em: datetime
    valor_venda: Decimal
    valor_entrada: Decimal | None
    debitos: Decimal | None
    km: int | None
    forma_pagamento: str
    parcelas: int | None
    status: StatusVenda
    observacoes: str | None
    valor_diferenca: Decimal | None
    pagamento_pendente: bool
    valor_pendente: Decimal | None
    datas_pagamento: str | None


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Venda]:
    return crud.list_all(session, Venda, limit=limit, offset=offset)


def query(session: Session) -> Query[Venda]:
    return (
        session.query(Venda)
        .join(Cliente, Venda.cliente_id == Cliente.id)
        .join(Veiculo, Venda.veiculo_id == Veiculo.id)
        .outerjoin(Usuario, Venda.vendedor_id == Usuario.id)
    )


def get(session: Session, venda_id: int) -> Venda | None:
    return crud.get(session, Venda, venda_id)


def list_by_cliente(session: Session, cliente_id: int) -> list[Venda]:
    return list(session.query(Venda).filter_by(cliente_id=cliente_id).all())


def create(session: Session, data: VendaCreate, actor_id: int | None = None) -> Venda:
    obj = crud.create(session, Venda, data, actor_id)
    return status_veiculo.sincronizar_apos_escrita(session, obj)


def update(
    session: Session, obj: Venda, data: VendaUpdate, actor_id: int | None = None
) -> Venda:
    veiculo_anterior_id = obj.veiculo_id
    veiculo_troca_anterior_id = obj.veiculo_troca_id
    obj = crud.update(session, obj, data, actor_id)
    return status_veiculo.sincronizar_apos_escrita(
        session,
        obj,
        anterior_id=veiculo_anterior_id,
        troca_anterior_id=veiculo_troca_anterior_id,
    )


def delete(session: Session, obj: Venda, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def search(session: Session, term: str, column: str | None = None) -> list[Venda]:
    return list(search_query(session, term, column).all())


def search_query(
    session: Session, term: str, column: str | None = None
) -> Query[Venda]:
    sql_query = query(session)

    columns_map = {
        "cliente": Cliente.nome,
        "veiculo": Veiculo.modelo,
        "data": Venda.criado_em,
        "valor": Venda.valor_venda,
        "entrada": Venda.valor_entrada,
        "divida": Venda.valor_pendente,
        "pagamento": Venda.forma_pagamento,
        "parcelas": Venda.parcelas,
        "status": Venda.status,
        "vendedor": Usuario.nome,
    }

    return apply_text_search(
        sql_query,
        term,
        columns_map=columns_map,
        default_columns=(
            Cliente.nome,
            Cliente.documento,
            Veiculo.modelo,
            Veiculo.placa,
            Venda.status,
            Venda.observacoes,
        ),
        column=column,
    )
