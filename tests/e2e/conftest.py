import socket
import threading
from collections.abc import Iterator
from contextlib import closing

import pytest
import uvicorn
from sqlalchemy.orm import Session, sessionmaker
from tests.database import create_test_engine

from xtreme_system.api.core import app
from xtreme_system.database.core import get_session
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object]) -> dict[str, object]:
    return {
        **browser_context_args,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
    }


@pytest.fixture
def live_server_url() -> Iterator[str]:
    engine = create_test_engine()
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with maker() as session:
        usuario.create(
            session,
            usuario.UsuarioCreate(
                username="admin", senha="senha", papel=usuario.Papel.admin
            ),
        )
        inv = investidor.create(
            session, investidor.InvestidorCreate(nome="Investidor A")
        )
        veiculo.create(
            session,
            veiculo.VeiculoCreate(
                tipo=veiculo.TipoVeiculo.carro,
                modelo="Onix",
                cor="Prata",
                ano=2024,
                placa="ABC1234",
                km=12000,
                preco=85000,
                investidor_id=inv.id,
            ),
        )

    def override() -> Iterator[Session]:
        with maker() as session:
            yield session

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)

    app.dependency_overrides[get_session] = override
    thread.start()
    try:
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("Servidor E2E falhou ao iniciar")
            threading.Event().wait(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        app.dependency_overrides.clear()
        engine.dispose()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
