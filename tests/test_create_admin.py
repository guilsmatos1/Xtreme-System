"""Bootstrap do primeiro admin."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from development import create_admin
from sqlalchemy.orm import sessionmaker

from tests.database import create_test_engine
from xtreme_system.auditoria import core as auditoria
from xtreme_system.auth import core as auth
from xtreme_system.usuario import core as usuario


def _load_seed_default_admin_migration() -> Any:
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "ab12cd34ef56_seed_default_admin.py"
    )
    spec = importlib.util.spec_from_file_location("seed_default_admin", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_migration_cria_admin_padrao_quando_nao_existe() -> None:
    engine = create_test_engine()
    migration = _load_seed_default_admin_migration()

    with engine.begin() as connection:
        migration._ensure_default_admin(connection)  # noqa: SLF001
        migration._ensure_default_admin(connection)  # noqa: SLF001

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        user = usuario.get_by_username(session, "admin")
        assert user is not None
        assert user.papel == usuario.Papel.admin
        assert user.ativo is True
        assert auth.verify_password("admin", user.senha_hash)
        assert len(usuario.list_all(session)) == 1

    engine.dispose()
