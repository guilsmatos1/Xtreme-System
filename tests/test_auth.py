"""Auth: hash de senha e roundtrip de JWT."""

import jwt
import pytest

from xtreme_system.auth import core as auth
from xtreme_system.usuario import core as usuario


def test_hash_roundtrip() -> None:
    h = auth.hash_password("segredo")
    assert h != "segredo"
    assert auth.verify_password("segredo", h)
    assert not auth.verify_password("errado", h)


def test_validate_senha_rejeita_vazia_ou_fraca() -> None:
    for senha in ("", "   ", "x", "xy"):
        with pytest.raises(usuario.SenhaFracaError):
            usuario.validate_senha(senha)


def test_validate_senha_remove_espacos() -> None:
    assert usuario.validate_senha("  abc  ") == "abc"


def test_token_roundtrip() -> None:
    token = auth.create_access_token("ana")
    dados = auth.decode_token(token)
    assert dados.username == "ana"


def test_token_invalido() -> None:
    with pytest.raises(Exception):  # noqa: B017, PT011
        auth.decode_token("nao-e-um-token")


def test_token_sem_claims_obrigatorias() -> None:
    settings = auth.get_settings()
    token = jwt.encode(
        {"foo": "bar"}, settings.auth_secret_key, algorithm=settings.auth_algorithm
    )
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token(token)
