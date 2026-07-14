"""Prova que register_ui_simples recebe Jinja2Templates como parâmetro (não mais
o singleton global de deps.py) — permite registrar rotas com templates de stub."""

from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.database import create_test_engine
from xtreme_system.api.deps import get_ui_user
from xtreme_system.api.route_factories import (
    _sort_key,
    register_crud_ui_routes,
    register_ui_simples,
)
from xtreme_system.database.core import get_session
from xtreme_system.documento_veiculo import core as _documento_veiculo  # noqa: F401
from xtreme_system.imagem_veiculo import core as _imagem_veiculo  # noqa: F401
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario


def test_register_ui_simples_aceita_templates_injetado(tmp_path: Path) -> None:
    for nome, conteudo in {
        "simples.html": "<p>{{ itens | length }} itens</p>",
        "_linhas_simples.html": "<p>linhas</p>",
        "_form_simples.html": "<p>form</p>",
        "_simples_ok.html": "<p>ok</p>",
    }.items():
        (tmp_path / nome).write_text(conteudo)
    stub_templates = Jinja2Templates(directory=tmp_path)

    engine = create_test_engine()
    session = sessionmaker(bind=engine)()
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
    def list_all(self, session: Session) -> list[investidor.Investidor]:
        return investidor.list_all(session)

    def get(self, session: Session, item_id: int) -> investidor.Investidor | None:
        return investidor.get(session, item_id)

    def create(
        self, session: Session, data: investidor.InvestidorCreate
    ) -> investidor.Investidor:
        investidor.create(session, data)
        raise IntegrityError("", {}, Exception())

    def update(
        self,
        session: Session,
        obj: investidor.Investidor,
        data: investidor.InvestidorUpdate,
    ) -> investidor.Investidor:
        investidor.update(session, obj, data)
        raise IntegrityError("", {}, Exception())

    def delete(self, session: Session, obj: investidor.Investidor) -> None:
        investidor.delete(session, obj)
        raise IntegrityError("", {}, Exception())


def test_register_ui_simples_rolls_back_when_write_fails_late(
    tmp_path: Path,
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
    session = sessionmaker(bind=engine)()
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

    def list_all(self, _session: Session) -> list[_StubItem]:
        return [self.item]

    def get(self, _session: Session, item_id: int) -> _StubItem | None:
        return self.item if item_id == self.item.id else None

    def create(self, _session: Session, _data: Any) -> _StubItem:
        if self.fail_on == "create":
            raise IntegrityError("", {}, Exception())
        return self.item

    def update(self, _session: Session, obj: _StubItem, _data: Any) -> _StubItem:
        if self.fail_on == "update":
            raise IntegrityError("", {}, Exception())
        return obj

    def delete(self, _session: Session, _obj: _StubItem) -> None:
        if self.fail_on == "delete":
            raise IntegrityError("", {}, Exception())


def _stub_crud_client(tmp_path: Path, module: _ConflictModule) -> TestClient:
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
    session = sessionmaker(bind=engine)()
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
        csv_filename="stubs.csv",
        csv_headers=["ID", "Nome"],
        csv_row=lambda item: [item.id, item.nome],
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ui_user] = lambda: admin
    return TestClient(app)


def test_crud_ui_create_integrity_error_retorna_409(tmp_path: Path) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="create"))

    resp = client.post("/ui/stubs", data={"nome": "Duplicado"})

    assert resp.status_code == 409
    assert "Stub já existe" in resp.text


def test_crud_ui_update_integrity_error_retorna_409(tmp_path: Path) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="update"))

    resp = client.post("/ui/stubs/1", data={"nome": "Duplicado"})

    assert resp.status_code == 409
    assert "Stub já existe" in resp.text


def test_crud_ui_delete_integrity_error_retorna_409(tmp_path: Path) -> None:
    client = _stub_crud_client(tmp_path, _ConflictModule(fail_on="delete"))

    resp = client.post("/ui/stubs/1/excluir")

    assert resp.status_code == 409
    assert "Stub possui registros vinculados" in resp.text
    assert "Original" in resp.text
