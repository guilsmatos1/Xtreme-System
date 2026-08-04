"""Perfil de permissões: acesso por página."""

from sqlalchemy.orm import Session

from xtreme_system.auditoria import core as auditoria
from xtreme_system.perfil import core as perfil
from xtreme_system.usuario import core as usuario
from xtreme_system.venda import core as venda


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

    perfil.delete(db_session, leitor, u.id)

    db_session.refresh(vendedor)
    assert vendedor.perfil_id is None
    assert perfil.list_all(db_session) == []
    rows = auditoria.query(db_session, tabela="usuario", tipo_acao="UPDATE")
    assert len(rows) == 1
    assert rows[0].registro_id == vendedor.id
    assert rows[0].usuario_id == u.id
    assert rows[0].dados_antes is not None
    assert rows[0].dados_depois is not None
    assert rows[0].dados_antes["perfil_id"] == leitor.id
    assert rows[0].dados_depois["perfil_id"] is None


def test_admin_ve_todos_campos_e_operacoes_mesmo_sem_perfil(
    db_session: Session,
) -> None:
    admin = _usuario(db_session, usuario.Papel.admin, None)
    assert perfil.pode_ver_campo(admin, "veiculos", "preco")
    assert perfil.pode_operacao(admin, "veiculos", "excluir")


def test_sem_perfil_campos_e_operacoes_negados(db_session: Session) -> None:
    vendedor = _usuario(db_session, usuario.Papel.funcionario, None)
    assert not perfil.pode_ver_campo(vendedor, "veiculos", "preco")
    assert not perfil.pode_operacao(vendedor, "veiculos", "excluir")


def test_campos_ocultos_sao_negados_e_o_resto_permanece_visivel(
    db_session: Session,
) -> None:
    vendedores = perfil.Perfil(
        nome="Vendedores",
        paginas=["veiculos"],
        restricoes={"veiculos": {"campos_ocultos": ["preco", "investidor"]}},
    )
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    assert not perfil.pode_ver_campo(vendedor, "veiculos", "preco")
    assert not perfil.pode_ver_campo(vendedor, "veiculos", "investidor")
    assert perfil.pode_ver_campo(vendedor, "veiculos", "revisao")


def test_preco_anunciado_e_preco_de_custo_sao_ocultaveis_separadamente(
    db_session: Session,
) -> None:
    vendedores = perfil.Perfil(
        nome="Vendedores",
        paginas=["veiculos"],
        restricoes={"veiculos": {"campos_ocultos": ["custo"]}},
    )
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    assert not perfil.pode_ver_campo(vendedor, "veiculos", "custo")
    assert perfil.pode_ver_campo(vendedor, "veiculos", "preco")


def test_campos_de_pagina_fora_do_perfil_sao_negados(db_session: Session) -> None:
    vendedores = perfil.Perfil(nome="Vendedores", paginas=["veiculos"])
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    assert not perfil.pode_ver_campo(vendedor, "vendas", "lucro")


def test_campos_protegidos_editaveis_de_venda_tem_mapa_de_form() -> None:
    campos_protegidos = {campo for campo, _label in perfil.CAMPOS_PROTEGIDOS["vendas"]}
    campos_form = set(perfil.CAMPOS_FORM_PROTEGIDOS["vendas"])
    campos_editaveis = {
        field.removesuffix("_id") if field.endswith("_id") else field
        for field in venda.VendaUpdate.model_fields
    }

    assert campos_protegidos & campos_editaveis <= campos_form


def test_campos_protegidos_de_veiculos_tem_mapa_de_form() -> None:
    assert perfil.CAMPOS_FORM_PROTEGIDOS["veiculos"] == {
        "modelo": "modelo",
        "marca": "marca",
        "placa": "placa",
        "chassi": "chassi",
        "renavam": "renavam",
        "tipo": "tipo",
        "ano": "ano",
        "km": "km",
        "status": "status",
        "preco": "preco",
        "tipo_entrada": "tipo_entrada",
        "investidor": "investidor_id",
        "procuracao": "procuracao",
        "proprietario_registrado": "proprietario_registrado",
        "proprietario_documento": "proprietario_documento",
        "proprietario_uf": "proprietario_uf",
        "revisao": "revisao",
        "debitos": "debitos",
    }


