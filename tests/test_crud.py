"""CRUD end-to-end dos bricks, em SQLite in-memory (sem depender do Postgres)."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.auditoria import core as auditoria
from xtreme_system.caixa import core as caixa
from xtreme_system.documento_veiculo import core as _documento_veiculo  # noqa: F401
from xtreme_system.imagem_veiculo import core as _imagem_veiculo  # noqa: F401
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.whatsapp import core as whatsapp


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_test_engine()
    with Session(engine) as s:
        yield s


def _seed_usuario(session: Session) -> usuario.Usuario:
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    session.add(u)
    session.flush()
    session.info["usuario_id"] = u.id
    return u


def test_veiculo_ciclo_completo(session: Session) -> None:
    _seed_usuario(session)
    u = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="auditor", senha="123", papel=usuario.Papel.admin
        ),
        session.info["usuario_id"],
    )
    actor_id = u.id
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"), actor_id)

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
        ),
        actor_id,
    )
    assert criado.id is not None
    assert criado.status is veiculo.StatusVeiculo.disponivel
    assert criado.investidor.nome == "Ana"

    veiculo.update(
        session,
        criado,
        veiculo.VeiculoUpdate(status=veiculo.StatusVeiculo.vendido),
        actor_id,
    )
    atualizado = veiculo.get(session, criado.id)
    assert atualizado is not None
    assert atualizado.status is veiculo.StatusVeiculo.vendido
    assert len(veiculo.list_all(session)) == 1

    veiculo.delete(session, criado, actor_id)
    assert veiculo.get(session, criado.id) is None

    # Audit assertions
    rows = (
        session.query(auditoria.Auditoria)
        .filter_by(tabela="veiculo")
        .order_by(auditoria.Auditoria.id)
        .all()
    )
    assert len(rows) == 3  # CREATE, UPDATE, DELETE
    assert rows[0].tipo_acao == "CREATE"
    assert rows[0].usuario_id == u.id
    assert rows[1].tipo_acao == "UPDATE"
    dados_antes = rows[1].dados_antes
    dados_depois = rows[1].dados_depois
    assert dados_antes is not None
    assert dados_depois is not None
    assert dados_antes["status"] == "disponivel"
    assert dados_depois["status"] == "vendido"
    assert rows[2].tipo_acao == "DELETE"


def test_placa_duplicada_rejeitada(session: Session) -> None:
    _seed_usuario(session)
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    dados = veiculo.VeiculoCreate(
        tipo=veiculo.TipoVeiculo.carro,
        modelo="Gol",
        cor="Branco",
        ano=2018,
        placa="AAA1B22",
        km=70000,
        preco=Decimal("32000.00"),
        investidor_id=inv.id,
    )
    veiculo.create(session, dados)
    assert veiculo.get_by_placa(session, "AAA1B22") is not None

    with pytest.raises(IntegrityError):
        # DB unique constraint catches the duplicate
        veiculo.create(session, dados)


def test_usuario_crud(session: Session) -> None:
    """CRUD de usuário: criar, buscar, listar, deletar e trocar senha."""
    _seed_usuario(session)
    u = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="teste", senha="abc", papel=usuario.Papel.funcionario
        ),
    )
    assert u.id is not None
    assert u.papel == usuario.Papel.funcionario

    encontrado = usuario.get(session, u.id)
    assert encontrado is not None
    assert encontrado.username == "teste"

    lista = usuario.list_all(session)
    assert len(lista) == 2

    usuario.change_password(session, u, "nova")
    senha_hash_antes = u.senha_hash
    usuario.change_password(session, u, "outra")
    assert u.senha_hash != senha_hash_antes

    usuario.delete(session, u)
    assert usuario.get(session, u.id) is None
    assert len(usuario.list_all(session)) == 1


def test_senha_hash_masked_in_audit(session: Session) -> None:
    session.info["usuario_id"] = 1
    _u = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="mask", senha="secret", papel=usuario.Papel.admin
        ),
        1,
    )
    rows = (
        session.query(auditoria.Auditoria)
        .filter_by(tabela="usuario", tipo_acao="CREATE")
        .all()
    )
    assert len(rows) == 1
    dados = rows[0].dados_depois
    assert dados is not None
    assert dados["senha_hash"] == "***"
    assert "secret" not in str(dados)


def test_evolution_api_key_masked_in_audit_data() -> None:
    config = whatsapp.WhatsappConfig(id=1, evolution_api_key="chave-secreta")
    dados = auditoria.snapshot(config)
    assert dados["evolution_api_key"] == "***"
    assert "chave-secreta" not in str(dados)


def test_caixa_lancamento_veiculo_audit(session: Session) -> None:
    _seed_usuario(session)
    u = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="caixa_audit", senha="123", papel=usuario.Papel.admin
        ),
        session.info["usuario_id"],
    )
    actor_id = u.id
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"), actor_id)
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
        ),
        actor_id,
    )
    lanc = caixa.criar_lancamento_veiculo(session, v, actor_id)
    rows = (
        session.query(auditoria.Auditoria)
        .filter_by(
            tabela="lancamento_investimento",
            tipo_acao="CREATE",
            registro_id=lanc.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].usuario_id == u.id
    dados_depois = rows[0].dados_depois
    assert dados_depois is not None
    assert dados_depois["tipo"] == "custo"

    # Deletar o veículo deve auditar o DELETE do lançamento vinculado
    # (a FK tem ondelete=CASCADE, mas isso ignoraria o ORM/auditoria).
    caixa.deletar_lancamento_veiculo(session, v, actor_id)
    veiculo.delete(session, v, actor_id)
    delete_rows = (
        session.query(auditoria.Auditoria)
        .filter_by(
            tabela="lancamento_investimento",
            tipo_acao="DELETE",
            registro_id=lanc.id,
        )
        .all()
    )
    assert len(delete_rows) == 1
    assert caixa.get(session, lanc.id) is None


def _investidor_e_veiculo(
    session: Session,
) -> tuple[investidor.Investidor, veiculo.Veiculo]:
    if "usuario_id" not in session.info:
        _seed_usuario(session)
    actor_id = int(session.info["usuario_id"])
    inv = investidor.create(session, investidor.InvestidorCreate(nome="Ana"), actor_id)
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
        ),
        actor_id,
    )
    return inv, v


def test_criar_veiculo_gera_lancamento_de_custo_e_reduz_saldo(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    lanc = caixa.criar_lancamento_veiculo(session, v, session.info["usuario_id"])
    assert lanc.tipo is caixa.TipoLancamento.custo
    assert lanc.origem is caixa.OrigemLancamento.veiculo
    assert caixa.saldo(session, inv.id) == Decimal("-32000.00")


def test_atualizar_preco_ou_investidor_sincroniza_lancamento(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    caixa.criar_lancamento_veiculo(session, v)
    outro = investidor.create(
        session,
        investidor.InvestidorCreate(nome="Bia"),
        session.info["usuario_id"],
    )

    atualizado = veiculo.update(
        session,
        v,
        veiculo.VeiculoUpdate(preco=Decimal("40000.00"), investidor_id=outro.id),
        session.info["usuario_id"],
    )
    caixa.sincronizar_lancamento_veiculo(
        session, atualizado, session.info["usuario_id"]
    )

    assert caixa.saldo(session, inv.id) == Decimal("0")
    assert caixa.saldo(session, outro.id) == Decimal("-40000.00")


def test_excluir_veiculo_apaga_lancamento_em_cascata(session: Session) -> None:
    inv, v = _investidor_e_veiculo(session)
    lanc_id = caixa.criar_lancamento_veiculo(session, v).id

    veiculo.delete(session, v, session.info["usuario_id"])
    session.expire_all()

    assert caixa.get(session, lanc_id) is None
    assert caixa.saldo(session, inv.id) == Decimal("0")


def test_lancamento_manual_ciclo_completo(session: Session) -> None:
    _seed_usuario(session)
    inv, _v = _investidor_e_veiculo(session)
    aporte = caixa.create(
        session,
        caixa.LancamentoInvestimentoCreate(
            investidor_id=inv.id,
            tipo=caixa.TipoLancamento.aporte,
            valor=Decimal("1000.00"),
            descricao="Aporte inicial",
        ),
        session.info["usuario_id"],
    )
    assert aporte.origem is caixa.OrigemLancamento.manual

    caixa.update(
        session,
        aporte,
        caixa.LancamentoInvestimentoUpdate(valor=Decimal("1500.00")),
        session.info["usuario_id"],
    )
    assert caixa.get(session, aporte.id).valor == Decimal("1500.00")  # type: ignore[union-attr]

    caixa.delete(session, aporte, session.info["usuario_id"])
    assert caixa.get(session, aporte.id) is None
