"""Fechamento financeiro de vendas."""

from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.caixa import core as caixa
from xtreme_system.cliente import core as cliente
from xtreme_system.custo_veiculo import core as custo_veiculo
from xtreme_system.fechamento_venda import core as fechamento_venda
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo
from xtreme_system.venda import core as venda


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


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        usuarios=[
            ("admin", usuario.Papel.admin),
            ("func", usuario.Papel.funcionario),
        ]
    )


def _token(client: TestClient, username: str) -> str:
    resp = client.post("/login", data={"username": username, "password": "senha"})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def _seed_venda(
    session: Session,
    *,
    status: venda.StatusVenda = venda.StatusVenda.concluido,
    pagamento_pendente: bool = False,
    valor_venda: Decimal = Decimal("60000.00"),
    debitos: Decimal | None = Decimal("500.00"),
) -> tuple[investidor.Investidor, investidor.Investidor, venda.Venda]:
    inv_principal = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))
    inv_participante = investidor.create(
        session, investidor.InvestidorCreate(nome="Bia")
    )
    cli = cliente.create(
        session,
        cliente.ClienteCreate(
            nome="João",
            documento="12345678901",
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
            placa="ABC1D23",
            km=50000,
            preco=Decimal("40000.00"),
            investidor_id=inv_principal.id,
        ),
    )
    custo_veiculo.create(
        session,
        custo_veiculo.CustoVeiculoCreate(
            veiculo_id=vei.id,
            categoria="Mecânica",
            descricao="Revisão",
            valor=Decimal("1500.00"),
            data_custo="2026-07-01",
        ),
    )
    obj = venda.create(
        session,
        venda.VendaCreate(
            cliente_id=cli.id,
            veiculo_id=vei.id,
            data_venda="2026-07-02",
            valor_venda=valor_venda,
            debitos=debitos,
            forma_pagamento="a_vista",
            parcelas=1,
            status=status,
            pagamento_pendente=pagamento_pendente,
        ),
    )
    return inv_principal, inv_participante, obj


def test_confirmar_fechamento_calcula_lucro_e_lancamentos(session: Session) -> None:
    principal, participante, venda_obj = _seed_venda(session)

    fechamento = fechamento_venda.confirmar(
        session,
        venda_obj,
        fechamento_venda.FechamentoVendaCreate(
            participacoes=[
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=principal.id, percentual=Decimal("60")
                ),
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=participante.id, percentual=Decimal("40")
                ),
            ]
        ),
        usuario_id=None,
    )

    assert fechamento.receita == Decimal("60000.00")
    assert fechamento.custo_veiculo == Decimal("40000.00")
    assert fechamento.custos_operacionais == Decimal("1500.00")
    assert fechamento.debitos == Decimal("500.00")
    assert fechamento.lucro_liquido == Decimal("18000.00")
    assert [p.valor for p in fechamento.participacoes] == [
        Decimal("10800.00"),
        Decimal("7200.00"),
    ]
    lancamentos = caixa.list_all(session)
    assert [lancamento.tipo for lancamento in lancamentos] == [
        caixa.TipoLancamento.receita_venda,
        caixa.TipoLancamento.distribuicao_lucro,
        caixa.TipoLancamento.distribuicao_lucro,
    ]
    assert caixa.saldo(session, principal.id) == Decimal("49200.00")
    assert caixa.saldo(session, participante.id) == Decimal("-7200.00")


