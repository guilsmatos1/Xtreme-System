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
    assert perfil.pode_acessar(admin, "compras")
    assert perfil.pode_acessar(admin, "custos-veiculos")


def test_vendedor_sem_perfil_nao_acessa_nada(db_session: Session) -> None:
    vendedor = _usuario(db_session, usuario.Papel.funcionario, None)
    assert not perfil.pode_acessar(vendedor, "veiculos")


def test_vendedor_acessa_apenas_paginas_do_seu_perfil(db_session: Session) -> None:
    leitor = perfil.Perfil(
        nome="Leitor", paginas=["veiculos", "clientes", "compras", "custos-veiculos"]
    )
    db_session.add(leitor)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, leitor)
    assert perfil.pode_acessar(vendedor, "veiculos")
    assert perfil.pode_acessar(vendedor, "clientes")
    assert perfil.pode_acessar(vendedor, "compras")
    assert perfil.pode_acessar(vendedor, "custos-veiculos")
    assert not perfil.pode_acessar(vendedor, "vendas")


def test_delete_desvincula_usuarios_do_perfil(db_session: Session) -> None:
    u = usuario.Usuario(username="seed", senha_hash="x", papel=usuario.Papel.admin)
    db_session.add(u)
    db_session.flush()
    db_session.info["usuario_id"] = u.id
    leitor = perfil.Perfil(nome="Leitor", paginas=["veiculos"])
    db_session.add(leitor)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, leitor)

    perfil.delete(db_session, leitor)

    db_session.refresh(vendedor)
    assert vendedor.perfil_id is None
    assert perfil.list_all(db_session) == []


def test_pagina_da_rota_extrai_apenas_paginas_conhecidas() -> None:
    assert perfil.pagina_da_rota("/ui/veiculos") == "veiculos"
    assert perfil.pagina_da_rota("/ui/veiculos/1/imagens") == "veiculos"
    assert perfil.pagina_da_rota("/ui/compras/1/comprovantes") == "compras"
    assert perfil.pagina_da_rota("/ui/custos-veiculos") == "custos-veiculos"
    assert perfil.pagina_da_rota("/ui/usuarios") is None
    assert perfil.pagina_da_rota("/ui/dashboard") is None
    assert perfil.pagina_da_rota("/static/app.css") is None
