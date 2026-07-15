"""Auditoria: leitura (query/count/tabelas) e schema, em SQLite in-memory."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from xtreme_system.auditoria import core as auditoria
from xtreme_system.investidor import core as investidor
from xtreme_system.usuario import core as usuario


def _seed_admin(session: Session) -> usuario.Usuario:
    admin = usuario.Usuario(username="admin", senha_hash="x", papel=usuario.Papel.admin)
    session.add(admin)
    session.flush()
    session.info["usuario_id"] = admin.id
    return admin


def test_query_filtra_por_usuario(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    rows = auditoria.query(db_session, usuario_id=admin.id)
    assert rows
    assert all(r.usuario_id == admin.id for r in rows)
    assert any(r.tabela == "investidor" for r in rows)


def test_query_filtra_por_tabela_e_acao(db_session: Session) -> None:
    _seed_admin(db_session)
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    cria = auditoria.query(db_session, tabela="investidor", tipo_acao="CREATE")
    assert cria
    assert all(r.tabela == "investidor" and r.tipo_acao == "CREATE" for r in cria)
    assert auditoria.query(db_session, tabela="investidor", tipo_acao="DELETE") == []


def test_query_pagina_com_limit_offset(db_session: Session) -> None:
    _seed_admin(db_session)
    for i in range(5):
        investidor.create(db_session, investidor.InvestidorCreate(nome=f"n{i}"))
    page1 = auditoria.query(db_session, limit=2, offset=0)
    page2 = auditoria.query(db_session, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r.id for r in page1}.isdisjoint({r.id for r in page2})


def test_count_bate_com_query_sem_limit(db_session: Session) -> None:
    _seed_admin(db_session)
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    total = auditoria.count(db_session)
    assert total == len(auditoria.query(db_session, limit=10000))


def test_count_respeita_filtros(db_session: Session) -> None:
    admin = _seed_admin(db_session)
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    assert auditoria.count(db_session, usuario_id=admin.id) == len(
        auditoria.query(db_session, usuario_id=admin.id, limit=10000)
    )


def test_tabelas_distintas(db_session: Session) -> None:
    _seed_admin(db_session)
    usuario.create(
        db_session,
        usuario.UsuarioCreate(username="u", senha="s", papel=usuario.Papel.admin),
    )
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    tabs = auditoria.tabelas(db_session)
    assert "usuario" in tabs
    assert "investidor" in tabs
    assert len(tabs) == len(set(tabs))


def test_query_filtra_por_data_de(db_session: Session) -> None:
    _seed_admin(db_session)
    investidor.create(db_session, investidor.InvestidorCreate(nome="X"))
    hoje = datetime.now(tz=UTC).date()
    assert len(auditoria.query(db_session, data_de=hoje)) >= 1
    assert auditoria.query(db_session, data_de=hoje + timedelta(days=10)) == []


def test_auditar_rejeita_usuario_id_none(db_session: Session) -> None:
    with pytest.raises(auditoria.AuditError):
        usuario.create(
            db_session,
            usuario.UsuarioCreate(
                username="sem_autor", senha="s", papel=usuario.Papel.admin
            ),
        )
