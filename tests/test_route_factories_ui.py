"""Prova que register_ui_simples recebe Jinja2Templates como parâmetro (não mais
o singleton global de deps.py) — permite registrar rotas com templates de stub."""

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.database import create_test_engine
from xtreme_system.api.crud_ui.query import query_list, sorted_list
from xtreme_system.api.deps import get_ui_user
from xtreme_system.api.route_factories import (
    _sort_key,
    register_crud_ui_routes,
    register_ui_simples,
)
from xtreme_system.api.routes.ui_routes.investidores import (
    MetricasInvestidor,
    ordenar_investidores,
)
from xtreme_system.database.core import get_session
from xtreme_system.documento_veiculo import core as _documento_veiculo  # noqa: F401
from xtreme_system.imagem_veiculo import core as _imagem_veiculo  # noqa: F401
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario


def test_register_ui_simples_aceita_templates_injetado(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    for nome, conteudo in {
        "simples.html": "<p>{{ itens | length }} itens</p>",
        "_linhas_simples.html": "<p>linhas</p>",
        "_form_simples.html": "<p>form</p>",
        "_simples_ok.html": "<p>ok</p>",
    }.items():
        (tmp_path / nome).write_text(conteudo)
    stub_templates = Jinja2Templates(directory=tmp_path)

    engine = create_test_engine()
    request.addfinalizer(engine.dispose)
    session = sessionmaker(bind=engine)()
    request.addfinalizer(session.close)
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    session.add(u)
    session.flush()
    session.info["usuario_id"] = u.id
    admin = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="admin", senha="senha", papel=usuario.Papel.admin
        ),
    )

    app = FastAPI()
    register_ui_simples(
        app,
        stub_templates,
        "/ui/investidores",
        "Investidores",
        investidor,
        investidor.InvestidorCreate,
        investidor.InvestidorUpdate,
        "investidores.csv",
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ui_user] = lambda: admin

    resp = TestClient(app).get("/ui/investidores")

    assert resp.status_code == 200
    assert "0 itens" in resp.text


class _FailAfterWriteModule:
    def list_all(
        self, session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[investidor.Investidor]:
        return investidor.list_all(session, limit=limit, offset=offset)

    def get(self, session: Session, item_id: int) -> investidor.Investidor | None:
        return investidor.get(session, item_id)

    def create(
        self,
        session: Session,
        data: investidor.InvestidorCreate,
        actor_id: int | None = None,
    ) -> investidor.Investidor:
        investidor.create(session, data, actor_id)
        raise IntegrityError("", {}, Exception())

    def update(
        self,
        session: Session,
        obj: investidor.Investidor,
        data: investidor.InvestidorUpdate,
        actor_id: int | None = None,
    ) -> investidor.Investidor:
        investidor.update(session, obj, data, actor_id)
        raise IntegrityError("", {}, Exception())

    def delete(
        self, session: Session, obj: investidor.Investidor, actor_id: int | None = None
    ) -> None:
        investidor.delete(session, obj, actor_id)
        raise IntegrityError("", {}, Exception())


def test_register_ui_simples_rolls_back_when_write_fails_late(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    for nome, conteudo in {
        "simples.html": "<p>{{ itens | length }} itens</p>",
        "_linhas_simples.html": "<p>linhas</p>",
        "_form_simples.html": "<p>form</p>",
        "_simples_ok.html": "<p>ok</p>",
    }.items():
        (tmp_path / nome).write_text(conteudo)
    stub_templates = Jinja2Templates(directory=tmp_path)

    engine = create_test_engine()
    request.addfinalizer(engine.dispose)
    session = sessionmaker(bind=engine)()
    request.addfinalizer(session.close)
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    session.add(u)
    session.flush()
    session.info["usuario_id"] = u.id
    admin = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="admin", senha="senha", papel=usuario.Papel.admin
        ),
    )

    app = FastAPI()
    register_ui_simples(
        app,
        stub_templates,
        "/ui/investidores",
        "Investidores",
        _FailAfterWriteModule(),
        investidor.InvestidorCreate,
        investidor.InvestidorUpdate,
        "investidores.csv",
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ui_user] = lambda: admin

    resp = TestClient(app).post("/ui/investidores", data={"nome": "Ana"})

    assert resp.status_code == 409
    assert investidor.list_all(session) == []


