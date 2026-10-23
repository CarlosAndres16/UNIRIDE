"""Configuracion del proceso, SQL Server y autenticacion JWT."""

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Carga variables del entorno y del archivo .env del proyecto."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    serverPort: int = Field(alias="SERVER_PORT", ge=1, le=65535)
    dbHost: str = Field(alias="DB_HOST", min_length=1)
    dbPort: int = Field(alias="DB_PORT", ge=1, le=65535)
    dbName: str = Field(alias="DB_NAME", min_length=1)
    dbUser: str = Field(alias="DB_USER", min_length=1)
    dbPassword: SecretStr = Field(alias="DB_PASSWORD", min_length=1)
    dbDriver: str = Field(alias="DB_DRIVER", min_length=1)


class JwtSettings(BaseSettings):
    """Valida el secreto JWT sin exigir una conexion a la base de datos."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    jwtSecret: SecretStr = Field(alias="JWT_SECRET", min_length=1)

    @field_validator("jwtSecret")
    @classmethod
    def validarSecreto(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("JWT_SECRET debe contener un secreto compartido no vacio.")
        return value


class HttpClientSettings(BaseSettings):
    """URLs y limites HTTP; independientes de la configuracion SQL y JWT."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8",
        extra="ignore", hide_input_in_errors=True,
    )

    viajesServiceUrl: AnyHttpUrl = Field(alias="VIAJES_SERVICE_URL")
    vehiculosServiceUrl: AnyHttpUrl = Field(alias="VEHICULOS_SERVICE_URL")
    httpTimeoutMs: int = Field(default=3000, alias="HTTP_TIMEOUT_MS", gt=0)
    httpMaxRetries: int = Field(default=1, alias="HTTP_MAX_RETRIES", ge=0, le=1)

    @field_validator("viajesServiceUrl", "vehiculosServiceUrl")
    @classmethod
    def validarUrlBase(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment or value.path not in (None, "/"):
            raise ValueError("La URL debe ser una base HTTP sin credenciales, ruta ni query.")
        return value


class ServiceAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8",
        extra="ignore", hide_input_in_errors=True,
    )

    serviceApiKey: SecretStr = Field(alias="SERVICE_API_KEY", min_length=1)

    @field_validator("serviceApiKey")
    @classmethod
    def validarSecreto(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("SERVICE_API_KEY debe contener una llave privada no vacia.")
        return value


@lru_cache(maxsize=1)
def getSettings() -> Settings:
    """Valida la configuración la primera vez que se solicita."""

    return Settings()


@lru_cache(maxsize=1)
def getJwtSettings() -> JwtSettings:
    """Carga la configuracion de seguridad solo cuando se utiliza."""

    return JwtSettings()


@lru_cache(maxsize=1)
def getHttpClientSettings() -> HttpClientSettings:
    return HttpClientSettings()


@lru_cache(maxsize=1)
def getServiceAuthSettings() -> ServiceAuthSettings:
    return ServiceAuthSettings()
