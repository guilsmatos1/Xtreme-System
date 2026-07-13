from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.database import create_test_engine
from xtreme_system.api.deps import get_current_user, require_admin
from xtreme_system.api.route_factories import register_crud_routes
from xtreme_system.database.core import get_session
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario


@pytest.fixture
def atomic_client() -> Iterator[tuple[TestClient, FastAPI, Session]]:
    engine = create_test_engine()
    app = FastAPI()
    with Session(engine) as session:
        admin = usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )

        def override_session() -> Iterator[Session]:
            yield session

        def override_user() -> usuario.Usuario:
            return admin

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[require_admin] = override_user
        yield TestClient(app, raise_server_exceptions=False), app, session
    engine.dispose()


def test_json_create_rolls_back_when_after_create_fails(
    atomic_client: tuple[TestClient, FastAPI, Session],
) -> None:
    client, app, session = atomic_client

    def fail_after_create(_session: Session, _obj: object) -> None:
        raise RuntimeError("hook failed")

    register_crud_routes(
        app,
        investidor,
        "/atomic-create-investidores",
        "Investidor",
        read_schema=investidor.InvestidorRead,
        create_schema=investidor.InvestidorCreate,
        update_schema=investidor.InvestidorUpdate,
        after_create=fail_after_create,
    )

    resp = client.post("/atomic-create-investidores", json={"nome": "Ana"})

    assert resp.status_code == 500
    assert investidor.list_all(session) == []


def test_json_update_rolls_back_when_after_update_fails(
    atomic_client: tuple[TestClient, FastAPI, Session],
) -> None:
    client, app, session = atomic_client
    existing = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))

    def fail_after_update(_session: Session, _obj: object) -> None:
        raise RuntimeError("hook failed")

    register_crud_routes(
        app,
        investidor,
        "/atomic-update-investidores",
        "Investidor",
        read_schema=investidor.InvestidorRead,
        create_schema=investidor.InvestidorCreate,
        update_schema=investidor.InvestidorUpdate,
        after_update=fail_after_update,
    )

    resp = client.patch(
        f"/atomic-update-investidores/{existing.id}", json={"nome": "Bia"}
    )

    assert resp.status_code == 500
    assert investidor.get(session, existing.id).nome == "Ana"  # type: ignore[union-attr]


def test_json_delete_rolls_back_when_before_delete_fails_after_writes(
    atomic_client: tuple[TestClient, FastAPI, Session],
) -> None:
    client, app, session = atomic_client
    existing = investidor.create(session, investidor.InvestidorCreate(nome="Ana"))

    def fail_before_delete(session: Session, _obj: object) -> None:
        investidor.create(session, investidor.InvestidorCreate(nome="Bia"))
        raise RuntimeError("hook failed")

    register_crud_routes(
        app,
        investidor,
        "/atomic-delete-investidores",
        "Investidor",
        read_schema=investidor.InvestidorRead,
        create_schema=investidor.InvestidorCreate,
        update_schema=investidor.InvestidorUpdate,
        before_delete=fail_before_delete,
    )

    resp = client.delete(f"/atomic-delete-investidores/{existing.id}")

    assert resp.status_code == 500
    assert [obj.nome for obj in investidor.list_all(session)] == ["Ana"]