def test_sort_key_nulls() -> None:
    """Nullable fields sort deterministically without crashing mixed lists."""
    assert _sort_key(None) == ""

    # None sorts before non-empty strings; original items preserved in output
    items = ["Z", None, "a", None, "M"]
    assert sorted(items, key=_sort_key) == [None, None, "a", "M", "Z"]

    # Existing behaviors preserved
    assert _sort_key("  ABC  ") == "  abc  "
    assert _sort_key(42) == 42
    assert _sort_key(True) is True
    assert _sort_key(Decimal("1.50")) == Decimal("1.50")
    assert _sort_key("") == ""


class _SortableItem:
    def __init__(self, nome: str, status: str, prioridade: int) -> None:
        self.nome = nome
        self.status = status
        self.prioridade = prioridade


def test_sorted_list_aceita_sort_multicampo() -> None:
    itens = [
        _SortableItem("Carla", "ativo", 2),
        _SortableItem("Bruno", "pendente", 1),
        _SortableItem("Ana", "ativo", 3),
    ]

    ordenados = sorted_list(
        itens,
        "status_nome",
        "asc",
        {
            "status_nome": lambda item: (_sort_key(item.status), _sort_key(item.nome)),
        },
    )

    assert [item.nome for item in ordenados] == ["Ana", "Carla", "Bruno"]


def test_sorted_list_aplica_desc() -> None:
    itens = [
        _SortableItem("Ana", "ativo", 1),
        _SortableItem("Bruno", "ativo", 3),
        _SortableItem("Carla", "ativo", 2),
    ]

    ordenados = sorted_list(
        itens,
        "prioridade",
        "desc",
        {"prioridade": "prioridade"},
    )

    assert [item.prioridade for item in ordenados] == [3, 2, 1]


def test_sorted_list_sem_spec_retorna_lista_original() -> None:
    itens = [
        _SortableItem("Ana", "ativo", 1),
        _SortableItem("Bruno", "ativo", 3),
    ]

    ordenados = sorted_list(itens, "inexistente", "asc", {})

    assert ordenados is itens


def test_query_list_nao_mascara_typeerror_do_search_func() -> None:
    def search_func(_session: Session, _term: str) -> list[investidor.Investidor]:
        raise TypeError("bug interno")

    with pytest.raises(TypeError, match="bug interno"):
        query_list(
            session=cast(Session, object()),
            module=investidor,
            q="ana",
            searchable=False,
            list_func=None,
            search_func=search_func,
        )


