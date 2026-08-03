from dataclasses import dataclass, field

from xtreme_system.perfil.permissions import (
    pode_acessar,
    pode_operacao,
    pode_ver_campo,
)


@dataclass
class PerfilStub:
    paginas: list[str] = field(default_factory=list)
    restricoes: dict[str, object] = field(default_factory=dict)


@dataclass
class UsuarioStub:
    is_admin: bool = False
    perfil: PerfilStub | None = None


def test_admin_bypasses_all_permission_restrictions() -> None:
    user = UsuarioStub(is_admin=True)

    assert pode_acessar(user, "qualquer-pagina")
    assert pode_ver_campo(user, "qualquer-pagina", "qualquer-campo")
    assert pode_operacao(user, "qualquer-pagina", "qualquer-operacao")


def test_plain_stubs_apply_profile_page_and_field_rules() -> None:
    user = UsuarioStub(
        perfil=PerfilStub(
            paginas=["veiculos"],
            restricoes={
                "veiculos": {
                    "campos_ocultos": ["preco"],
                    "operacoes": ["editar"],
                }
            },
        )
    )

    assert pode_acessar(user, "veiculos")
    assert not pode_acessar(user, "vendas")
    assert not pode_ver_campo(user, "veiculos", "preco")
    assert pode_ver_campo(user, "veiculos", "modelo")
    assert pode_operacao(user, "veiculos", "editar")
    assert not pode_operacao(user, "veiculos", "excluir")
