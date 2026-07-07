"""Cria o primeiro admin: uv run python development/create_admin.py <user> <senha>."""

import sys

from xtreme_system.database.core import SessionLocal
from xtreme_system.usuario import core as usuario


def main() -> None:
    try:
        _, username, senha = sys.argv
    except ValueError:
        sys.exit("uso: create_admin.py <username> <senha>")
    with SessionLocal() as session:
        if usuario.get_by_username(session, username) is not None:
            sys.exit(f"usuário '{username}' já existe")
        user = usuario.create(
            session,
            usuario.UsuarioCreate(
                username=username, senha=senha, papel=usuario.Papel.admin
            ),
        )
        print(f"admin criado: id={user.id} username={user.username}")


if __name__ == "__main__":
    main()
