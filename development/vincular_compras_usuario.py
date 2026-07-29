"""Vincula todas as compras cadastradas a um usuário.

Uso: uv run python development/vincular_compras_usuario.py <username>
"""

import importlib
import sys

from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.compra import core as compra
from xtreme_system.database.core import SessionLocal
from xtreme_system.usuario import core as usuario

_MODELS_PARA_REGISTRAR = (
    "custo_veiculo",
    "documento_contrato_venda",
    "documento_procuracao",
    "documento_veiculo",
    "empresa",
    "fechamento_venda",
    "imagem_comprovante_compra",
    "imagem_comprovante_venda",
    "imagem_documento_cliente",
    "imagem_veiculo",
    "perfil",
    "usuario",
    "venda",
    "whatsapp",
)


def _registrar_models() -> None:
    """Carrega todos os models para o registry de mappers do SQLAlchemy."""
    for nome in _MODELS_PARA_REGISTRAR:
        importlib.import_module(f"xtreme_system.{nome}.core")


def vincular(session: Session, username: str) -> int:
    user = usuario.get_by_username(session, username)
    if user is None:
        sys.exit(f"usuário '{username}' não encontrado")

    alterados = 0
    for obj in compra.list_all(session):
        if obj.usuario_id == user.id:
            continue
        antes = snapshot(obj)
        obj.usuario_id = user.id
        session.flush()
        auditar(
            session,
            actor_id=user.id,
            tabela="compra",
            tipo_acao="UPDATE",
            registro_id=obj.id,
            dados_antes=antes,
            dados_depois=snapshot(obj),
        )
        alterados += 1
    return alterados


def main() -> int:
    if len(sys.argv) != 2:  # noqa: PLR2004
        sys.exit(
            "uso: uv run python development/vincular_compras_usuario.py <username>"
        )
    username = sys.argv[1]
    _registrar_models()
    with SessionLocal() as session:
        alterados = vincular(session, username)
        session.commit()
        print(f"{alterados} compra(s) vinculada(s) ao usuário '{username}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
