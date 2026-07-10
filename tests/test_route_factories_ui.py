"""Prova que register_ui_simples recebe Jinja2Templates como parâmetro (não mais
o singleton global de deps.py) — permite registrar rotas com templates de stub."""

from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from xtreme_system.api.deps import get_ui_user
from xtreme_system.api.route_factories import _sort_key, register_ui_simples
from xtreme_system.database.core import Base, get_session
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

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
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
