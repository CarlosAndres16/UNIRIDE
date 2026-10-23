"""Transporte HTTP comun: limites, reintentos y errores publicos controlados."""

import asyncio
import logging
from typing import TypeVar
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.config.settings import HttpClientSettings, getHttpClientSettings
from app.exceptions.exceptions import ErrorInterno, ExcepcionAplicacion, ServicioDependienteNoDisponibleError
from app.middleware.correlation_id import getCorrelationId
from app.schemas.error_schema import CodigoError, ErrorResponse
from app.schemas.integracion_schema import validarTimestampExterno
from app.security.jwt_service import ConductorAutenticado

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("uniride.clients")


def getHttpClientSettingsSeguro() -> HttpClientSettings:
    try:
        return getHttpClientSettings()
    except ValidationError:
        logger.error("No se pudo cargar la configuracion HTTP del servicio.")
        raise ErrorInterno() from None


def resolverCorrelationId(correlationId: str | None = None) -> str:
    value = correlationId if correlationId is not None else getCorrelationId()
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        # Este valor viene del contexto interno, ya validado por el middleware.
        raise ErrorInterno() from None


def headersConductor(conductor: ConductorAutenticado, correlationId: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer " + conductor.token.get_secret_value(),
        "X-Correlation-Id": resolverCorrelationId(correlationId),
    }


def headersServicio(key: SecretStr, correlationId: str | None = None) -> dict[str, str]:
    if not key.get_secret_value().strip():
        raise ErrorInterno()
    return {
        "X-Service-Key": key.get_secret_value(),
        "X-Correlation-Id": resolverCorrelationId(correlationId),
    }


class ClienteHttp:
    """Usa una sesion prestada. Su propietario se encarga de cerrarla."""

    def __init__(self, settings: HttpClientSettings, httpClient: httpx.AsyncClient, baseUrl: str, dependencia: str):
        self.settings = settings
        self.httpClient = httpClient
        self.baseUrl = str(baseUrl).rstrip("/")
        self.dependencia = dependencia

    def _errorProveedor(self, response: httpx.Response) -> ExcepcionAplicacion:
        payload = response.json()
        required = {"timestamp", "status", "error", "message", "path", "correlationId"}
        if response.status_code == 400:
            required.add("detalles")
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("El error no contiene los campos requeridos")
        if response.status_code == 400 and not isinstance(payload["detalles"], list):
            raise ValueError("Los detalles deben ser una lista")
        validarTimestampExterno(payload["timestamp"])
        error = ErrorResponse.model_validate(payload)
        if error.status != response.status_code:
            raise ValueError("Estado de error incoherente")
        mensajes = {
            CodigoError.NO_AUTENTICADO: "Se requiere un token o llave de autenticacion valido.",
            CodigoError.NO_AUTORIZADO: "No tienes autorizacion para consultar este recurso.",
            CodigoError.VIAJE_NO_ENCONTRADO: "El viaje no existe.",
            CodigoError.VEHICULO_NO_ENCONTRADO: "El vehiculo no existe.",
            CodigoError.OPERACION_NO_PERMITIDA_POR_ESTADO: "El estado del viaje no permite la operacion.",
        }
        if error.status == 404:
            esperado = CodigoError.VIAJE_NO_ENCONTRADO if self.dependencia == "Viajes" else CodigoError.VEHICULO_NO_ENCONTRADO
            if error.error != esperado:
                raise ValueError("Recurso del error incoherente")
        return ExcepcionAplicacion(
            error.status, error.error,
            mensajes.get(error.error, "El proveedor rechazo la solicitud."),
            detalles=[] if error.status == 400 else None,
        )

    async def solicitar(
        self, method: str, path: str, modelo: type[T], *, headers: dict[str, str],
        params: dict | None = None, json: dict | None = None,
    ) -> T:
        method = method.upper()
        # No se admite una operacion nueva por accidente con credenciales.
        if method != "GET" and not (method == "PUT" and path.endswith("/ocupacion")):
            raise ErrorInterno()
        correlationId = resolverCorrelationId(headers.get("X-Correlation-Id"))
        headers = {**headers, "X-Correlation-Id": correlationId}
        seconds = self.settings.httpTimeoutMs / 1000
        for intento in range(self.settings.httpMaxRetries + 1):
            response = None
            retryable = True
            razon = "transporte"
            try:
                async with asyncio.timeout(seconds):
                    request = self.httpClient.build_request(
                        method, self.baseUrl + path, headers=headers, params=params,
                        json=json, timeout=httpx.Timeout(seconds),
                    )
                    # No heredar la autenticacion opuesta de una sesion inyectada.
                    request.headers.pop("Authorization" if method == "PUT" else "X-Service-Key", None)
                    response = await self.httpClient.send(request, auth=None, follow_redirects=False)
            except (httpx.RequestError, TimeoutError):
                # Nunca registrar str(error), URLs, tokens ni cuerpo de respuesta.
                pass
            else:
                if response.status_code == 200:
                    try:
                        resultado = modelo.model_validate_json(response.content)
                    except (ValidationError, ValueError):
                        razon = "respuesta_invalida"
                    else:
                        logger.info(
                            "dependencia=%s method=%s status=200 intento=%s",
                            self.dependencia, method, intento + 1,
                            extra={"correlationId": correlationId},
                        )
                        return resultado
                elif response.status_code in (400, 401, 403, 404) or (response.status_code == 409 and method == "PUT"):
                    try:
                        error = self._errorProveedor(response)
                    except (ValidationError, ValueError):
                        razon = "error_proveedor_invalido"
                        retryable = False
                    else:
                        logger.warning(
                            "dependencia=%s method=%s status=%s error=%s",
                            self.dependencia, method, error.status, error.error,
                            extra={"correlationId": correlationId},
                        )
                        raise error
                else:
                    razon = "estado_proveedor"
                    retryable = response.status_code >= 500
            logger.warning(
                "dependencia=%s method=%s fallo=%s status=%s intento=%s",
                self.dependencia, method, razon,
                response.status_code if response is not None else "sin_respuesta", intento + 1,
                extra={"correlationId": correlationId},
            )
            if not retryable:
                break
        raise ServicioDependienteNoDisponibleError() from None
