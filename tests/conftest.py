import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.database import create_test_engine
from xtreme_system.api.core import app
from xtreme_system.api.routes.ui_routes.vendas import _aguardar_contratos_background
from xtreme_system.api.setup import reset_rate_limiters
from xtreme_system.database.core import get_session
from xtreme_system.database.core import invoke_post_commit as run_post_commit_callbacks
from xtreme_system.usuario import core as usuario


def pytest_configure() -> None:
    # Garante segredo JWT em ambientes sem .env (ex.: pre-commit, CI) antes
    # do lru_cache de get_settings() ser populado por qualquer rota de login.
    os.environ.setdefault("AUTH_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("RATE_LIMIT_STORE", "memory")
    if not os.environ.get("TEST_DATABASE_URL") and not os.environ.get(
        "XTREME_ALLOW_SQLITE_TEST_DB"
    ):
        msg = (
            "TEST_DATABASE_URL is required so tests run against an "
            "Alembic-migrated PostgreSQL database. Use `make test` or set "
            "XTREME_ALLOW_SQLITE_TEST_DB=1 for the explicit SQLite fallback."
        )
        raise pytest.UsageError(msg)


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    # limiters são module-level; sem reset um teste consome o limite do
    # próximo (TestClient sempre usa o mesmo IP).
    reset_rate_limiters()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão isolada com schema migrado em Postgres ou SQLite local."""
    engine = create_test_engine()
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with maker() as session:
        yield session
    engine.dispose()


@pytest.fixture
def make_client() -> Iterator[Callable[..., TestClient]]:
    """Fábrica de `TestClient` com `get_session` sobrescrito por uma sessão
    de teste compartilhada, seedando opcionalmente usuários autenticáveis.

    Uso: `make_client(usuarios=[("admin", usuario.Papel.admin)])`. Quando
    `usuarios` é informado, também cria o usuário `seed` (necessário para
    `session.info["usuario_id"]`, usado por auditoria). `invoke_post_commit`
    replica o comportamento de `get_session` real, que dispara callbacks
    de post-commit — necessário para rotas que dependem deles (ex.: envio
    de whatsapp, jobs assíncronos). `seed` recebe a sessão para popular
    dados adicionais (ex.: investidor/veículo) antes do `TestClient` existir.
    """
    engines: list[Engine] = []
    sessions: list[Session] = []

    def _make(
        usuarios: list[tuple[str, usuario.Papel]] | None = None,
        *,
        invoke_post_commit: bool = False,
        client_addr: tuple[str, int] | None = None,
        seed: Callable[[Session], None] | None = None,
        client_kwargs: dict[str, Any] | None = None,
    ) -> TestClient:
        engine = create_test_engine()
        engines.append(engine)
        session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        sessions.append(session)

        if usuarios:
            u = usuario.Usuario(
                username="seed", senha_hash="x", papel=usuario.Papel.admin
            )
            session.add(u)
            session.flush()
            session.info["usuario_id"] = u.id
            for username, papel in usuarios:
                existing = usuario.get_by_username(session, username)
                if existing is None:
                    usuario.create(
                        session,
                        usuario.UsuarioCreate(
                            username=username, senha="senha", papel=papel
                        ),
                    )
                else:
                    existing.papel = papel
                    usuario.change_password(session, existing, "senha")

        if seed is not None:
            seed(session)

        def override() -> Iterator[Session]:
            yield session
            if invoke_post_commit:
                run_post_commit_callbacks(session)
                _aguardar_contratos_background()

        app.dependency_overrides[get_session] = override
        kwargs = dict(client_kwargs or {})
        if client_addr is not None:
            kwargs.setdefault("client", client_addr)

        class ManagedTestClient(TestClient):
            def __exit__(self, *args: Any) -> None:
                try:
                    super().__exit__(*args)
                finally:
                    _aguardar_contratos_background()
                    session.close()
                    engine.dispose()

        return ManagedTestClient(app, **kwargs)

    yield _make

    app.dependency_overrides.clear()
    for session in sessions:
        session.close()
    for engine in engines:
        engine.dispose()
