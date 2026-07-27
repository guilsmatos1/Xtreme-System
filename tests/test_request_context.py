from unittest.mock import MagicMock

import pytest
import structlog
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api import setup
from xtreme_system.api.core import app
from xtreme_system.database import core as database_core


@app.get("/__test_unhandled_error")
def _test_unhandled_error() -> None:
    raise RuntimeError("boom")


@app.post("/__test_commit_failure")
def _test_commit_failure(
    _session: Session = Depends(database_core.get_session),  # noqa: B008
) -> dict[str, bool]:
    return {"ok": True}


class _FailingCommitSession:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1
        raise IntegrityError("", {}, Exception("commit falhou"))

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


def test_unhandled_error_logs_once_cleans_context_and_keeps_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_exception = MagicMock()
    monkeypatch.setattr(setup.logger, "exception", log_exception)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(
        "/__test_unhandled_error", headers={"X-Request-ID": "req-test-123"}
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-test-123"
    assert log_exception.call_count == 1
    assert "request_id" not in structlog.contextvars.get_contextvars()


def test_commit_failure_returns_error_before_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FailingCommitSession()
    monkeypatch.setattr(database_core, "SessionLocal", lambda: session)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/__test_commit_failure", headers={"X-Request-ID": "req-test-commit"}
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-test-commit"
    assert response.json() == {"detail": "Erro interno do servidor"}
    assert session.commits == 1
    assert session.rollbacks == 1
    assert session.closes == 1
