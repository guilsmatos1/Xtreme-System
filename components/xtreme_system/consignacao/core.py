"""Consignacao: model (com FKs para cliente e veiculo), schemas e CRUD."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, Query, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.crud.search import apply_text_search
from xtreme_system.database.core import Base
from xtreme_system.imagem_contrato_consignacao.core import ImagemContratoConsignacao
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import Veiculo, VeiculoRead


class StatusConsignacao(StrEnum):
    ativa = "ativa"
    vendida = "vendida"
    devolvida = "devolvida"
    cancelada = "cancelada"


class Consignacao(Base):
    __tablename__ = "consignacao"
    __table_args__ = (
        CheckConstraint("valor_venda > 0", name="ck_consignacao_valor_venda_positive"),
        CheckConstraint(
            "comissao_percentual IS NULL OR "
            "(comissao_percentual >= 0 AND comissao_percentual <= 100)",
            name="ck_consignacao_comissao_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("cliente.id", ondelete="RESTRICT"), index=True
    )
    veiculo_id: Mapped[int] = mapped_column(
        ForeignKey("veiculo.id", ondelete="RESTRICT"), index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id", ondelete="SET NULL"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True
    )
    data_consignacao: Mapped[date] = mapped_column(Date)
    data_vencimento: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valor_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    comissao_percentual: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    observacoes: Mapped[str | None]
    status: Mapped[StatusConsignacao] = mapped_column(
        default=StatusConsignacao.ativa,
        server_default="ativa",
    )

    cliente: Mapped[Cliente] = relationship(lazy="selectin")
    veiculo: Mapped[Veiculo] = relationship(lazy="selectin")
    usuario: Mapped[Usuario | None] = relationship(lazy="selectin")
    contratos: Mapped[list["ImagemContratoConsignacao"]] = relationship(
        cascade="all, delete-orphan"
    )


class ConsignacaoCreate(BaseModel):
    cliente_id: int
    veiculo_id: int
    usuario_id: int | None = None
    idempotency_key: str | None = None
    data_consignacao: date = Field(default_factory=date.today)
    data_vencimento: date | None = None
    valor_venda: Decimal = Field(gt=0)
    comissao_percentual: Decimal | None = Field(default=None, ge=0, le=100)
    observacoes: str | None = None
    status: StatusConsignacao = StatusConsignacao.ativa

    @field_validator("valor_venda", "comissao_percentual", mode="before")
    @classmethod
    def _normalizar_valores(cls, value: object) -> object:
        _ = cls
        return crud.parse_decimal_br(value)


class ConsignacaoUpdate(BaseModel):
    cliente_id: int | None = None
    veiculo_id: int | None = None
    data_consignacao: date | None = None
    data_vencimento: date | None = None
    valor_venda: Decimal | None = Field(default=None, gt=0)
    comissao_percentual: Decimal | None = Field(default=None, ge=0, le=100)
    observacoes: str | None = None
    status: StatusConsignacao | None = None

    @field_validator("valor_venda", "comissao_percentual", mode="before")
    @classmethod
    def _normalizar_valores(cls, value: object) -> object:
        _ = cls
        return crud.parse_decimal_br(value)


class ConsignacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: ClienteRead
    veiculo: VeiculoRead
    usuario: UsuarioRead | None
    data_consignacao: date
    data_vencimento: date | None
    criado_em: datetime
    valor_venda: Decimal
    comissao_percentual: Decimal | None
    observacoes: str | None
    status: StatusConsignacao


# ---- CRUD ----


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Consignacao]:
    return crud.list_all(session, Consignacao, limit=limit, offset=offset)


def query(session: Session) -> Query[Consignacao]:
    return (
        session.query(Consignacao)
        .join(Cliente, Consignacao.cliente_id == Cliente.id)
        .join(Veiculo, Consignacao.veiculo_id == Veiculo.id)
        .outerjoin(Usuario, Consignacao.usuario_id == Usuario.id)
    )


def get(session: Session, consignacao_id: int) -> Consignacao | None:
    return crud.get(session, Consignacao, consignacao_id)


def get_by_idempotency_key(session: Session, key: str) -> Consignacao | None:
    return session.query(Consignacao).filter_by(idempotency_key=key).one_or_none()


def list_by_cliente(session: Session, cliente_id: int) -> list[Consignacao]:
    return list(session.query(Consignacao).filter_by(cliente_id=cliente_id).all())


def create(
    session: Session, data: ConsignacaoCreate, actor_id: int | None = None
) -> Consignacao:
    return crud.create(session, Consignacao, data, actor_id)


def update(
    session: Session,
    obj: Consignacao,
    data: ConsignacaoUpdate,
    actor_id: int | None = None,
) -> Consignacao:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Consignacao, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def search(session: Session, term: str, column: str | None = None) -> list[Consignacao]:
    return list(search_query(session, term, column).all())


def search_query(
    session: Session, term: str, column: str | None = None
) -> Query[Consignacao]:
    sql_query = query(session)

    columns_map = {
        "proprietario": Cliente.nome,
        "documento": Cliente.documento,
        "modelo": Veiculo.modelo,
        "placa": Veiculo.placa,
        "data": Consignacao.criado_em,
        "valor": Consignacao.valor_venda,
        "status": Consignacao.status,
        "observacoes": Consignacao.observacoes,
        "usuario": Usuario.nome,
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
            Consignacao.observacoes,
        ),
        column=column,
    )
