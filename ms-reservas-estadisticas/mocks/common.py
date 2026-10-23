"""Infraestructura compartida de los mocks; no abre conexiones SQL."""

from datetime import date
from functools import lru_cache
from hmac import compare_digest
import logging
import re
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.logging_config import configurarLogging
from app.config.settings import PROJECT_ROOT
from app.exceptions.exceptions import ErrorInterno, NoAutenticadoError, SolicitudInvalidaError
from app.exceptions.handlers import registrarManejadores
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.schemas.error_schema import CodigoError

logger = logging.getLogger("uniride.mocks")
serviceKeyScheme = APIKeyHeader(name="X-Service-Key", auto_error=False)


class MockEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


class ViajesMockSettings(MockEnvSettings):
    viajesServiceUrl: AnyHttpUrl = Field(alias="VIAJES_SERVICE_URL")


class VehiculosMockSettings(MockEnvSettings):
    vehiculosServiceUrl: AnyHttpUrl = Field(alias="VEHICULOS_SERVICE_URL")


class ServiceKeySettings(MockEnvSettings):
    serviceApiKey: SecretStr = Field(alias="SERVICE_API_KEY", min_length=1)

    @field_validator("serviceApiKey")
    @classmethod
    def validarSecreto(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("SERVICE_API_KEY debe contener una llave privada no vacia.")
        return value


@lru_cache(maxsize=1)
def getViajesMockSettings() -> ViajesMockSettings:
    return ViajesMockSettings()


@lru_cache(maxsize=1)
def getVehiculosMockSettings() -> VehiculosMockSettings:
    return VehiculosMockSettings()


@lru_cache(maxsize=1)
def getServiceKeySettings() -> ServiceKeySettings:
    return ServiceKeySettings()


def getServiceApiKey() -> SecretStr:
    try:
        return getServiceKeySettings().serviceApiKey
    except ValidationError:
        logger.error("No se pudo cargar la configuracion de la llave de servicio.")
        raise ErrorInterno() from None


def obtenerServiceKey(
    request: Request,
    value: Annotated[str | None, Security(serviceKeyScheme)],
) -> str:
    headers = request.headers.getlist("x-service-key")
    if len(headers) != 1 or not value or not value.strip():
        raise NoAutenticadoError("Se requiere una llave de servicio valida.")
    return value


def verificarServiceKey(
    provided: Annotated[str, Depends(obtenerServiceKey)],
    expected: Annotated[SecretStr, Depends(getServiceApiKey)],
) -> None:
    if not compare_digest(provided.encode("utf-8"), expected.get_secret_value().encode("utf-8")):
        raise NoAutenticadoError("Se requiere una llave de servicio valida.")


def crearMockBase(nombre: str) -> FastAPI:
    configurarLogging()
    application = FastAPI(
        title=nombre,
        description="Mock local en memoria para desarrollar Reservas y Estadisticas.",
        version="1.0.0",
        redoc_url=None,
    )
    registrarManejadores(application)
    application.add_middleware(CorrelationIdMiddleware)
    return application


def validarPeriodo(desde: str | None, hasta: str | None) -> tuple[date | None, date | None]:
    fechas = []
    for campo, value in (("desde", desde), ("hasta", hasta)):
        if value is None:
            fechas.append(None)
            continue
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError("Formato invalido")
            fechas.append(date.fromisoformat(value))
        except ValueError:
            raise SolicitudInvalidaError(
                "La fecha debe ser valida y usar YYYY-MM-DD.",
                detalles=[{"campo": campo, "problema": "Debe ser una fecha valida en formato YYYY-MM-DD."}],
                error=CodigoError.FECHA_HORA_INVALIDA,
            ) from None
    inicio, fin = fechas
    if inicio is not None and fin is not None and inicio > fin:
        raise SolicitudInvalidaError(
            "El periodo de consulta no es valido.",
            detalles=[{"campo": "desde", "problema": "No puede ser posterior a hasta."}],
        )
    return inicio, fin


def ejecutarMock(importPath: str, service: Literal["viajes", "vehiculos"]) -> None:
    import uvicorn

    try:
        url = (
            getViajesMockSettings().viajesServiceUrl
            if service == "viajes"
            else getVehiculosMockSettings().vehiculosServiceUrl
        )
        if url.scheme != "http" or url.path not in (None, "/") or url.query or url.fragment or url.username or url.password:
            raise ValueError("El mock necesita una URL HTTP base, sin credenciales.")
    except (ValidationError, ValueError):
        raise SystemExit("Configura la URL HTTP base del mock en su variable de entorno.") from None
    uvicorn.run(importPath, host=url.host, port=url.port, workers=1, reload=False, access_log=False)
