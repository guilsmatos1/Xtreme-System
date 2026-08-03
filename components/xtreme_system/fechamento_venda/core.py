"""Fechamento financeiro de vendas: cálculo, participações e lançamentos."""

from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
    inspect,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Mapped, Session, lazyload, mapped_column, relationship

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.caixa import core as caixa
from xtreme_system.compra import core as compra
from xtreme_system.crud import core as crud
from xtreme_system.custo_veiculo.core import CustoVeiculo
from xtreme_system.database.core import Base
from xtreme_system.investidor.core import Investidor, InvestidorRead
from xtreme_system.usuario.core import Usuario, UsuarioRead
from xtreme_system.veiculo.core import Veiculo
from xtreme_system.venda.core import StatusVenda, Venda, VendaRead

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")
PERCENTUAL_TOTAL = Decimal("100")
ERRO_SEM_DISTRIBUICAO = "Venda sem lucro positivo não aceita distribuição"
ERRO_RATEIO_OBRIGATORIO = "Informe o rateio do lucro"
ERRO_INVESTIDOR_DUPLICADO = "Investidor duplicado no rateio"
ERRO_INVESTIDOR_INEXISTENTE = "investidor_id inexistente no rateio"
ERRO_RATEIO_TOTAL = "Rateio deve somar 100%"
ERRO_SCHEMA_DESATUALIZADO = (
    "Atualize o banco com `make migrate` para usar fechamento de vendas"
)
_SCHEMA_DISPONIVEL_POR_ENGINE: WeakKeyDictionary[Engine, bool] = WeakKeyDictionary()


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
        Date, server_default=func.current_date(), index=True
    )
    receita: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custo_veiculo: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custos_operacionais: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    debitos: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    lucro_liquido: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    venda: Mapped[Venda] = relationship(lazy="selectin")
    usuario: Mapped[Usuario | None] = relationship(lazy="selectin")
    participacoes: Mapped[list["ParticipacaoFechamentoVenda"]] = relationship(
        back_populates="fechamento",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ParticipacaoFechamentoVenda(Base):
    __tablename__ = "participacao_fechamento_venda"
    __table_args__ = (
        UniqueConstraint(
            "fechamento_venda_id",
            "investidor_id",
            name="uq_participacao_fechamento_investidor",
        ),
        CheckConstraint(
            "percentual > 0 AND percentual <= 100",
            name="ck_participacao_percentual_range",
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
    investidor: Mapped[Investidor] = relationship(lazy="selectin")


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


class DreTotais(BaseModel):
    quantidade: int
    receita: Decimal
    custo_veiculo: Decimal
    custos_operacionais: Decimal
    debitos: Decimal
    lucro_liquido: Decimal
    margem: Decimal


class DreLinhaMes(DreTotais):
    mes: date


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


class ResultadoCalculo(BaseModel):
    receita: Decimal
    custo_veiculo: Decimal
    custos_operacionais: Decimal
    debitos: Decimal
    lucro_liquido: Decimal


def _schema_disponivel(session: Session) -> bool:
    bind = session.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    try:
        return _SCHEMA_DISPONIVEL_POR_ENGINE[engine]
    except KeyError:
        pass
    # Inspeciona a conexão ativa da sessão (não o engine): inspecionar o engine
    # abriria uma conexão própria cujo rollback descarta escritas ainda não
    # commitadas da sessão (flush sem commit).
    inspector = inspect(session.connection())
    disponivel = inspector.has_table(
        FechamentoVenda.__tablename__
    ) and inspector.has_table(ParticipacaoFechamentoVenda.__tablename__)
    _SCHEMA_DISPONIVEL_POR_ENGINE[engine] = disponivel
    return disponivel


def get(session: Session, fechamento_id: int) -> FechamentoVenda | None:
    if not _schema_disponivel(session):
        return None
    return crud.get(session, FechamentoVenda, fechamento_id)


def get_by_venda(session: Session, venda_id: int) -> FechamentoVenda | None:
    if not _schema_disponivel(session):
        return None
    return session.query(FechamentoVenda).filter_by(venda_id=venda_id).one_or_none()


def ids_by_venda_ids(session: Session, venda_ids: list[int]) -> dict[int, int]:
    if not venda_ids or not _schema_disponivel(session):
        return {}
    rows = (
        session.query(FechamentoVenda.venda_id, FechamentoVenda.id)
        .filter(FechamentoVenda.venda_id.in_(venda_ids))
        .all()
    )
    return {row.venda_id: row.id for row in rows}


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[FechamentoVenda]:
    if not _schema_disponivel(session):
        raise FechamentoVendaError(ERRO_SCHEMA_DESATUALIZADO)
    query = session.query(FechamentoVenda).order_by(FechamentoVenda.id)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    return list(query.all())


def preview(session: Session, venda_obj: Venda) -> FechamentoVendaPreview:
    calculo = _calcular(session, venda_obj)
    motivo = _motivo_inelegivel(session, venda_obj)
    investidores = list(session.query(Investidor).order_by(Investidor.nome).all())
    return FechamentoVendaPreview(
        elegivel=motivo is None,
        motivo=motivo,
        ja_fechada=get_by_venda(session, venda_obj.id) is not None,
        **calculo.model_dump(),
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
    calculo = _calcular(session, venda_obj)
    _validar_elegibilidade(session, venda_obj)
    _validar_participacoes(session, data.participacoes, calculo.lucro_liquido)

    fechamento = FechamentoVenda(
        venda_id=venda_obj.id,
        usuario_id=usuario_id,
        **calculo.model_dump(),
    )
    session.add(fechamento)
    session.flush()
    session.refresh(fechamento)
    auditar(
        session,
        actor_id=usuario_id,
        tabela="fechamento_venda",
        tipo_acao="CREATE",
        registro_id=fechamento.id,
        dados_depois=snapshot(fechamento),
    )

    caixa.criar_lancamento_fechamento(
        session,
        investidor_id=venda_obj.veiculo.investidor_id,
        fechamento_venda_id=fechamento.id,
        tipo=caixa.TipoLancamento.receita_venda,
        valor=calculo.receita,
        descricao=f"Receita da venda #{venda_obj.id}",
        actor_id=usuario_id,
    )
    if calculo.lucro_liquido > 0:
        valores = _distribuir_lucro(calculo.lucro_liquido, data.participacoes)
        for item, valor in zip(data.participacoes, valores, strict=True):
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
                actor_id=usuario_id,
                tabela="participacao_fechamento_venda",
                tipo_acao="CREATE",
                registro_id=participacao.id,
                dados_depois=snapshot(participacao),
            )
            caixa.criar_lancamento_fechamento(
                session,
                investidor_id=item.investidor_id,
                fechamento_venda_id=fechamento.id,
                tipo=caixa.TipoLancamento.distribuicao_lucro,
                valor=valor,
                descricao=f"Distribuição de lucro da venda #{venda_obj.id}",
                actor_id=usuario_id,
            )
    crud.flush(session)
    session.refresh(fechamento)
    return fechamento


def listar_para_dre(
    session: Session,
    *,
    data_de: date | None = None,
    data_ate: date | None = None,
    investidor_id: int | None = None,
    vendedor_id: int | None = None,
) -> list[FechamentoVenda]:
    if not _schema_disponivel(session):
        raise FechamentoVendaError(ERRO_SCHEMA_DESATUALIZADO)
    query = session.query(FechamentoVenda).options(
        lazyload(FechamentoVenda.usuario),
        lazyload(FechamentoVenda.participacoes),
    )
    if investidor_id is not None:
        query = query.join(Venda, FechamentoVenda.venda_id == Venda.id).join(
            Veiculo, Venda.veiculo_id == Veiculo.id
        )
        query = query.filter(Veiculo.investidor_id == investidor_id)
    elif vendedor_id is not None:
        query = query.join(Venda, FechamentoVenda.venda_id == Venda.id)
    if vendedor_id is not None:
        query = query.filter(Venda.vendedor_id == vendedor_id)
    if data_de is not None:
        query = query.filter(FechamentoVenda.data_fechamento >= data_de)
    if data_ate is not None:
        query = query.filter(FechamentoVenda.data_fechamento <= data_ate)
    return list(
        query.order_by(FechamentoVenda.data_fechamento, FechamentoVenda.id).all()
    )


def dre_totais(fechamentos: list[FechamentoVenda]) -> DreTotais:
    receita = sum((f.receita for f in fechamentos), Decimal("0"))
    lucro = sum((f.lucro_liquido for f in fechamentos), Decimal("0"))
    return DreTotais(
        quantidade=len(fechamentos),
        receita=_quantizar(receita),
        custo_veiculo=_quantizar(
            sum((f.custo_veiculo for f in fechamentos), Decimal("0"))
        ),
        custos_operacionais=_quantizar(
            sum((f.custos_operacionais for f in fechamentos), Decimal("0"))
        ),
        debitos=_quantizar(sum((f.debitos for f in fechamentos), Decimal("0"))),
        lucro_liquido=_quantizar(lucro),
        margem=_quantizar(lucro / receita * PERCENTUAL_TOTAL) if receita else ZERO,
    )


def dre_por_mes(fechamentos: list[FechamentoVenda]) -> list[DreLinhaMes]:
    por_mes: dict[date, list[FechamentoVenda]] = {}
    for item in fechamentos:
        mes = item.data_fechamento.replace(day=1)
        por_mes.setdefault(mes, []).append(item)
    return [
        DreLinhaMes(mes=mes, **dre_totais(itens).model_dump())
        for mes, itens in sorted(por_mes.items())
    ]


def _calcular(session: Session, venda_obj: Venda) -> ResultadoCalculo:
    receita = _quantizar(venda_obj.valor_venda)
    compra_atual = compra.get_latest_by_veiculo(session, venda_obj.veiculo_id)
    custo_veiculo = _quantizar(
        compra_atual.valor_compra
        if compra_atual is not None
        else venda_obj.veiculo.preco or Decimal("0")
    )
    custos_operacionais = _quantizar(
        session.query(func.sum(CustoVeiculo.valor))
        .filter_by(veiculo_id=venda_obj.veiculo_id)
        .scalar()
        or Decimal("0")
    )
    debitos = _quantizar(venda_obj.debitos or Decimal("0"))
    lucro = _quantizar(receita - custo_veiculo - custos_operacionais - debitos)
    return ResultadoCalculo(
        receita=receita,
        custo_veiculo=custo_veiculo,
        custos_operacionais=custos_operacionais,
        debitos=debitos,
        lucro_liquido=lucro,
    )


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


def _distribuir_lucro(
    lucro: Decimal, participacoes: list[ParticipacaoFechamentoVendaCreate]
) -> list[Decimal]:
    valores: list[Decimal] = []
    restos: list[tuple[Decimal, int]] = []
    for indice, item in enumerate(participacoes):
        valor_exato = lucro * item.percentual / PERCENTUAL_TOTAL
        valor = valor_exato.quantize(CENTAVO, rounding=ROUND_DOWN)
        valores.append(valor)
        restos.append((valor_exato - valor, indice))

    centavos_restantes = int((lucro - sum(valores, Decimal("0"))) / CENTAVO)
    for indice in sorted(
        range(len(restos)), key=lambda idx: restos[idx][0], reverse=True
    )[:centavos_restantes]:
        valores[indice] += CENTAVO

    return valores
