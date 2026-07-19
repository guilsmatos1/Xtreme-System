"""Cria o primeiro admin: uv run python development/create_admin.py <user> <senha>."""

import sys

from sqlalchemy.orm import Session

from xtreme_system.auditoria.core import auditar, snapshot
from xtreme_system.auth.core import hash_password
from xtreme_system.database.core import SessionLocal
from xtreme_system.usuario import core as usuario


def create_first_admin(session: Session, username: str, senha: str) -> usuario.Usuario:
    if usuario.get_by_username(session, username) is not None:
        sys.exit(f"usuário '{username}' já existe")

    user = usuario.Usuario(
        username=username,
        senha_hash=hash_password(senha),
        papel=usuario.Papel.admin,
    )
    session.add(user)
    session.flush()
    session.refresh(user)
    auditar(
        session,
        actor_id=user.id,
        tabela="usuario",
        tipo_acao="CREATE",
        registro_id=user.id,
        dados_depois=snapshot(user),
    )
    return user


def main() -> None:
    try:
        _, username, senha = sys.argv
    except ValueError:
        sys.exit("uso: create_admin.py <username> <senha>")
    with SessionLocal() as session:
        user = create_first_admin(session, username, senha)
        session.commit()
        print(f"admin criado: id={user.id} username={user.username}")


if __name__ == "__main__":
    main()
