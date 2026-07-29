"""Venda: enum de status, model (com FKs), schemas e CRUD."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    extract,
    false,
    func,
)
from sqlalchemy.orm import Mapped, Query, Session, mapped_column, relationship

from xtreme_system.cliente.core import Cliente, ClienteRead
from xtreme_system.crud import core as crud
from xtreme_system.crud.search import apply_text_search
from xtreme_system.database.core import Base
from xtreme_system.documento_contrato_venda.core import DocumentoContratoVenda
from xtreme_system.imagem_comprovante_venda.core import ImagemComprovanteVenda
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import StatusVeiculo, TipoVeiculo, Veiculo, VeiculoRead

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


class Venda(Base):
    __tablename__ = "venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), index=True)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculo.id"), index=True)
    vendedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), index=True
    )
    data_venda: Mapped[date | None] = mapped_column(Date)
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
        if self.valor_entrada is not None and self.valor_entrada > self.valor_venda:
            raise ValueError(ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA)
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

    @model_validator(mode="after")
    def validar_valores(self) -> Self:
        if (
            self.valor_venda is not None
            and self.valor_entrada is not None
            and self.valor_entrada > self.valor_venda
        ):
            raise ValueError(ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA)
        if "pagamento_pendente" in self.model_fields_set:
            validar_coerencia_pagamento(
                self.pagamento_pendente, self.valor_pendente, self.datas_pagamento
            )
        return self


def validate_valores_venda_update(venda_obj: Venda, data: VendaUpdate) -> None:
    valor_venda = (
        data.valor_venda if data.valor_venda is not None else venda_obj.valor_venda
    )
    valor_entrada = (
        data.valor_entrada
        if data.valor_entrada is not None
        else venda_obj.valor_entrada
    )
    if valor_entrada is not None and valor_entrada > valor_venda:
        raise ValueError(ERRO_VALOR_ENTRADA_MAIOR_QUE_VALOR_VENDA)
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
    cliente: ClienteRead
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


def veiculo_tem_outra_venda_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(Venda).filter(
        Venda.veiculo_id == veiculo_id,
        Venda.status == StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def veiculo_tem_outra_venda_pendente(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(Venda).filter(
        Venda.veiculo_id == veiculo_id,
        Venda.status == StatusVenda.pendente,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def veiculo_tem_outra_troca_concluida(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> bool:
    sql_query = session.query(Venda).filter(
        Venda.veiculo_troca_id == veiculo_id,
        Venda.status == StatusVenda.concluido,
    )
    if excluir_venda_id is not None:
        sql_query = sql_query.filter(Venda.id != excluir_venda_id)
    return sql_query.first() is not None


def recomputar_status_veiculo_por_vendas(
    session: Session, veiculo_id: int, *, excluir_venda_id: int | None = None
) -> None:
    v = session.get(Veiculo, veiculo_id)
    if v is None or v.status == StatusVeiculo.indisponivel:
        return
    if veiculo_tem_outra_troca_concluida(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.disponivel
    elif veiculo_tem_outra_venda_concluida(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.vendido
    elif veiculo_tem_outra_venda_pendente(
        session, veiculo_id, excluir_venda_id=excluir_venda_id
    ):
        v.status = StatusVeiculo.reservado
    else:
        v.status = StatusVeiculo.disponivel


def _sincronizar_status_veiculo(
    session: Session,
    obj: Venda,
    *,
    veiculo_anterior_id: int | None = None,
    veiculo_troca_anterior_id: int | None = None,
) -> Venda:
    """Recomputa o status dos veículos ligados a `obj` a partir do estado
    já persistido das vendas (prioridade: vendido > reservado > disponivel),
    preservando `indisponivel` como override manual não pisado pela sync."""
    if veiculo_anterior_id is not None and veiculo_anterior_id != obj.veiculo_id:
        recomputar_status_veiculo_por_vendas(
            session, veiculo_anterior_id, excluir_venda_id=obj.id
        )
    recomputar_status_veiculo_por_vendas(session, obj.veiculo_id)
    if (
        veiculo_troca_anterior_id is not None
        and veiculo_troca_anterior_id != obj.veiculo_troca_id
    ):
        recomputar_status_veiculo_por_vendas(
            session, veiculo_troca_anterior_id, excluir_venda_id=obj.id
        )
    if obj.veiculo_troca_id is not None:
        recomputar_status_veiculo_por_vendas(session, obj.veiculo_troca_id)
    crud.flush(session)
    session.refresh(obj)
    return obj


def create(session: Session, data: VendaCreate, actor_id: int | None = None) -> Venda:
    obj = crud.create(session, Venda, data, actor_id)
    return _sincronizar_status_veiculo(session, obj)


def update(
    session: Session, obj: Venda, data: VendaUpdate, actor_id: int | None = None
) -> Venda:
    validate_valores_venda_update(obj, data)
    veiculo_anterior_id = obj.veiculo_id
    veiculo_troca_anterior_id = obj.veiculo_troca_id
    obj = crud.update(session, obj, data, actor_id)
    return _sincronizar_status_veiculo(
        session,
        obj,
        veiculo_anterior_id=veiculo_anterior_id,
        veiculo_troca_anterior_id=veiculo_troca_anterior_id,
    )


def delete(session: Session, obj: Venda, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def search(session: Session, term: str, column: str | None = None) -> list[Venda]:
    return list(search_query(session, term, column).all())


def search_query(
    session: Session, term: str, column: str | None = None
) -> Query[Venda]:
    sql_query = (
        session.query(Venda)
        .join(Cliente, Venda.cliente_id == Cliente.id)
        .join(Veiculo, Venda.veiculo_id == Veiculo.id)
        .outerjoin(Usuario, Venda.vendedor_id == Usuario.id)
    )

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


def _mes_atual_inicio() -> date:
    hoje = datetime.now(UTC).date()
    return hoje.replace(day=1)


def resumo_mes(session: Session) -> tuple[int, Decimal]:
    """Retorna (contagem, soma) de vendas do mês atual com status != cancelado."""
    resultado = (
        session.query(func.count(Venda.id), func.sum(Venda.valor_venda))
        .filter(Venda.data_venda >= _mes_atual_inicio())
        .filter(Venda.status != StatusVenda.cancelado)
        .all()
    )
    count, total = resultado[0] if resultado else (0, None)
    return count or 0, total or Decimal("0")


def ticket_medio(session: Session) -> Decimal:
    """Retorna valor médio de venda com status != cancelado."""
    valor = (
        session.query(func.avg(Venda.valor_venda))
        .filter(Venda.status != StatusVenda.cancelado)
        .scalar()
    )
    return valor or Decimal("0")


def receita_por_tipo(session: Session) -> dict[TipoVeiculo, Decimal]:
    """Retorna soma de valor_venda agrupada por tipo de veículo, sem cancelados."""
    rows = (
        session.query(Veiculo.tipo, func.sum(Venda.valor_venda))
        .join(Venda, Venda.veiculo_id == Veiculo.id)
        .filter(Venda.status != StatusVenda.cancelado)
        .group_by(Veiculo.tipo)
        .all()
    )
    return {tipo: total or Decimal("0") for tipo, total in rows}


def funil_status(session: Session) -> dict[StatusVenda, tuple[int, Decimal]]:
    """Retorna (contagem, soma) de vendas por status (incluindo cancelado)."""
    rows = (
        session.query(Venda.status, func.count(Venda.id), func.sum(Venda.valor_venda))
        .group_by(Venda.status)
        .all()
    )
    return {
        status: (count or 0, total or Decimal("0")) for status, count, total in rows
    }


def ranking_vendedores(
    session: Session, limite: int = 5
) -> list[tuple[Usuario, int, Decimal]]:
    """Retorna top N vendedores por valor vendido (status != cancelado).

    Retorna: (usuario, count, total_valor)
    """
    rows = (
        session.query(
            Usuario,
            func.count(Venda.id).label("count_vendas"),
            func.sum(Venda.valor_venda).label("total_valor"),
        )
        .join(Venda, Venda.vendedor_id == Usuario.id)
        .filter(Venda.status != StatusVenda.cancelado)
        .group_by(Usuario.id)
        .order_by(func.sum(Venda.valor_venda).desc(), Usuario.id.asc())
        .limit(limite)
        .all()
    )
    return [
        (usuario, count or 0, total or Decimal("0")) for usuario, count, total in rows
    ]


def tendencia_por_periodo(
    session: Session, periodo: str
) -> list[tuple[str, int, Decimal]]:
    """Retorna vendas agregadas por semana (30d/90d) ou mês (12m)."""
    hoje = datetime.now(UTC).date()
    if periodo == "12m":
        mes_inicial = hoje.month - 11
        ano_inicial = hoje.year
        if mes_inicial <= 0:
            mes_inicial += 12
            ano_inicial -= 1
        inicio = date(ano_inicial, mes_inicial, 1)
        granularidade = "mes"
    elif periodo == "90d":
        inicio = hoje - timedelta(days=89)
        granularidade = "semana"
    else:
        inicio = hoje - timedelta(days=29)
        granularidade = "semana"

    base = (
        session.query(Venda)
        .filter(Venda.data_venda >= inicio)
        .filter(Venda.data_venda.isnot(None))
        .filter(Venda.status != StatusVenda.cancelado)
    )

    if granularidade == "mes":
        ano_expr = extract("year", Venda.data_venda)
        mes_expr = extract("month", Venda.data_venda)
        rows = (
            base.with_entities(
                ano_expr.label("ano"),
                mes_expr.label("mes"),
                func.count(Venda.id).label("count"),
                func.sum(Venda.valor_venda).label("total"),
            )
            .group_by(ano_expr, mes_expr)
            .order_by(ano_expr, mes_expr)
            .all()
        )
        return [
            (f"{ano:04d}-{mes:02d}", count or 0, total or Decimal("0"))
            for ano, mes, count, total in rows
        ]

    ano_expr = extract("year", Venda.data_venda)
    mes_expr = extract("month", Venda.data_venda)
    dia_expr = extract("day", Venda.data_venda)
    dia_rows = (
        base.with_entities(
            ano_expr.label("ano"),
            mes_expr.label("mes"),
            dia_expr.label("dia"),
            func.count(Venda.id).label("count"),
            func.sum(Venda.valor_venda).label("total"),
        )
        .group_by(ano_expr, mes_expr, dia_expr)
        .order_by(ano_expr, mes_expr, dia_expr)
        .all()
    )

    grupos: dict[str, tuple[int, Decimal]] = {}
    for ano, mes, dia, count, total in dia_rows:
        data_venda = date(ano, mes, dia)
        iso_ano, iso_semana, _ = data_venda.isocalendar()
        chave = f"{iso_ano:04d}-S{iso_semana:02d}"
        prev_count, prev_total = grupos.get(chave, (0, Decimal("0")))
        grupos[chave] = prev_count + count, prev_total + total

    return [(chave, count, total) for chave, (count, total) in grupos.items()]


MESES_ABREV = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
]


def desempenho_vendas_mensal(
    session: Session, meses: int = 6
) -> list[tuple[str, int, Decimal]]:
    """Retorna (label, count, total) dos últimos N meses, incluindo meses sem vendas."""
    hoje = datetime.now(UTC).date()
    mes_inicial = hoje.month - (meses - 1)
    ano_inicial = hoje.year
    while mes_inicial <= 0:
        mes_inicial += 12
        ano_inicial -= 1
    inicio = date(ano_inicial, mes_inicial, 1)

    ano_expr = extract("year", Venda.data_venda)
    mes_expr = extract("month", Venda.data_venda)
    rows = (
        session.query(
            ano_expr.label("ano"),
            mes_expr.label("mes"),
            func.count(Venda.id).label("count"),
            func.sum(Venda.valor_venda).label("total"),
        )
        .filter(Venda.data_venda >= inicio)
        .filter(Venda.data_venda.isnot(None))
        .filter(Venda.status != StatusVenda.cancelado)
        .group_by(ano_expr, mes_expr)
        .all()
    )
    por_chave = {
        (int(ano), int(mes)): (count or 0, total or Decimal("0"))
        for ano, mes, count, total in rows
    }

    resultado: list[tuple[str, int, Decimal]] = []
    ano, mes = ano_inicial, mes_inicial
    for _ in range(meses):
        count, total = por_chave.get((ano, mes), (0, Decimal("0")))
        resultado.append((f"{MESES_ABREV[mes - 1]}/{ano % 100:02d}", count, total))
        mes += 1
        if mes > len(MESES_ABREV):
            mes = 1
            ano += 1
    return resultado
