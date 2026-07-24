from unittest.mock import MagicMock

import pytest
import structlog
from fastapi.testclient import TestClient

from xtreme_system.api import setup
from xtreme_system.api.core import app


@app.get("/__test_unhandled_error")
def _test_unhandled_error() -> None:
    raise RuntimeError("boom")


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
