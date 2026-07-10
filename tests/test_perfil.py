"""Perfil de permissões: acesso por página."""

from sqlalchemy.orm import Session

from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario


def _usuario(
    session: Session, papel: usuario.Papel, perfil_obj: perfil.Perfil | None
) -> usuario.Usuario:
    obj = usuario.Usuario(
        username=f"user-{papel.value}-{id(perfil_obj)}",
        senha_hash="x",
        papel=papel,
        perfil=perfil_obj,
    )
    session.add(obj)
    session.flush()
    return obj


def test_admin_acessa_qualquer_pagina_mesmo_sem_perfil(db_session: Session) -> None:
    admin = _usuario(db_session, usuario.Papel.admin, None)
    assert perfil.pode_acessar(admin, "veiculos")
    assert perfil.pode_acessar(admin, "clientes")


def test_vendedor_sem_perfil_nao_acessa_nada(db_session: Session) -> None:
    vendedor = _usuario(db_session, usuario.Papel.vendedor, None)
    assert not perfil.pode_acessar(vendedor, "veiculos")


def test_vendedor_acessa_apenas_paginas_do_seu_perfil(db_session: Session) -> None:
    leitor = perfil.Perfil(nome="Leitor", paginas=["veiculos", "clientes"])
    db_session.add(leitor)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.vendedor, leitor)
    assert perfil.pode_acessar(vendedor, "veiculos")
    assert perfil.pode_acessar(vendedor, "clientes")
    assert not perfil.pode_acessar(vendedor, "vendas")


def test_pagina_da_rota_extrai_apenas_paginas_conhecidas() -> None:
    assert perfil._pagina_da_rota("/ui/veiculos") == "veiculos"
    assert perfil._pagina_da_rota("/ui/veiculos/1/imagens") == "veiculos"
    assert perfil._pagina_da_rota("/ui/usuarios") is None
    assert perfil._pagina_da_rota("/ui/dashboard") is None
    assert perfil._pagina_da_rota("/static/app.css") is None
