"""CRUD end-to-end dos bricks, em SQLite in-memory (sem depender do Postgres)."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.caixa import core as caixa
from xtreme_system.database.core import Base
from xtreme_system.investidor import core as investidor
from xtreme_system.meio_captacao import core as meio_captacao
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    event.listen(
        engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_veiculo_ciclo_completo(session: Session) -> None:
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    meio = meio_captacao.create(
        session, meio_captacao.MeioCaptacaoCreate(nome="Instagram")
    )

    criado = veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Gol",
            cor="Branco",
            ano=2018,
            placa="AAA1B22",
            km=70000,
            preco=Decimal("32000.00"),
            investidor_id=inv.id,
            meio_captacao_id=meio.id,
        ),
    )
    assert criado.id is not None
    assert criado.status is veiculo.StatusVeiculo.disponivel
    assert criado.investidor.nome == "Ana"

    veiculo.update(
        session, criado, veiculo.VeiculoUpdate(status=veiculo.StatusVeiculo.vendido)
    )
    atualizado = veiculo.get(session, criado.id)
    assert atualizado is not None
    assert atualizado.status is veiculo.StatusVeiculo.vendido
    assert len(veiculo.list_all(session)) == 1

    veiculo.delete(session, criado)
    assert veiculo.get(session, criado.id) is None


def test_placa_duplicada_rejeitada(session: Session) -> None:
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    meio = meio_captacao.create(session, meio_captacao.MeioCaptacaoCreate(nome="Site"))
    dados = veiculo.VeiculoCreate(
        tipo=veiculo.TipoVeiculo.carro,
        modelo="Gol",
        cor="Branco",
        ano=2018,
        placa="AAA1B22",
        km=70000,
        preco=Decimal("32000.00"),
        investidor_id=inv.id,
        meio_captacao_id=meio.id,
    )
    veiculo.create(session, dados)
    assert veiculo.get_by_placa(session, "AAA1B22") is not None

    with pytest.raises(IntegrityError):
        # ponytail: DB unique constraint catches the duplicate
        veiculo.create(session, dados)


def test_usuario_crud(session: Session) -> None:
    """CRUD de usuário: criar, buscar, listar, deletar e trocar senha."""
    u = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="teste", senha="abc", papel=usuario.Papel.vendedor
        ),
    )
    assert u.id is not None
    assert u.papel == usuario.Papel.vendedor

    encontrado = usuario.get(session, u.id)
    assert encontrado is not None
    assert encontrado.username == "teste"

    lista = usuario.list_all(session)
    assert len(lista) == 1

    usuario.change_password(session, u, "nova")
    senha_hash_antes = u.senha_hash
    usuario.change_password(session, u, "outra")
    assert u.senha_hash != senha_hash_antes

    usuario.delete(session, u)
    assert usuario.get(session, u.id) is None
    assert len(usuario.list_all(session)) == 0


def _investidor_e_veiculo(
    session: Session,
) -> tuple[investidor.Investidor, veiculo.Veiculo]:
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    meio = meio_captacao.create(session, meio_captacao.MeioCaptacaoCreate(nome="Site"))
    v = veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Gol",
            cor="Branco",
            ano=2018,
            placa="AAA1B22",
            km=70000,
            preco=Decimal("32000.00"),
            investidor_id=inv.id,
            meio_captacao_id=meio.id,
        ),
    )
    return inv, v


def test_criar_veiculo_gera_lancamento_de_custo_e_reduz_saldo(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    lanc = caixa.criar_lancamento_veiculo(session, v)
    assert lanc.tipo is caixa.TipoLancamento.custo
    assert lanc.origem is caixa.OrigemLancamento.veiculo
    assert caixa.saldo(session, inv.id) == Decimal("-32000.00")


def test_atualizar_preco_ou_investidor_sincroniza_lancamento(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    caixa.criar_lancamento_veiculo(session, v)
    outro = investidor.create(session, investidor.InvestidorCreate(nome="Bia"))

    atualizado = veiculo.update(
        session,
        v,
        veiculo.VeiculoUpdate(preco=Decimal("40000.00"), investidor_id=outro.id),
    )
    caixa.sincronizar_lancamento_veiculo(session, atualizado)

    assert caixa.saldo(session, inv.id) == Decimal("0")
    assert caixa.saldo(session, outro.id) == Decimal("-40000.00")


def test_excluir_veiculo_apaga_lancamento_em_cascata(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    lanc_id = caixa.criar_lancamento_veiculo(session, v).id

    veiculo.delete(session, v)
    session.expire_all()

    assert caixa.get(session, lanc_id) is None
    assert caixa.saldo(session, inv.id) == Decimal("0")


def test_lancamento_manual_ciclo_completo(session: Session) -> None:
    inv, _v = _investidor_e_veiculo(session)
    aporte = caixa.create(
        session,
        caixa.LancamentoCaixaCreate(
            investidor_id=inv.id,
            tipo=caixa.TipoLancamento.aporte,
            valor=Decimal("1000.00"),
            descricao="Aporte inicial",
        ),
    )
    assert aporte.origem is caixa.OrigemLancamento.manual

    caixa.update(session, aporte, caixa.LancamentoCaixaUpdate(valor=Decimal("1500.00")))
    assert caixa.get(session, aporte.id).valor == Decimal("1500.00")  # type: ignore[union-attr]

    caixa.delete(session, aporte)
    assert caixa.get(session, aporte.id) is None
