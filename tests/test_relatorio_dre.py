"""Relatório de DRE por período, a partir dos fechamentos de venda."""

from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.cliente import core as cliente
from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda

_seq = iter(range(1, 1000))


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_test_engine()
    with Session(engine) as s:
        u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
        s.add(u)
        s.flush()
        s.info["usuario_id"] = u.id
        yield s
    engine.dispose()


def _fechar(
    session: Session,
    *,
    data_fechamento: date,
    valor_venda: Decimal = Decimal("60000.00"),
    preco: Decimal = Decimal("40000.00"),
    custo_operacional: Decimal = Decimal("1500.00"),
    debitos: Decimal = Decimal("500.00"),
    inv: investidor.Investidor | None = None,
    vendedor_id: int | None = None,
) -> fechamento_venda.FechamentoVenda:
    """Cria venda concluída e seu fechamento, com data de competência forçada."""
    idx = next(_seq)
    dono = inv or investidor.create(
        session, investidor.InvestidorCreate(nome=f"Investidor {idx}")
    )
    cli = cliente.create(
        session,
        cliente.ClienteCreate(
            nome=f"Cliente {idx}",
            documento=f"{idx:011d}",
            tipo=cliente.TipoCliente.pessoa_fisica,
        ),
    )
    vei = veiculo.create(
        session,
        veiculo.VeiculoCreate(
            tipo=veiculo.TipoVeiculo.carro,
            modelo="Gol",
            cor="Branco",
            ano=2018,
            placa=f"ABC{idx:04d}",
            km=50000,
            preco=preco,
            investidor_id=dono.id,
        ),
    )
    if custo_operacional > 0:
        custo_veiculo.create(
            session,
            custo_veiculo.CustoVeiculoCreate(
                veiculo_id=vei.id,
                categoria="Mecânica",
                descricao="Revisão",
                valor=custo_operacional,
                data_custo=data_fechamento,
            ),
        )
    obj = venda.create(
        session,
        venda.VendaCreate(
            cliente_id=cli.id,
            veiculo_id=vei.id,
            vendedor_id=vendedor_id,
            data_venda=data_fechamento,
            valor_venda=valor_venda,
            debitos=debitos,
            forma_pagamento="a_vista",
            parcelas=1,
            status=venda.StatusVenda.concluido,
        ),
    )
    fechamento = fechamento_venda.confirmar(
        session,
        obj,
        fechamento_venda.FechamentoVendaCreate(
            participacoes=[
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=dono.id, percentual=Decimal("100")
                )
            ]
        ),
        usuario_id=None,
    )
    fechamento.data_fechamento = data_fechamento
    session.flush()
    return fechamento


def test_dre_totais_soma_snapshots_e_margem(session: Session) -> None:
    _fechar(session, data_fechamento=date(2026, 1, 10))
    _fechar(session, data_fechamento=date(2026, 2, 10))

    fechamentos = fechamento_venda.listar_para_dre(session)
    totais = fechamento_venda.dre_totais(fechamentos)

    assert totais.quantidade == 2
    assert totais.receita == Decimal("120000.00")
    assert totais.custo_veiculo == Decimal("80000.00")
    assert totais.custos_operacionais == Decimal("3000.00")
    assert totais.debitos == Decimal("1000.00")
    assert totais.lucro_liquido == Decimal("36000.00")
    assert totais.margem == Decimal("30.00")


def test_dre_totais_vazio_nao_divide_por_zero() -> None:
    totais = fechamento_venda.dre_totais([])

    assert totais.quantidade == 0
    assert totais.receita == Decimal("0.00")
    assert totais.margem == Decimal("0.00")


def test_dre_por_mes_agrupa_por_competencia(session: Session) -> None:
    _fechar(session, data_fechamento=date(2026, 1, 10))
    _fechar(session, data_fechamento=date(2026, 1, 20))
    _fechar(session, data_fechamento=date(2026, 2, 10))

    linhas = fechamento_venda.dre_por_mes(fechamento_venda.listar_para_dre(session))

    assert [linha.mes for linha in linhas] == [date(2026, 1, 1), date(2026, 2, 1)]
    assert [linha.quantidade for linha in linhas] == [2, 1]
    assert linhas[0].receita == Decimal("120000.00")
    assert linhas[1].lucro_liquido == Decimal("18000.00")


def test_listar_para_dre_recorta_periodo(session: Session) -> None:
    _fechar(session, data_fechamento=date(2026, 1, 10))
    dentro = _fechar(session, data_fechamento=date(2026, 2, 10))
    _fechar(session, data_fechamento=date(2026, 3, 10))

    fechamentos = fechamento_venda.listar_para_dre(
        session, data_de=date(2026, 2, 1), data_ate=date(2026, 2, 28)
    )

    assert [f.id for f in fechamentos] == [dentro.id]


def test_listar_para_dre_inclui_limites_do_periodo(session: Session) -> None:
    inicio = _fechar(session, data_fechamento=date(2026, 2, 1))
    fim = _fechar(session, data_fechamento=date(2026, 2, 28))

    fechamentos = fechamento_venda.listar_para_dre(
        session, data_de=date(2026, 2, 1), data_ate=date(2026, 2, 28)
    )

    assert [f.id for f in fechamentos] == [inicio.id, fim.id]


