"""Bootstrap do primeiro admin."""

import sys

import pytest
from development import create_admin
from sqlalchemy.orm import sessionmaker

from tests.database import create_test_engine
from xtreme_system.auditoria import core as auditoria
from xtreme_system.usuario import core as usuario


def test_main_cria_admin_inicial_e_comita(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine = create_test_engine()
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(create_admin, "SessionLocal", session_factory)
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "admin", "senha"])

    create_admin.main()

    out = capsys.readouterr().out
    assert "admin criado: id=" in out

    with session_factory() as session:
        user = usuario.get_by_username(session, "admin")
        assert user is not None
        audit = session.query(auditoria.Auditoria).one()
        assert audit.usuario_id == user.id
        assert audit.registro_id == user.id

    engine.dispose()