def test_query_list_passa_limit_e_offset_para_list_func_paginal() -> None:
    chamadas: list[tuple[int | None, int]] = []

    def list_func(
        _session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[investidor.Investidor]:
        chamadas.append((limit, offset))
        dados = [
            investidor.Investidor(id=1, nome="Ana"),
            investidor.Investidor(id=2, nome="Bruno"),
            investidor.Investidor(id=3, nome="Carla"),
            investidor.Investidor(id=4, nome="Davi"),
        ]
        return dados[offset : offset + limit] if limit is not None else dados[offset:]

    resultados = query_list(
        session=cast(Session, object()),
        module=investidor,
        q="",
        searchable=False,
        list_func=list_func,
        search_func=None,
        limit=2,
        offset=1,
    )

    assert chamadas == [(2, 1)]
    assert [item.nome for item in resultados] == ["Bruno", "Carla"]


def test_ordenar_investidores_por_nome() -> None:
    investidores = [
        investidor.Investidor(id=1, nome="Carla"),
        investidor.Investidor(id=2, nome="ana"),
        investidor.Investidor(id=3, nome="Bruno"),
    ]

    ordenados = ordenar_investidores(investidores, {}, "nome", "asc")

    assert [item.nome for item in ordenados] == ["ana", "Bruno", "Carla"]

    ordenados_desc = ordenar_investidores(investidores, {}, "nome", "desc")

    assert [item.nome for item in ordenados_desc] == ["Carla", "Bruno", "ana"]


def test_ordenar_investidores_por_metricas() -> None:
    investidores = [
        investidor.Investidor(id=1, nome="Ana"),
        investidor.Investidor(id=2, nome="Bruno"),
        investidor.Investidor(id=3, nome="Carla"),
    ]
    metricas = {
        1: MetricasInvestidor(
            saldo=Decimal("10.00"),
            num_veiculos=2,
            valor_veiculos=Decimal("5000.00"),
            total_aportado=Decimal("200.00"),
        ),
        2: MetricasInvestidor(
            saldo=Decimal("30.00"),
            num_veiculos=1,
            valor_veiculos=Decimal("1000.00"),
            total_aportado=Decimal("700.00"),
        ),
        3: MetricasInvestidor(
            saldo=Decimal("20.00"),
            num_veiculos=3,
            valor_veiculos=Decimal("3000.00"),
            total_aportado=Decimal("400.00"),
        ),
    }

    assert [
        item.id for item in ordenar_investidores(investidores, metricas, "saldo", "asc")
    ] == [1, 3, 2]
    assert [
        item.id
        for item in ordenar_investidores(investidores, metricas, "saldo", "desc")
    ] == [2, 3, 1]
    assert [
        item.id
        for item in ordenar_investidores(investidores, metricas, "num_veiculos", "asc")
    ] == [2, 1, 3]
    assert [
        item.id
        for item in ordenar_investidores(investidores, metricas, "num_veiculos", "desc")
    ] == [3, 1, 2]
    assert [
        item.id
        for item in ordenar_investidores(
            investidores, metricas, "valor_veiculos", "asc"
        )
    ] == [2, 3, 1]
    assert [
        item.id
        for item in ordenar_investidores(
            investidores, metricas, "valor_veiculos", "desc"
        )
    ] == [1, 3, 2]
    assert [
        item.id
        for item in ordenar_investidores(
            investidores, metricas, "total_investido", "asc"
        )
    ] == [1, 3, 2]
    assert [
        item.id
        for item in ordenar_investidores(
            investidores, metricas, "total_investido", "desc"
        )
    ] == [2, 3, 1]


def test_ordenar_investidores_usa_metricas_padrao_quando_ausentes() -> None:
    investidores = [
        investidor.Investidor(id=1, nome="Ana"),
        investidor.Investidor(id=2, nome="Bruno"),
        investidor.Investidor(id=3, nome="Carla"),
    ]
    metricas = {
        1: MetricasInvestidor(saldo=Decimal("10.00")),
        3: MetricasInvestidor(saldo=Decimal("5.00")),
    }

    ordenados_asc = ordenar_investidores(investidores, metricas, "saldo", "asc")
    ordenados_desc = ordenar_investidores(investidores, metricas, "saldo", "desc")

    assert [item.id for item in ordenados_asc] == [2, 3, 1]
    assert [item.id for item in ordenados_desc] == [1, 3, 2]


class _StubSchema(BaseModel):
    nome: str | None = None


class _StubItem:
    def __init__(self, item_id: int, nome: str) -> None:
        self.id = item_id
        self.nome = nome


class _ConflictModule:
    def __init__(self, *, fail_on: str) -> None:
        self.fail_on = fail_on
        self.item = _StubItem(1, "Original")

    def list_all(
        self, _session: Session, *, limit: int | None = None, offset: int = 0
    ) -> list[_StubItem]:
        return (
            [self.item][offset : offset + limit]
            if limit is not None
            else [self.item][offset:]
        )

    def get(self, _session: Session, item_id: int) -> _StubItem | None:
        return self.item if item_id == self.item.id else None

    def create(
        self, _session: Session, _data: Any, _actor_id: int | None = None
    ) -> _StubItem:
        if self.fail_on == "create":
            raise IntegrityError("", {}, Exception())
        return self.item

    def update(
        self,
        _session: Session,
        obj: _StubItem,
        _data: Any,
        _actor_id: int | None = None,
    ) -> _StubItem:
        if self.fail_on == "update":
            raise IntegrityError("", {}, Exception())
        return obj

    def delete(
        self, _session: Session, _obj: _StubItem, _actor_id: int | None = None
    ) -> None:
        if self.fail_on == "delete":
            raise IntegrityError("", {}, Exception())


def _stub_crud_client(
    tmp_path: Path,
    module: _ConflictModule,
    request: pytest.FixtureRequest,
    *,
    before_create: Callable[[Session, Any], None] | None = None,
) -> TestClient:
    for nome, conteudo in {
        "lista.html": "<div id='linhas'>{% include 'linhas.html' %}</div>",
        "linhas.html": "{% if erro %}<p>{{ erro }}</p>{% endif %}"
        "{% for item in itens %}<p>{{ item.nome }}</p>{% endfor %}",
        "ok.html": "<p>ok</p>",
        "form.html": "{% if erro %}<p>{{ erro }}</p>{% endif %}",
    }.items():
        (tmp_path / nome).write_text(conteudo)

    templates = Jinja2Templates(directory=tmp_path)
    engine = create_test_engine()
    request.addfinalizer(engine.dispose)
    session = sessionmaker(bind=engine)()
    request.addfinalizer(session.close)
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    session.add(u)
    session.flush()
    session.info["usuario_id"] = u.id
    admin = usuario.create(
        session,
        usuario.UsuarioCreate(
            username="admin", senha="senha", papel=usuario.Papel.admin
        ),
    )

    app = FastAPI()
    register_crud_ui_routes(
        app,
        templates,
        module,
        "/ui/stubs",
        "Stub",
        create_schema=_StubSchema,
        update_schema=_StubSchema,
        list_key="itens",
        item_key="item",
        list_template="lista.html",
        list_partial_template="linhas.html",
        ok_partial_template="ok.html",
        form_template="form.html",
        sort_fields={},
        before_create=before_create,
        csv_filename="stubs.csv",
        csv_headers=["ID", "Nome"],
        csv_row=lambda item: [item.id, item.nome],
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ui_user] = lambda: admin
    return TestClient(app)


def test_crud_ui_create_integrity_error_retorna_409(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="create"), request)

    resp = client.post("/ui/stubs", data={"nome": "Duplicado"})

    assert resp.status_code == 409
    assert "Stub já existe" in resp.text


def test_crud_ui_create_integrity_error_before_create_maintains_session(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    def fail_before_create(_session: Session, _data: _StubSchema) -> None:
        raise IntegrityError("", {}, Exception())

    client = _stub_crud_client(
        tmp_path,
        _ConflictModule(fail_on="none"),
        request,
        before_create=fail_before_create,
    )

    resp = client.post("/ui/stubs", data={"nome": "Duplicado"})

    assert resp.status_code == 409
    assert "Stub já existe" in resp.text
    assert client.get("/ui/stubs").status_code == 200


def test_crud_ui_update_integrity_error_retorna_409(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="update"), request)

    resp = client.post("/ui/stubs/1", data={"nome": "Duplicado"})

    assert resp.status_code == 409
    assert "Stub já existe" in resp.text


def test_crud_ui_delete_integrity_error_retorna_409(
    tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="delete"), request)

    resp = client.post("/ui/stubs/1/excluir")

    assert resp.status_code == 409
    assert "Stub possui registros vinculados" in resp.text
    assert "Original" in resp.text
