from contextlib import suppress
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request

from xtreme_system.database import core


class FakeSession:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {}
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


def _finish_session(session_dep: Any) -> None:
    with suppress(StopIteration):
        next(session_dep)


def _request(method: str) -> Request:
    return Request({"type": "http", "method": method, "path": "/", "headers": []})


def test_get_session_rolls_back_read_only_request(monkeypatch: Any) -> None:
    session = FakeSession()
    monkeypatch.setattr(core, "SessionLocal", lambda: session)
    called = False

    def callback() -> None:
        nonlocal called
        called = True

    request = _request("GET")
    session_dep = core.get_session(request)
    yielded = next(session_dep)
    core.register_post_commit(yielded, callback)

    _finish_session(session_dep)

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closes == 1
    assert called is False


def test_get_session_commits_write_request(monkeypatch: Any) -> None:
    session = FakeSession()
    monkeypatch.setattr(core, "SessionLocal", lambda: session)
    called = False

    def callback() -> None:
        nonlocal called
        called = True

    request = _request("POST")
    session_dep = core.get_session(request)
    yielded = next(session_dep)
    core.register_post_commit(yielded, callback)

    _finish_session(session_dep)

    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.closes == 1
    assert called is True


def test_request_session_commit_failure_returns_error_before_response(
    monkeypatch: Any,
) -> None:
    class FailingCommitSession(FakeSession):
        def commit(self) -> None:
            super().commit()
            raise IntegrityError("", {}, Exception("commit failed"))

    session = FailingCommitSession()
    monkeypatch.setattr(core, "SessionLocal", lambda: session)

    app = FastAPI()

    @app.middleware("http")
    async def database_session(request: Request, call_next: Any) -> Any:
        core.bind_request_session(request)
        try:
            response = await call_next(request)
        except Exception as exc:
            core.finish_request_session(request, exc)
            raise
        core.finish_request_session(request)
        return response

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        try:
            return await call_next(request)
        except Exception:
            return PlainTextResponse("commit failed", status_code=500)

    @app.post("/")
    def create(
        _session: Session = Depends(core.get_session),  # noqa: B008
    ) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app, raise_server_exceptions=False).post("/")

    assert response.status_code == 500
    assert session.commits == 1
    assert session.rollbacks == 1
    assert session.closes == 1


def test_detach_request_session_closes_early_and_skips_finalization(
    monkeypatch: Any,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(core, "SessionLocal", lambda: session)
    request = _request("POST")
    core.bind_request_session(request)

    core.detach_request_session(request)
    core.finish_request_session(request)

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closes == 1
