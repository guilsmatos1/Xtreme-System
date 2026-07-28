import pytest
from sqlalchemy.engine import Engine

from xtreme_system.database import connection


def test_engine_is_created_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    connection.get_engine.cache_clear()
    connection.get_session_factory.cache_clear()
    calls = 0

    def create_test_engine(*_args: object, **_kwargs: object) -> Engine:
        nonlocal calls
        calls += 1
        raise AssertionError("engine creation should be deferred")

    monkeypatch.setattr(connection, "create_engine", create_test_engine)

    assert calls == 0

    with pytest.raises(AssertionError, match="engine creation should be deferred"):
        connection.get_engine()