def test_campos_form_visiveis_does_not_mutate_inputs(
    db_session: Session,
) -> None:
    vendedores = perfil.Perfil(
        nome="Vendedores",
        paginas=["compras"],
        restricoes={"compras": {"campos_ocultos": ["valor_compra"]}},
    )
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    data = {"valor_compra": "1000", "observacoes": "ok"}

    filtered_data = perfil.campos_form_visiveis(vendedor, "compras", data)

    assert data == {"valor_compra": "1000", "observacoes": "ok"}
    assert filtered_data == {"observacoes": "ok"}


def test_operacoes_sao_opt_in(db_session: Session) -> None:
    vendedores = perfil.Perfil(
        nome="Vendedores",
        paginas=["veiculos"],
        restricoes={"veiculos": {"operacoes": ["editar"]}},
    )
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    assert perfil.pode_operacao(vendedor, "veiculos", "editar")
    assert not perfil.pode_operacao(vendedor, "veiculos", "excluir")


def test_operacoes_de_pagina_fora_do_perfil_sao_negadas(
    db_session: Session,
) -> None:
    vendedores = perfil.Perfil(
        nome="Vendedores",
        paginas=["veiculos"],
        restricoes={"vendas": {"operacoes": ["ver_fechamento"]}},
    )
    db_session.add(vendedores)
    db_session.flush()
    vendedor = _usuario(db_session, usuario.Papel.funcionario, vendedores)
    assert not perfil.pode_operacao(vendedor, "vendas", "ver_fechamento")


def test_catalogos_cobrem_as_seis_paginas_do_rollout() -> None:
    for pagina in (
        "veiculos",
        "investidores",
        "clientes",
        "compras",
        "custos-veiculos",
        "vendas",
    ):
        chaves = {chave for chave, _ in perfil.OPERACOES.get(pagina, [])}
        assert {"editar", "excluir"} <= chaves
    for pagina in ("clientes", "compras", "vendas"):
        assert {"cadastrar"} <= {chave for chave, _ in perfil.OPERACOES[pagina]}
    assert {"excluir_documento"} <= {chave for chave, _ in perfil.OPERACOES["clientes"]}
    assert {"excluir_comprovante"} <= {
        chave for chave, _ in perfil.OPERACOES["compras"]
    }
    assert {"fechar"} <= {chave for chave, _ in perfil.OPERACOES["vendas"]}
    assert {"debitos"} <= {chave for chave, _ in perfil.CAMPOS_PROTEGIDOS["veiculos"]}
    assert {
        "modelo",
        "placa",
        "tipo",
        "ano",
        "km",
        "status",
        "tipo_entrada",
        "procuracao",
    } <= {chave for chave, _ in perfil.CAMPOS_PROTEGIDOS["veiculos"]}
    assert {
        "abrir_cliente_vendedor",
        "upload_documento",
        "abrir_imagens",
        "enviar_imagens",
        "excluir_imagens",
        "abrir_procuracao",
        "enviar_procuracao",
        "excluir_procuracao",
    } <= {chave for chave, _ in perfil.OPERACOES["veiculos"]}
    assert {"lucro", "participacao"} <= {
        chave for chave, _ in perfil.CAMPOS_PROTEGIDOS["vendas"]
    }


def test_pagina_da_rota_extrai_apenas_paginas_conhecidas() -> None:
    assert perfil.pagina_da_rota("/ui/veiculos") == "veiculos"
    assert perfil.pagina_da_rota("/ui/veiculos/1/imagens") == "veiculos"
    assert perfil.pagina_da_rota("/ui/compras/1/comprovantes") == "compras"
    assert perfil.pagina_da_rota("/ui/custos-veiculos") == "custos-veiculos"
    assert perfil.pagina_da_rota("/ui/fechamentos-vendas/1") == "vendas"
    assert perfil.pagina_da_rota("/ui/rsd/puxar-dados") == "veiculos"
    assert perfil.pagina_da_rota("/ui/usuarios") is None
    assert perfil.pagina_da_rota("/ui/dashboard") is None
    assert perfil.pagina_da_rota("/static/app.css") is None
