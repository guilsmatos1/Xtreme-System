import pytest

from xtreme_system.api.setup import _docs_url


def test_docs_are_enabled_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")

    assert _docs_url() == "/docs"


def test_docs_are_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert _docs_url() is None