def test_listar_para_dre_filtra_por_investidor(session: Session) -> None:
    alvo = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    do_alvo = _fechar(session, data_fechamento=date(2026, 1, 10), inv=alvo)
    _fechar(session, data_fechamento=date(2026, 1, 11))

    fechamentos = fechamento_venda.listar_para_dre(session, investidor_id=alvo.id)

    assert [f.id for f in fechamentos] == [do_alvo.id]


def test_listar_para_dre_filtra_por_vendedor(session: Session) -> None:
    vendedor = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="vendedor", senha="senha", papel=usuario.Papel.funcionario
        ),
    )
    do_vendedor = _fechar(
        session, data_fechamento=date(2026, 1, 10), vendedor_id=vendedor.id
    )
    _fechar(session, data_fechamento=date(2026, 1, 11))

    fechamentos = fechamento_venda.listar_para_dre(session, vendedor_id=vendedor.id)

    assert [f.id for f in fechamentos] == [do_vendedor.id]


def test_listar_para_dre_combina_investidor_e_vendedor(session: Session) -> None:
    alvo = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    vendedor = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="vendedor", senha="senha", papel=usuario.Papel.funcionario
        ),
    )
    ambos = _fechar(
        session, data_fechamento=date(2026, 1, 10), inv=alvo, vendedor_id=vendedor.id
    )
    _fechar(session, data_fechamento=date(2026, 1, 11), inv=alvo)
    _fechar(session, data_fechamento=date(2026, 1, 12), vendedor_id=vendedor.id)

    fechamentos = fechamento_venda.listar_para_dre(
        session, investidor_id=alvo.id, vendedor_id=vendedor.id
    )

    assert [f.id for f in fechamentos] == [ambos.id]


# ---- UI ----


def _seed_dre(session: Session) -> None:
    _fechar(session, data_fechamento=date(2026, 1, 10))
    _fechar(session, data_fechamento=date(2026, 2, 10))


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[
            ("admin", usuario.Papel.admin),
            ("func", usuario.Papel.funcionario),
        ],
        seed=_seed_dre,
    )


def _login(client: TestClient, username: str) -> None:
    client.post("/ui/login", data={"username": username, "password": "senha"})


_PERIODO = "data_de=2026-01-01&data_ate=2026-12-31"


def test_ui_dre_admin_renderiza_totais(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(f"/ui/relatorios/dre?{_PERIODO}")

    assert resp.status_code == 200
    assert 'id="dre-resultado"' in resp.text
    assert "R$ 120.000,00" in resp.text
    assert "R$ 36.000,00" in resp.text
    assert "01/2026" in resp.text
    assert "02/2026" in resp.text


def test_ui_dre_funcionario_recebe_403(client: TestClient) -> None:
    _login(client, "func")

    resp = client.get("/ui/relatorios/dre")

    assert resp.status_code == 403


def test_ui_dre_sem_cookie_redireciona_login(client: TestClient) -> None:
    resp = client.get("/ui/relatorios/dre", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui/login"


def test_ui_dre_htmx_retorna_apenas_o_partial(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(f"/ui/relatorios/dre?{_PERIODO}", headers={"HX-Request": "true"})

    assert resp.status_code == 200
    assert 'id="dre-resultado"' in resp.text
    assert '<aside class="sidebar"' not in resp.text


def test_ui_dre_periodo_sem_fechamentos_mostra_vazio(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get("/ui/relatorios/dre?data_de=2020-01-01&data_ate=2020-12-31")

    assert resp.status_code == 200
    assert "Sem fechamentos" in resp.text
    assert "Detalhe dos fechamentos" not in resp.text


def test_ui_dre_data_invalida_retorna_422(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get("/ui/relatorios/dre?data_de=nao-e-data")

    assert resp.status_code == 422


def test_ui_dre_filtro_vazio_usa_periodo_padrao(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get("/ui/relatorios/dre?data_de=&data_ate=&investidor_id=")

    assert resp.status_code == 200


def test_ui_dre_id_nao_positivo_retorna_422(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(f"/ui/relatorios/dre?{_PERIODO}&investidor_id=0")

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "investidor_id"]


def test_ui_dre_periodo_invertido_retorna_422(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get("/ui/relatorios/dre?data_de=2026-12-31&data_ate=2026-01-01")

    assert resp.status_code == 422
    assert "data_de não pode ser maior" in resp.json()["detail"][0]["msg"]


def test_ui_dre_periodo_longo_demais_retorna_422(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get("/ui/relatorios/dre?data_de=2000-01-01&data_ate=2026-01-01")

    assert resp.status_code == 422
    assert "não pode exceder" in resp.json()["detail"][0]["msg"]


def test_ui_dre_exportar_valida_periodo(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(
        "/ui/relatorios/dre/exportar?data_de=2026-12-31&data_ate=2026-01-01"
    )

    assert resp.status_code == 422


def test_ui_dre_exportar_csv(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(f"/ui/relatorios/dre/exportar?{_PERIODO}")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="dre.csv"' in resp.headers["content-disposition"]
    linhas = resp.text.strip().splitlines()
    assert linhas[0].startswith("ID,Data,Venda,Veiculo,Placa,Investidor,Vendedor")
    assert len(linhas) == 3
    assert "60000.00" in linhas[1]


def test_ui_dre_exportar_respeita_filtro_de_periodo(client: TestClient) -> None:
    _login(client, "admin")

    resp = client.get(
        "/ui/relatorios/dre/exportar?data_de=2026-02-01&data_ate=2026-02-28"
    )

    assert len(resp.text.strip().splitlines()) == 2
