"""Veículo: enums, model (com FKs), schemas e CRUD."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, Query, Session, mapped_column, relationship

from xtreme_system.crud import core as crud
from xtreme_system.crud.search import apply_text_search
from xtreme_system.database.core import Base
from xtreme_system.documento_procuracao.core import DocumentoProcuracao
from xtreme_system.documento_veiculo.core import DocumentoVeiculo
from xtreme_system.imagem_veiculo.core import ImagemVeiculo
from xtreme_system.investidor.core import Investidor, InvestidorRead


class TipoVeiculo(StrEnum):
    moto = "moto"
    carro = "carro"


class StatusVeiculo(StrEnum):
    disponivel = "disponivel"
    vendido = "vendido"
    reservado = "reservado"


class TipoEntrada(StrEnum):
    compra = "compra"
    consignacao = "consignacao"


class Veiculo(Base):
    __tablename__ = "veiculo"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoVeiculo]
    modelo: Mapped[str]
    marca: Mapped[str | None]
    cor: Mapped[str]
    ano: Mapped[int]
    placa: Mapped[str] = mapped_column(unique=True, index=True)
    chassi: Mapped[str | None]
    renavam: Mapped[str | None]
    km: Mapped[int | None]
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    procuracao: Mapped[str | None]
    proprietario_registrado: Mapped[str | None]
    status: Mapped[StatusVeiculo] = mapped_column(default=StatusVeiculo.disponivel)
    tipo_entrada: Mapped[TipoEntrada] = mapped_column(default=TipoEntrada.compra)
    revisao: Mapped[bool] = mapped_column(default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    investidor_id: Mapped[int] = mapped_column(ForeignKey("investidor.id"), index=True)

    investidor: Mapped[Investidor] = relationship(lazy="selectin")
    imagens: Mapped[list["ImagemVeiculo"]] = relationship(cascade="all, delete-orphan")
    documentos: Mapped[list["DocumentoVeiculo"]] = relationship(
        cascade="all, delete-orphan"
    )
    documentos_procuracao: Mapped[list["DocumentoProcuracao"]] = relationship(
        cascade="all, delete-orphan"
    )

    @property
    def tempo_estoque(self) -> int:
        return (datetime.now(UTC).date() - self.criado_em.date()).days


class VeiculoCreate(BaseModel):
    tipo: TipoVeiculo
    modelo: str
    marca: str | None = None
    cor: str
    ano: int
    placa: str
    chassi: str | None = None
    renavam: str | None = None
    km: int | None = Field(default=None, ge=0)
    preco: Decimal = Field(gt=0)
    procuracao: str | None = None
    proprietario_registrado: str | None = None
    status: StatusVeiculo = StatusVeiculo.disponivel
    tipo_entrada: TipoEntrada = TipoEntrada.compra
    revisao: bool = False
    investidor_id: int


class VeiculoUpdate(BaseModel):
    tipo: TipoVeiculo | None = None
    modelo: str | None = None
    marca: str | None = None
    cor: str | None = None
    ano: int | None = None
    placa: str | None = None
    chassi: str | None = None
    renavam: str | None = None
    km: int | None = Field(default=None, ge=0)
    preco: Decimal | None = Field(default=None, gt=0)
    procuracao: str | None = None
    proprietario_registrado: str | None = None
    status: StatusVeiculo | None = None
    tipo_entrada: TipoEntrada | None = None
    revisao: bool | None = None
    investidor_id: int | None = None


class VeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoVeiculo
    modelo: str
    marca: str | None
    cor: str
    ano: int
    placa: str
    chassi: str | None
    renavam: str | None
    km: int | None = None
    preco: Decimal
    procuracao: str | None
    proprietario_registrado: str | None
    status: StatusVeiculo
    tipo_entrada: TipoEntrada
    revisao: bool
    investidor: InvestidorRead


def list_all(
    session: Session, *, limit: int | None = None, offset: int = 0
) -> list[Veiculo]:
    return crud.list_all(session, Veiculo, limit=limit, offset=offset)


def query(session: Session) -> Query[Veiculo]:
    return session.query(Veiculo).join(Investidor)


def list_ids(session: Session) -> list[int]:
    return [row.id for row in session.query(Veiculo.id).order_by(Veiculo.id).all()]


def get(session: Session, veiculo_id: int) -> Veiculo | None:
    return crud.get(session, Veiculo, veiculo_id)


def create(
    session: Session, data: VeiculoCreate, actor_id: int | None = None
) -> Veiculo:
    return crud.create(session, Veiculo, data, actor_id)


def update(
    session: Session, obj: Veiculo, data: VeiculoUpdate, actor_id: int | None = None
) -> Veiculo:
    return crud.update(session, obj, data, actor_id)


def delete(session: Session, obj: Veiculo, actor_id: int | None = None) -> None:
    crud.delete(session, obj, actor_id)


def get_by_placa(session: Session, placa: str) -> Veiculo | None:
    return session.query(Veiculo).filter_by(placa=placa).one_or_none()


def search(session: Session, term: str, column: str | None = None) -> list[Veiculo]:
    return list(search_query(session, term, column).all())


def search_query(
    session: Session, term: str, column: str | None = None
) -> Query[Veiculo]:
    sql_query = query(session)

    # Mapa de colunas permitidas para busca
    columns_map = {
        "modelo": Veiculo.modelo,
        "placa": Veiculo.placa,
        "cor": Veiculo.cor,
        "marca": Veiculo.marca,
        "chassi": Veiculo.chassi,
        "renavam": Veiculo.renavam,
        "procuracao": Veiculo.procuracao,
        "proprietario_registrado": Veiculo.proprietario_registrado,
        "tipo": Veiculo.tipo,
        "status": Veiculo.status,
        "tipo_entrada": Veiculo.tipo_entrada,
        "investidor": Investidor.nome,
        "ano": Veiculo.ano,
        "km": Veiculo.km,
        "preco": Veiculo.preco,
        "revisao": Veiculo.revisao,
    }

    return apply_text_search(
        sql_query,
        term,
        columns_map=columns_map,
        default_columns=(
            Veiculo.modelo,
            Veiculo.placa,
            Veiculo.cor,
        ),
        column=column,
    )


def resumo_estoque(session: Session) -> dict[StatusVeiculo, tuple[int, Decimal]]:
    """Retorna (contagem, soma de preco) por status de veículo."""
    rows = (
        session.query(Veiculo.status, func.count(Veiculo.id), func.sum(Veiculo.preco))
        .group_by(Veiculo.status)
        .all()
    )
    return {
        status: (count or 0, total or Decimal("0")) for status, count, total in rows
    }
