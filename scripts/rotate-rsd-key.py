"""Recifra a credencial RSD após uma rotação de chave.

Defina RSD_ENCRYPTION_KEY com a chave nova e
RSD_ENCRYPTION_KEY_PREVIOUS com a chave anterior apenas durante a execução.
"""

import os

from xtreme_system.database.core import SessionLocal
from xtreme_system.rsd import core as rsd


def main() -> None:
    previous = os.environ.get("RSD_ENCRYPTION_KEY_PREVIOUS", "")
    if not previous:
        raise SystemExit("RSD_ENCRYPTION_KEY_PREVIOUS não configurada")
    session = SessionLocal()
    try:
        rsd.recriptografar_config(session, previous)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
