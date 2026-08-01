from typing import cast

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from xtreme_system.database import connection


def test_engine_is_created_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    connection.clear_engine_cache()
    calls = 0

    def create_test_engine(*_args: object, **_kwargs: object) -> Engine:
        nonlocal calls
        calls += 1
        raise AssertionError("engine creation should be deferred")

    monkeypatch.setattr(connection, "create_engine", create_test_engine)

    assert calls == 0

    with pytest.raises(AssertionError, match="engine creation should be deferred"):
        connection.get_engine()


class _FakeConnection:
    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeEngine:
    def __init__(self, *, fail_first_connection: bool = False) -> None:
        self.connect_calls = 0
        self.disposed = False
        self._fail_first_connection = fail_first_connection

    def connect(self) -> _FakeConnection:
        self.connect_calls += 1
        if self._fail_first_connection and self.connect_calls == 1:
            raise OperationalError("SELECT 1", {}, RuntimeError("unreachable"))
        return _FakeConnection()

    def dispose(self) -> None:
        self.disposed = True


def test_engine_retries_primary_after_transient_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection.clear_engine_cache()
    settings = type(
        "Settings",
        (),
        {
            "database_url": "postgresql://primary",
            "database_url_fallback": "postgresql://fallback",
        },
    )()
    engines: dict[str, _FakeEngine] = {}

    def create_test_engine(database_url: str, **_kwargs: object) -> Engine:
        engine = _FakeEngine(fail_first_connection=database_url.endswith("primary"))
        engines[database_url] = engine
        return cast(Engine, engine)

    monkeypatch.setattr(connection, "get_settings", lambda: settings)
    monkeypatch.setattr(connection, "create_engine", create_test_engine)

    assert connection.get_engine() is cast(Engine, engines["postgresql://fallback"])
    assert connection.get_database_target() == "fallback"
    assert connection.get_engine() is cast(Engine, engines["postgresql://primary"])
    assert connection.get_database_target() == "primary"
    assert engines["postgresql://primary"].connect_calls == 2
    assert engines["postgresql://fallback"].connect_calls == 1
    assert engines["postgresql://fallback"].disposed

    connection.clear_engine_cache()


def test_engine_fails_fast_when_fallback_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection.clear_engine_cache()
    settings = type(
        "Settings",
        (),
        {
            "database_url": "postgresql://primary",
            "database_url_fallback": "postgresql://fallback",
        },
    )()
    engines: dict[str, _FakeEngine] = {}

    def create_test_engine(database_url: str, **_kwargs: object) -> Engine:
        engine = _FakeEngine(fail_first_connection=True)
        engines[database_url] = engine
        return cast(Engine, engine)

    monkeypatch.setattr(connection, "get_settings", lambda: settings)
    monkeypatch.setattr(connection, "create_engine", create_test_engine)

    with pytest.raises(OperationalError):
        connection.get_engine()

    assert connection.get_database_target() == "primary"
    assert engines["postgresql://fallback"].connect_calls == 1
    assert engines["postgresql://fallback"].disposed

    connection.clear_engine_cache()
