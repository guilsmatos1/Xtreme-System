"""Fechamento financeiro de vendas: cálculo, participações e lançamentos."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint, func, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from xtreme_system.auditoria.core import _snapshot, auditar
from xtreme_system.caixa import core as caixa
from xtreme_system.crud import core as crud
from xtreme_system.custo_veiculo.core import CustoVeiculo
from xtreme_system.database.core import Base
from xtreme_system.investidor.core import Investidor, InvestidorRead
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.venda.core import StatusVenda, Venda, VendaRead

CENTAVO = Decimal("0.01")
PERCENTUAL_TOTAL = Decimal("100")
ERRO_SEM_DISTRIBUICAO = "Venda sem lucro positivo não aceita distribuição"
ERRO_RATEIO_OBRIGATORIO = "Informe o rateio do lucro"
ERRO_INVESTIDOR_DUPLICADO = "Investidor duplicado no rateio"
ERRO_INVESTIDOR_INEXISTENTE = "investidor_id inexistente no rateio"
ERRO_RATEIO_TOTAL = "Rateio deve somar 100%"
ERRO_SCHEMA_DESATUALIZADO = (
    "Atualize o banco com `make migrate` para usar fechamento de vendas"
)


class FechamentoVendaError(ValueError):
    pass


class FechamentoVenda(Base):
    __tablename__ = "fechamento_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    venda_id: Mapped[int] = mapped_column(
        ForeignKey("venda.id", ondelete="CASCADE"), unique=True, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    data_fechamento: Mapped[date] = mapped_column(
        Date, server_default=func.current_date()
    )
    receita: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custo_veiculo: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custos_operacionais: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    lucro_liquido: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    venda: Mapped[Venda] = relationship(lazy="joined")
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")
    participacoes: Mapped[list["ParticipacaoFechamentoVenda"]] = relationship(
        back_populates="fechamento",
        cascade="all, delete-orphan",
        lazy="joined",
    )


class ParticipacaoFechamentoVenda(Base):
    __tablename__ = "participacao_fechamento_venda"
    __table_args__ = (
        UniqueConstraint(
            "fechamento_venda_id",
            "investidor_id",
            name="uq_participacao_fechamento_investidor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fechamento_venda_id: Mapped[int] = mapped_column(
        ForeignKey("fechamento_venda.id", ondelete="CASCADE"), index=True
    )
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)
    percentual: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    fechamento: Mapped[FechamentoVenda] = relationship(back_populates="participacoes")
    investidor: Mapped[Investidor] = relationship(lazy="joined")


class ParticipacaoFechamentoVendaCreate(BaseModel):
    investidor_id: int
    percentual: Decimal = Field(gt=0, le=100)


class FechamentoVendaCreate(BaseModel):
    participacoes: list[ParticipacaoFechamentoVendaCreate] = Field(default_factory=list)


class ParticipacaoFechamentoVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investidor: InvestidorRead
    percentual: Decimal
    valor: Decimal


class FechamentoVendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venda: VendaRead
    usuario: UsuarioRead | None
    data_fechamento: date
    receita: Decimal
    custo_veiculo: Decimal
    custos_operacionais: Decimal
    debitos: Decimal
    lucro_liquido: Decimal
    participacoes: list[ParticipacaoFechamentoVendaRead]


class FechamentoVendaPreview(BaseModel):
    elegivel: bool
    motivo: str | None
    ja_fechada: bool
    receita: Decimal
    custo_veiculo: Decimal
    custos_operacionais: Decimal
    debitos: Decimal
    lucro_liquido: Decimal
    investidores: list[InvestidorRead]


def _schema_disponivel(session: Session) -> bool:
    # Inspeciona a conexão ativa da sessão (não o engine): inspecionar o engine
    # abriria uma conexão própria cujo rollback descarta escritas ainda não
    # commitadas da sessão (flush sem commit).
    inspector = inspect(session.connection())
    return inspector.has_table(FechamentoVenda.__tablename__) and inspector.has_table(
        ParticipacaoFechamentoVenda.__tablename__
    )


def list_all(session: Session) -> list[FechamentoVenda]:
    if not _schema_disponivel(session):
        return []
    return list(session.query(FechamentoVenda).order_by(FechamentoVenda.id).all())


def get(session: Session, fechamento_id: int) -> FechamentoVenda | None:
    if not _schema_disponivel(session):
        return None
    return crud.get(session, FechamentoVenda, fechamento_id)


def get_by_venda(session: Session, venda_id: int) -> FechamentoVenda | None:
    if not _schema_disponivel(session):
        return None
    return session.query(FechamentoVenda).filter_by(venda_id=venda_id).one_or_none()


def preview(session: Session, venda_obj: Venda) -> FechamentoVendaPreview:
    receita, custo_veiculo, custos_operacionais, debitos, lucro = _calcular(
        session, venda_obj
    )
    motivo = _motivo_inelegivel(session, venda_obj)
    investidores = list(session.query(Investidor).order_by(Investidor.nome).all())
    return FechamentoVendaPreview(
        elegivel=motivo is None,
        motivo=motivo,
        ja_fechada=get_by_venda(session, venda_obj.id) is not None,
        receita=receita,
        custo_veiculo=custo_veiculo,
        custos_operacionais=custos_operacionais,
        debitos=debitos,
        lucro_liquido=lucro,
        investidores=investidores,
    )


def confirmar(
    session: Session,
    venda_obj: Venda,
    data: FechamentoVendaCreate,
    *,
    usuario_id: int | None,
) -> FechamentoVenda:
    if not _schema_disponivel(session):
        raise FechamentoVendaError(ERRO_SCHEMA_DESATUALIZADO)
    receita, custo_veiculo, custos_operacionais, debitos, lucro = _calcular(
        session, venda_obj
    )
    _validar_elegibilidade(session, venda_obj)
    _validar_participacoes(session, data.participacoes, lucro)

    fechamento = FechamentoVenda(
        venda_id=venda_obj.id,
        usuario_id=usuario_id,
        receita=receita,
        custo_veiculo=custo_veiculo,
        custos_operacionais=custos_operacionais,
        debitos=debitos,
        lucro_liquido=lucro,
    )
    session.add(fechamento)
    session.flush()
    session.refresh(fechamento)
    auditar(
        session,
        tabela="fechamento_venda",
        tipo_acao="CREATE",
        registro_id=fechamento.id,
        dados_depois=_snapshot(fechamento),
    )

    caixa.criar_lancamento_fechamento(
        session,
        investidor_id=venda_obj.veiculo.investidor_id,
        fechamento_venda_id=fechamento.id,
        tipo=caixa.TipoLancamento.receita_venda,
        valor=receita,
        descricao=f"Receita da venda #{venda_obj.id}",
    )
    if lucro > 0:
        for item in data.participacoes:
            valor = _quantizar(lucro * item.percentual / PERCENTUAL_TOTAL)
            participacao = ParticipacaoFechamentoVenda(
                fechamento_venda_id=fechamento.id,
                investidor_id=item.investidor_id,
                percentual=_quantizar(item.percentual),
                valor=valor,
            )
            session.add(participacao)
            session.flush()
            auditar(
                session,
                tabela="participacao_fechamento_venda",
                tipo_acao="CREATE",
                registro_id=participacao.id,
                dados_depois=_snapshot(participacao),
            )
            caixa.criar_lancamento_fechamento(
                session,
                investidor_id=item.investidor_id,
                fechamento_venda_id=fechamento.id,
                tipo=caixa.TipoLancamento.distribuicao_lucro,
                valor=valor,
                descricao=f"Distribuição de lucro da venda #{venda_obj.id}",
            )
    crud.flush(session)
    session.refresh(fechamento)
    return fechamento


def _calcular(
    session: Session, venda_obj: Venda
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    receita = _quantizar(venda_obj.valor_venda)
    custo_veiculo = _quantizar(venda_obj.veiculo.preco)
    custos_operacionais = _quantizar(
        session.query(func.sum(CustoVeiculo.valor))
        .filter_by(veiculo_id=venda_obj.veiculo_id)
        .scalar()
        or Decimal("0")
    )
    debitos = _quantizar(venda_obj.debitos or Decimal("0"))
    lucro = _quantizar(receita - custo_veiculo - custos_operacionais - debitos)
    return receita, custo_veiculo, custos_operacionais, debitos, lucro


def _motivo_inelegivel(session: Session, venda_obj: Venda) -> str | None:
    if get_by_venda(session, venda_obj.id) is not None:
        return "Venda já fechada"
    if venda_obj.status != StatusVenda.concluido:
        return "Venda precisa estar concluída"
    if venda_obj.pagamento_pendente:
        return "Venda possui pagamento pendente"
    return None


def _validar_elegibilidade(session: Session, venda_obj: Venda) -> None:
    motivo = _motivo_inelegivel(session, venda_obj)
    if motivo is not None:
        raise FechamentoVendaError(motivo)


def _validar_participacoes(
    session: Session,
    participacoes: list[ParticipacaoFechamentoVendaCreate],
    lucro: Decimal,
) -> None:
    if lucro <= 0:
        if participacoes:
            raise FechamentoVendaError(ERRO_SEM_DISTRIBUICAO)
        return
    if not participacoes:
        raise FechamentoVendaError(ERRO_RATEIO_OBRIGATORIO)
    ids = [p.investidor_id for p in participacoes]
    if len(ids) != len(set(ids)):
        raise FechamentoVendaError(ERRO_INVESTIDOR_DUPLICADO)
    existentes = {
        row[0]
        for row in session.query(Investidor.id).filter(Investidor.id.in_(ids)).all()
    }
    if existentes != set(ids):
        raise FechamentoVendaError(ERRO_INVESTIDOR_INEXISTENTE)
    total = sum((p.percentual for p in participacoes), Decimal("0"))
    if _quantizar(total) != PERCENTUAL_TOTAL:
        raise FechamentoVendaError(ERRO_RATEIO_TOTAL)


def _quantizar(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)
