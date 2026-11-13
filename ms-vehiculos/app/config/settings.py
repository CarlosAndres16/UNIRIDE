"""Configuración obtenida exclusivamente de variables de entorno (sección 13)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

projectRoot = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=projectRoot / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    SERVER_PORT: int = Field(ge=1, le=65535)
    DB_HOST: str = Field(min_length=1)
    DB_PORT: int = Field(ge=1, le=65535)
    DB_NAME: str = Field(min_length=1, max_length=128)
    DB_USER: str = Field(min_length=1)
    DB_PASSWORD: SecretStr
    JWT_SECRET: SecretStr

    @field_validator("DB_PASSWORD")
    @classmethod
    def validarPassword(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("DB_PASSWORD es obligatorio.")
        return value

    @field_validator("JWT_SECRET")
    @classmethod
    def validarSecreto(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if not secret.strip() or len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET debe contener al menos 32 bytes.")
        return value


@lru_cache(maxsize=1)
def getSettings() -> Settings:
    return Settings()
