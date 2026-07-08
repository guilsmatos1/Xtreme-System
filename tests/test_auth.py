"""Auth: hash de senha e roundtrip de JWT."""

import jwt
import pytest

from xtreme_system.auth import core as auth


def test_hash_roundtrip() -> None:
    h = auth.hash_password("segredo")
    assert h != "segredo"
    assert auth.verify_password("segredo", h)
    assert not auth.verify_password("errado", h)


def test_token_roundtrip() -> None:
    token = auth.create_access_token("ana", "admin")
    dados = auth.decode_token(token)
    assert dados.username == "ana"
    assert dados.papel == "admin"


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
