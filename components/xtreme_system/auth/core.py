"""Auth: settings, hash de senha e JWT (puro, sem FastAPI)."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_secret_key: str = "change-me"
    auth_algorithm: str = "HS256"
    auth_token_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


_hasher = PasswordHash.recommended()


class Token(BaseModel):
    access_token: str  # noqa: Pydantic field
    token_type: str = "bearer"  # noqa: Pydantic field


class TokenData(BaseModel):
    username: str
    papel: str


def hash_password(senha: str) -> str:
    return _hasher.hash(senha)


def verify_password(senha: str, senha_hash: str) -> bool:
    return _hasher.verify(senha, senha_hash)


def create_access_token(username: str, papel: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.auth_token_expire_minutes)
    payload = {"sub": username, "papel": papel, "exp": expire}
    return jwt.encode(
        payload, settings.auth_secret_key, algorithm=settings.auth_algorithm
    )


def decode_token(token: str) -> TokenData:
    settings = get_settings()
    payload = jwt.decode(
        token, settings.auth_secret_key, algorithms=[settings.auth_algorithm]
    )
    return TokenData(username=payload["sub"], papel=payload["papel"])