def test_confirmar_fechamento_distribui_residuo_de_arredondamento(
    session: Session,
) -> None:
    principal, participante, venda_obj = _seed_venda(
        session, valor_venda=Decimal("42001.00")
    )
    terceiro = investidor.create(session, investidor.InvestidorCreate(nome="Caio"))

    fechamento = fechamento_venda.confirmar(
        session,
        venda_obj,
        fechamento_venda.FechamentoVendaCreate(
            participacoes=[
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=principal.id, percentual=Decimal("33.33")
                ),
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=participante.id, percentual=Decimal("33.33")
                ),
                fechamento_venda.ParticipacaoFechamentoVendaCreate(
                    investidor_id=terceiro.id, percentual=Decimal("33.34")
                ),
            ]
        ),
        usuario_id=None,
    )

    assert fechamento.lucro_liquido == Decimal("1.00")
    assert [p.valor for p in fechamento.participacoes] == [
        Decimal("0.33"),
        Decimal("0.33"),
        Decimal("0.34"),
    ]
    assert sum((p.valor for p in fechamento.participacoes), Decimal("0")) == Decimal(
        "1.00"
    )


def test_schema_disponivel_e_cacheada_por_engine(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []

    class InspectorStub:
        def has_table(self, table_name: str) -> bool:
            chamadas.append(table_name)
            return True

    fechamento_venda._SCHEMA_DISPONIVEL_POR_ENGINE.clear()  # noqa: SLF001
    monkeypatch.setattr(fechamento_venda, "inspect", lambda _conn: InspectorStub())

    assert fechamento_venda._schema_disponivel(session) is True  # noqa: SLF001
    assert fechamento_venda._schema_disponivel(session) is True  # noqa: SLF001
    assert chamadas == ["fechamento_venda", "participacao_fechamento_venda"]


@pytest.mark.parametrize(
    ("status", "pagamento_pendente"),
    [
        (venda.StatusVenda.pendente, False),
        (venda.StatusVenda.cancelado, False),
        (venda.StatusVenda.concluido, True),
    ],
)
def test_bloqueia_venda_inelegivel(
    session: Session, status: venda.StatusVenda, pagamento_pendente: bool
) -> None:
    principal, _, venda_obj = _seed_venda(
        session, status=status, pagamento_pendente=pagamento_pendente
    )

    with pytest.raises(fechamento_venda.FechamentoVendaError):
        fechamento_venda.confirmar(
            session,
            venda_obj,
            fechamento_venda.FechamentoVendaCreate(
                participacoes=[
                    fechamento_venda.ParticipacaoFechamentoVendaCreate(
                        investidor_id=principal.id, percentual=Decimal("100")
                    )
                ]
            ),
            usuario_id=None,
        )


def test_bloqueia_fechamento_duplicado_e_rateio_incompleto(
    session: Session,
) -> None:
    principal, _, venda_obj = _seed_venda(session)
    data = fechamento_venda.FechamentoVendaCreate(
        participacoes=[
            fechamento_venda.ParticipacaoFechamentoVendaCreate(
                investidor_id=principal.id, percentual=Decimal("90")
            )
        ]
    )
    with pytest.raises(fechamento_venda.FechamentoVendaError, match="100"):
        fechamento_venda.confirmar(session, venda_obj, data, usuario_id=None)

    data = fechamento_venda.FechamentoVendaCreate(
        participacoes=[
            fechamento_venda.ParticipacaoFechamentoVendaCreate(
                investidor_id=principal.id, percentual=Decimal("100")
            )
        ]
    )
    fechamento_venda.confirmar(session, venda_obj, data, usuario_id=None)
    with pytest.raises(fechamento_venda.FechamentoVendaError, match="fechada"):
        fechamento_venda.confirmar(session, venda_obj, data, usuario_id=None)


def test_lucro_zero_ou_negativo_nao_cria_distribuicao(session: Session) -> None:
    _, _, venda_obj = _seed_venda(
        session,
        valor_venda=Decimal("41500.00"),
        debitos=None,
    )

    fechamento = fechamento_venda.confirmar(
        session,
        venda_obj,
        fechamento_venda.FechamentoVendaCreate(participacoes=[]),
        usuario_id=None,
    )

    assert fechamento.lucro_liquido == Decimal("0.00")
    assert fechamento.participacoes == []
    assert [lancamento.tipo for lancamento in caixa.list_all(session)] == [
        caixa.TipoLancamento.receita_venda
    ]


def _seed_api(client: TestClient, headers: dict[str, str]) -> tuple[int, int, int]:
    inv_ana = client.post("/investidores", json={"nome": "Ana"}, headers=headers)
    inv_bia = client.post("/investidores", json={"nome": "Bia"}, headers=headers)
    cliente_resp = client.post(
        "/clientes",
        json={
            "nome": "João Silva",
            "documento": "12345678901",
            "tipo": "pessoa_fisica",
        },
        headers=headers,
    )
    veiculo_resp = client.post(
        "/veiculos",
        json={
            "tipo": "carro",
            "modelo": "Gol",
            "cor": "Branco",
            "ano": 2018,
            "placa": "ABC1D23",
            "km": 50000,
            "preco": "40000.00",
            "investidor_id": inv_ana.json()["id"],
        },
        headers=headers,
    )
    venda_resp = client.post(
        "/vendas",
        json={
            "cliente_id": cliente_resp.json()["id"],
            "veiculo_id": veiculo_resp.json()["id"],
            "data_venda": "2026-07-02",
            "valor_venda": "50000.00",
            "forma_pagamento": "a_vista",
            "parcelas": 1,
            "status": "concluido",
        },
        headers=headers,
    )
    return venda_resp.json()["id"], inv_ana.json()["id"], inv_bia.json()["id"]


def test_endpoints_json_e_permissoes(client: TestClient) -> None:
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    func_headers = {"Authorization": f"Bearer {_token(client, 'func')}"}
    venda_id, inv_ana, inv_bia = _seed_api(client, admin_headers)

    preview = client.get(f"/vendas/{venda_id}/fechamento/preview", headers=func_headers)
    assert preview.status_code == 200
    assert preview.json()["elegivel"] is True
    assert preview.json()["lucro_liquido"] == "10000.00"

    proibido = client.post(
        f"/vendas/{venda_id}/fechamento",
        json={"participacoes": [{"investidor_id": inv_ana, "percentual": "100"}]},
        headers=func_headers,
    )
    assert proibido.status_code == 403

    criado = client.post(
        f"/vendas/{venda_id}/fechamento",
        json={
            "participacoes": [
                {"investidor_id": inv_ana, "percentual": "50"},
                {"investidor_id": inv_bia, "percentual": "50"},
            ]
        },
        headers=admin_headers,
    )
    assert criado.status_code == 201, criado.text
    fechamento_id = criado.json()["id"]

    lista = client.get("/fechamentos-vendas", headers=func_headers)
    assert lista.status_code == 200
    assert lista.json()[0]["id"] == fechamento_id

    lancamentos = client.get("/lancamentos-caixa", headers=admin_headers).json()
    automatico = next(
        item for item in lancamentos if item["origem"] == "fechamento_venda"
    )
    bloqueado = client.patch(
        f"/lancamentos-caixa/{automatico['id']}",
        json={"descricao": "editado"},
        headers=admin_headers,
    )
    assert bloqueado.status_code == 400


def test_ui_modal_fechamento_e_estado_fechada(client: TestClient) -> None:
    login = client.post(
        "/ui/login",
        data={"username": "admin", "password": "senha"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    admin_headers = {"Authorization": f"Bearer {_token(client, 'admin')}"}
    venda_id, inv_ana, _inv_bia = _seed_api(client, admin_headers)

    pagina = client.get("/ui/vendas")
    assert pagina.status_code == 200
    assert f"/ui/vendas/{venda_id}/fechamento" in pagina.text

    modal = client.get(f"/ui/vendas/{venda_id}/fechamento")
    assert modal.status_code == 200
    assert "Lucro líquido" in modal.text
    assert "Rateio do lucro" in modal.text

    fechado = client.post(
        f"/ui/vendas/{venda_id}/fechamento",
        data={"investidor_id": str(inv_ana), "percentual": "100"},
    )
    assert fechado.status_code == 200
    assert "Fechada" in fechado.text
