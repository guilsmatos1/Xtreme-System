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


def test_verify_password_uses_dummy_hash_when_user_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hashes: list[str] = []

    def verify(_senha: str, senha_hash: str) -> bool:
        hashes.append(senha_hash)
        return False

    monkeypatch.setattr(auth._hasher, "verify", verify)  # noqa: SLF001

    assert not auth.verify_password("errado", None)
    assert hashes == [auth._DUMMY_PASSWORD_HASH]  # noqa: SLF001


def test_validate_senha_rejeita_vazia_ou_fraca() -> None:
    for senha in ("", "   ", "x", "xy"):
        with pytest.raises(usuario.SenhaFracaError):
            usuario.validate_senha(senha)


def test_validate_senha_remove_espacos() -> None:
    assert usuario.validate_senha("  abc  ") == "abc"


def test_token_roundtrip() -> None:
    token = auth.create_access_token("ana", token_version=3)
    dados = auth.decode_token(token)
    assert dados.username == "ana"
    assert dados.token_version == 3


def test_token_nao_carrega_papel() -> None:
    settings = auth.get_settings()

    token = auth.create_access_token("ana")
    payload = jwt.decode(
        token, settings.auth_secret_key, algorithms=[settings.auth_algorithm]
    )

    assert payload["sub"] == "ana"
    assert "exp" in payload
    assert payload["tv"] == 0
    assert "papel" not in payload


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
